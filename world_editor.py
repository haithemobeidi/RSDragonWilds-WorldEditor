"""
RS Dragonwilds World Editor — focused UI for world .sav editing.

A minimal, single-purpose Flask app dedicated to world save manipulation:
  - List all worlds in the SaveGames folder
  - Show structures placed in each world (counts, types, positions)
  - Transplant structures from one world into another
  - Clone a world to a new identity
  - Toggle world mode (Standard ↔ Custom)

Runs on port 5001 (the main app uses 5000) so they don't conflict.

Run:
    python world_editor.py
"""
import os
import shutil
import struct
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, jsonify, request

# Reuse the same parser as the main app
from parser import WorldSave, discover_saves


app = Flask(__name__)


# Friendly names for known building piece GUIDs.
# Building piece classes aren't in the .pak-extracted guid_map.json (which has
# items/quests/etc.). These are empirically identified during reverse engineering.
# Add to this dict as more piece types are identified.
KNOWN_PIECE_NAMES = {
    "SEZxX0vWAzlYYDGkwphIsw": "Personal Chest",
    "PzsvXL09Q0KYg23WaYfRcg": "Ash Chest",
    "4AfTREj9KmVBOF-HvMtqhw": "Cabin Wall",
    "L9AIt0ZB6Q7GHPyDVM96iw": "Cabin Wall (Doorframe)",
    "ra70cEh9cDOb_leFJwQE2Q": "Square Floor Tile",
    "segcy0CHL7BmMbSlaE83dg": "Cottage Roof Support Wall",
    "2UsmOEgQqigQFcGR4Btfkg": "Cottage Roof Variant 1",
    "rbQt1kvlqxc5kAS6Eabung": "Cottage Roof Variant 2",
    "ybcu1EaJdCYIDHeLGhyIeg": "Cottage Roof Variant 3",
    "k6IcOKDMvU6npWyppYGNYA": "(Persistence Anchor)",
    # 2rxJ495rm0GDn4h5OWKiyQ is a shared anchor ref, NOT a piece — don't map it as one
}


def piece_friendly_name(guid: str) -> str:
    """Return a human-friendly name for a piece GUID, or the GUID itself."""
    return KNOWN_PIECE_NAMES.get(guid, guid)


# ---------- helpers ----------

def list_worlds() -> list[dict]:
    """Return summary of every world .sav in the saves directory."""
    # Files in SaveGames that aren't actual worlds — skip them
    NON_WORLD_FILES = {"EnhancedInputUserSettings.sav"}

    saves = discover_saves()
    worlds = []
    for w in saves.get("worlds", []):
        path = w["filepath"]
        if os.path.basename(path) in NON_WORLD_FILES:
            continue
        try:
            ws = WorldSave(path)
            ws.load()
            pieces = ws.get_placed_pieces()
            from collections import Counter
            piece_counts = Counter(p["guid"] for p in pieces)
            header = ws.get_header_info()
            worlds.append({
                "filename": os.path.basename(path),
                "filepath": path,
                "filesize_kb": round(os.path.getsize(path) / 1024),
                "world_name": header.get("world_name", "?"),
                "world_mode": header.get("world_mode", "unknown"),
                "save_timestamp": header.get("save_timestamp", ""),
                "piece_count": len(pieces),
                "distinct_classes": len(piece_counts),
                "piece_breakdown": [
                    {"guid": g, "name": piece_friendly_name(g), "count": c}
                    for g, c in piece_counts.most_common()
                ],
            })
        except Exception as e:
            worlds.append({
                "filename": os.path.basename(path),
                "filepath": path,
                "error": str(e),
            })
    return worlds


# ---------- routes ----------

@app.route("/")
def index():
    return render_template("world_editor.html")


@app.route("/api/worlds")
def api_worlds():
    return jsonify(list_worlds())


@app.route("/api/world/<filename>")
def api_world(filename: str):
    """Detailed info for a single world."""
    saves = discover_saves()
    target = None
    for w in saves.get("worlds", []):
        if os.path.basename(w["filepath"]) == filename:
            target = w["filepath"]
            break
    if not target:
        return jsonify({"error": f"world not found: {filename}"}), 404

    try:
        ws = WorldSave(target)
        ws.load()
        pieces = ws.get_placed_pieces()
        header = ws.get_header_info()
        from collections import Counter
        piece_counts = Counter(p["guid"] for p in pieces)
        return jsonify({
            "filename": filename,
            "filepath": target,
            "header": header,
            "piece_count": len(pieces),
            "pces_counter": ws.get_pces_counter(),
            "distinct_classes": len(piece_counts),
            "piece_breakdown": [
                {"guid": g, "name": piece_friendly_name(g), "count": c}
                for g, c in piece_counts.most_common()
            ],
            "pieces_sample": [
                {
                    "persistent_id": p["persistent_id"],
                    "guid": p["guid"],
                    "x": round(p["position"]["x"], 1),
                    "y": round(p["position"]["y"], 1),
                    "z": round(p["position"]["z"], 1),
                    "rot": round(p["rotation_deg"], 1),
                }
                for p in pieces[:50]  # cap for response size
            ],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/world/<filename>/transplant", methods=["POST"])
def api_transplant(filename: str):
    """
    Transplant building pieces from a source world into this world.
    Body: { "source_filename": "..." }
    """
    body = request.get_json() or {}
    source_filename = body.get("source_filename")
    if not source_filename:
        return jsonify({"error": "source_filename required"}), 400
    if source_filename == filename:
        return jsonify({"error": "source and target must be different"}), 400

    saves = discover_saves()
    target_path = None
    source_path = None
    for w in saves.get("worlds", []):
        base = os.path.basename(w["filepath"])
        if base == filename:
            target_path = w["filepath"]
        if base == source_filename:
            source_path = w["filepath"]

    if not target_path:
        return jsonify({"error": f"target not found: {filename}"}), 404
    if not source_path:
        return jsonify({"error": f"source not found: {source_filename}"}), 404

    try:
        source = WorldSave(source_path)
        source.load()
        target = WorldSave(target_path)
        target.load()

        # Auto-clear SpudCache so the game doesn't load stale data
        cache = _spud_cache_dir() / "L_World.lvl"
        cache_was_present = cache.exists()
        if cache_was_present:
            cache.unlink()

        result = target.transplant_structures_from(source, auto_save=True)
        result["source"] = source_filename
        result["target"] = filename
        result["spud_cache_cleared"] = cache_was_present
        result["success"] = True
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@app.route("/api/world/<filename>/clone", methods=["POST"])
def api_clone(filename: str):
    """
    Clone a world to a new filename. Generates a new WorldSaveGuid and rewrites
    internal WorldName/WorldSlotName to match the new name.

    Body: { "new_name": "..." }   (no extension, no path)
    """
    body = request.get_json() or {}
    new_name = body.get("new_name", "").strip()
    if not new_name:
        return jsonify({"error": "new_name required"}), 400
    # Sanitize: only allow alphanumerics, spaces, dashes, underscores
    if not all(c.isalnum() or c in " -_" for c in new_name):
        return jsonify({"error": "new_name can only contain letters, numbers, spaces, dashes, underscores"}), 400

    saves = discover_saves()
    source_path = None
    for w in saves.get("worlds", []):
        if os.path.basename(w["filepath"]) == filename:
            source_path = Path(w["filepath"])
            break
    if not source_path:
        return jsonify({"error": f"source not found: {filename}"}), 404

    target_path = source_path.parent / f"{new_name}.sav"
    if target_path.exists():
        return jsonify({"error": f"target already exists: {target_path.name}"}), 409

    try:
        # Read source bytes
        data = bytearray(source_path.read_bytes())

        # Get the source's WorldName so we can replace it
        ws = WorldSave(str(source_path))
        ws.load()
        header = ws.get_header_info()
        old_name = header.get("world_name", "")
        if not old_name:
            return jsonify({"error": "couldn't determine source WorldName"}), 500

        # Find old WorldName as length-prefixed FString
        old_fstring = struct.pack("<I", len(old_name) + 1) + old_name.encode("ascii") + b"\x00"
        new_fstring = struct.pack("<I", len(new_name) + 1) + new_name.encode("ascii") + b"\x00"

        if old_fstring not in bytes(data):
            return jsonify({"error": f"couldn't find length-prefixed '{old_name}' FString in save"}), 500

        # Compute byte delta and rebuild
        delta_per = len(new_fstring) - len(old_fstring)
        positions = []
        idx = 0
        d_bytes = bytes(data)
        while True:
            i = d_bytes.find(old_fstring, idx)
            if i == -1:
                break
            positions.append(i)
            idx = i + 1

        # Build replacement bytes
        out = bytearray()
        last_end = 0
        for pos in sorted(positions):
            out.extend(data[last_end:pos])
            out.extend(new_fstring)
            last_end = pos + len(old_fstring)
        out.extend(data[last_end:])

        # Update chunk lengths for chunks containing the FStrings
        # Use strict whitelist walker (similar to rename_world.py)
        if delta_per != 0:
            _update_chunk_lengths_for_string_change(out, positions, delta_per, d_bytes)

        # Generate new WorldSaveGuid (16 bytes)
        new_guid = uuid.uuid4().bytes
        # Find old GUID — it's the 16 bytes immediately preceding the FIRST occurrence of old WorldName FString
        # In the CINF chunk, the GUID lives 4 bytes (VERSION) + before the WorldName FString.
        # Easier: just find the first occurrence and grab the 16 bytes before its length prefix
        first_name_pos = positions[0]
        old_guid = bytes(data[first_name_pos - 16 : first_name_pos])

        # Replace old GUID with new GUID throughout the file
        # (Some saves have the GUID at multiple offsets — replace all)
        if old_guid in bytes(out):
            new_out = bytes(out).replace(old_guid, new_guid)
            out = bytearray(new_out)

        # Write to new file
        target_path.write_bytes(bytes(out))

        # Clear SpudCache
        cache = _spud_cache_dir() / "L_World.lvl"
        cache_was_present = cache.exists()
        if cache_was_present:
            cache.unlink()

        return jsonify({
            "success": True,
            "source": filename,
            "target": target_path.name,
            "size_bytes": len(out),
            "new_guid": new_guid.hex(),
            "spud_cache_cleared": cache_was_present,
        })
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@app.route("/api/world/<filename>/mode", methods=["POST"])
def api_world_mode(filename: str):
    """
    Toggle a world between Standard and Custom mode.
    Body: { "mode": "custom" | "standard" }
    """
    body = request.get_json() or {}
    mode = body.get("mode", "").lower()
    if mode not in ("standard", "custom"):
        return jsonify({"error": "mode must be 'standard' or 'custom'"}), 400

    saves = discover_saves()
    target_path = None
    for w in saves.get("worlds", []):
        if os.path.basename(w["filepath"]) == filename:
            target_path = w["filepath"]
            break
    if not target_path:
        return jsonify({"error": f"world not found: {filename}"}), 404

    try:
        ws = WorldSave(target_path)
        ws.load()
        old_mode = ws.get_world_mode()
        if mode == "custom":
            ok = ws.convert_to_custom()
        else:
            ok = ws.revert_to_standard()
        if not ok:
            return jsonify({"error": "couldn't locate world mode bytes"}), 500
        ws.save()
        return jsonify({
            "success": True,
            "filename": filename,
            "old_mode": old_mode,
            "new_mode": ws.get_world_mode(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- helper internals ----------

def _spud_cache_dir() -> Path:
    """Locate the SpudCache directory cross-platform."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts" / "structure_research"))
    from _paths import find_cache_dir
    return find_cache_dir()


def _update_chunk_lengths_for_string_change(out: bytearray, positions: list[int], delta_per: int, original: bytes):
    """
    For each chunk in `original` whose body contains one or more of the
    `positions`, update its length field in `out` by `count_inside * delta_per`.
    Only walks recognized SPUD container chunks to avoid phantom-chunk bugs.
    """
    VALID_TAGS = {
        b"SAVE", b"INFO", b"CINF", b"META", b"SHOT",
        b"CLST", b"CDEF", b"CNIX", b"PNIX", b"VERS",
        b"NOBJ", b"SPWN", b"KILL", b"LVLS", b"LEVL",
        b"GLOB", b"GOBS", b"LATS", b"SATS", b"DATS",
        b"PDEF", b"PROP", b"CUST", b"CORA",
    }
    RECURSE_TAGS = {
        b"SAVE", b"INFO", b"CINF", b"CLST", b"GLOB", b"GOBS",
        b"LVLS", b"LEVL", b"LATS", b"SATS", b"DATS", b"META",
    }

    chunk_counts: dict[int, int] = {}

    def recurse(body_start, body_end):
        pos = body_start
        while pos + 8 <= body_end:
            tag = original[pos:pos+4]
            length = struct.unpack_from("<I", original, pos + 4)[0]
            child_body_start = pos + 8
            child_body_end = child_body_start + length
            if tag not in VALID_TAGS or length < 0 or length > 100_000_000 or child_body_end > body_end:
                pos += 1
                continue
            contained = sum(1 for p in positions if child_body_start <= p < child_body_end)
            if contained > 0:
                chunk_counts[pos] = contained
                if tag in RECURSE_TAGS:
                    recurse(child_body_start, child_body_end)
            pos = child_body_end

    save_length = struct.unpack_from("<I", original, 4)[0]
    save_body_start = 8
    save_body_end = save_body_start + save_length
    contained = sum(1 for p in positions if save_body_start <= p < save_body_end)
    if contained > 0:
        chunk_counts[0] = contained
    recurse(save_body_start, save_body_end)

    # For each containing chunk, decrement its length in `out` by count*delta_per
    # The chunk's header offset in `out` shifts by the cumulative delta of preceding occurrences.
    def cumulative_shift(old_offset):
        return sum(delta_per for p in positions if p < old_offset)

    for hdr_off, count in chunk_counts.items():
        old_length = struct.unpack_from("<I", original, hdr_off + 4)[0]
        new_length = old_length + count * delta_per
        new_hdr_off = hdr_off + cumulative_shift(hdr_off)
        struct.pack_into("<I", out, new_hdr_off + 4, new_length)


if __name__ == "__main__":
    print("=" * 60)
    print("RS Dragonwilds World Editor")
    print("=" * 60)
    print("Open: http://localhost:5001")
    print("(or http://127.0.0.1:5001 if localhost doesn't resolve)")
    print()
    print("⚠️  Always close the game before editing world files.")
    print("⚠️  Back up your saves before any destructive operations.")
    print()
    # Bind to 0.0.0.0 so it's reachable from a Windows browser when running
    # under WSL (WSL2 sometimes has trouble forwarding 127.0.0.1).
    app.run(host="0.0.0.0", port=5001, debug=False)
