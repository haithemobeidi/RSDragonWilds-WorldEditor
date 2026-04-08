#!/usr/bin/env python3
"""
Surgical cabin transplant.

Source: E_with_cabin.sav (has cabin in GlobalBuildingManager's CUST/Pces)
Target: Middle Eearth.sav (empty-ish — has only a k6Ic... anchor piece)

Operation:
  1. Find source's GBM NOBJ, extract its CUST body → contains a Pces chunk
     with all piece records
  2. Find target's GBM NOBJ, extract its CUST body → contains a Pces chunk
     with the target's existing piece records
  3. Compute NEW pieces present in source but not target (by class GUID + position)
  4. Build a merged CUST body: target's existing Pces records + source's new records
  5. Rewrite target's GBM NOBJ's CUST chunk with the merged content
  6. Update the chunk-length chain going UP the tree:
     - CUST TArray count uint32
     - CUST chunk length
     - NOBJ chunk length
     - LATS chunk length
     - LEVL chunk length
     - LVLS chunk length
     - SAVE chunk length
  7. Write target with backup
  8. Clear SpudCache
"""
import os
import sys
import struct
import shutil
import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent

sys.path.insert(0, str(HERE))
from _paths import find_saves_dir, find_cache_dir

SAVES_DIR = find_saves_dir()
SOURCE_SAV = HERE / "E_with_cabin.sav"
TARGET_SAV = SAVES_DIR / "Middle Eearth.sav"
SPUD_CACHE = find_cache_dir() / "L_World.lvl"


# ---------- low-level helpers ----------

def read_u32_le(data, off):
    return struct.unpack_from("<I", data, off)[0]

def write_u32_le(data, off, value):
    struct.pack_into("<I", data, off, value)

def read_i32_le(data, off):
    return struct.unpack_from("<i", data, off)[0]

def read_fstring(data, off):
    """UE FString: int32 length + ASCII/UTF-16 bytes. Returns (string, new_offset)."""
    length = read_i32_le(data, off)
    off += 4
    if length == 0:
        return "", off
    if length > 0:
        raw = data[off:off + length - 1]
        off += length
        try:
            return raw.decode("ascii"), off
        except UnicodeDecodeError:
            return f"<non-ascii {length}B>", off
    else:
        n = -length
        raw = data[off:off + (n - 1) * 2]
        off += n * 2
        return raw.decode("utf-16-le", errors="replace"), off


# ---------- chunk walkers ----------

def find_chunk_by_tag(data, tag, start=0, end=None):
    """Find the first chunk with this tag in [start, end). Returns (header_off, length, body_start, body_end)."""
    if end is None:
        end = len(data)
    i = start
    while i < end - 8:
        if data[i:i+4] == tag:
            length = read_u32_le(data, i + 4)
            if 0 <= length < 50_000_000:
                return i, length, i + 8, i + 8 + length
        i += 1
    return None


def walk_sub_chunks(data, body_start, body_end):
    """Walk sub-chunks sequentially inside a parent body. Yields (tag, header_off, length, body_start, body_end)."""
    pos = body_start
    while pos + 8 <= body_end:
        tag = bytes(data[pos:pos+4])
        length = read_u32_le(data, pos + 4)
        sub_body_start = pos + 8
        sub_body_end = sub_body_start + length
        if sub_body_end > body_end or length > 50_000_000:
            return
        yield tag, pos, length, sub_body_start, sub_body_end
        pos = sub_body_end


# ---------- GBM NOBJ locator ----------

def find_gbm_nobj(data):
    """
    Walk SAVE → LVLS → L_World LEVL → LATS → GBM NOBJ.
    Returns a dict with all the offsets we need for the length-update chain.
    """
    # SAVE
    save = find_chunk_by_tag(data, b"SAVE", 0)
    assert save is not None, "No SAVE chunk"
    save_header_off, save_len, save_body_start, save_body_end = save

    # LVLS (direct child of SAVE)
    lvls = find_chunk_by_tag(data, b"LVLS", save_body_start, save_body_end)
    assert lvls is not None, "No LVLS chunk"
    lvls_header_off, lvls_len, lvls_body_start, lvls_body_end = lvls

    # L_World LEVL (first LEVL inside LVLS that has name "L_World")
    l_world_levl = None
    for tag, hdr, length, bs, be in walk_sub_chunks(data, lvls_body_start, lvls_body_end):
        if tag != b"LEVL":
            continue
        name, _ = read_fstring(data, bs)
        if name == "L_World":
            l_world_levl = (hdr, length, bs, be)
            break
    assert l_world_levl is not None, "No L_World LEVL chunk"
    levl_header_off, levl_len, levl_body_start, levl_body_end = l_world_levl

    # LATS (sub-chunk of LEVL, after name FString + 8-byte version header)
    _, after_name_pos = read_fstring(data, levl_body_start)
    after_version_pos = after_name_pos + 8
    lats = None
    for tag, hdr, length, bs, be in walk_sub_chunks(data, after_version_pos, levl_body_end):
        if tag == b"LATS":
            lats = (hdr, length, bs, be)
            break
    assert lats is not None, "No LATS chunk in L_World"
    lats_header_off, lats_len, lats_body_start, lats_body_end = lats

    # GBM NOBJ (NOBJ inside LATS whose name contains "GlobalBuildingManager")
    gbm_nobj = None
    for tag, hdr, length, bs, be in walk_sub_chunks(data, lats_body_start, lats_body_end):
        if tag != b"NOBJ":
            continue
        # NOBJ body: uint32 ClassID, FString Name, ...
        class_id = read_u32_le(data, bs)
        name, _ = read_fstring(data, bs + 4)
        if "GlobalBuildingManager" in name:
            gbm_nobj = (hdr, length, bs, be, name, class_id)
            break
    assert gbm_nobj is not None, "No GlobalBuildingManager NOBJ found"
    nobj_header_off, nobj_len, nobj_body_start, nobj_body_end, nobj_name, nobj_class_id = gbm_nobj

    # Now walk the NOBJ body to find CUST
    # Body layout: ClassID(4) + FString Name + 12 bytes meta + 8 bytes version + CORA + PROP + CUST
    pos = nobj_body_start + 4  # skip ClassID
    _, pos = read_fstring(data, pos)  # skip Name
    pos += 12  # skip 3 uint32 metadata
    pos += 8   # skip 8-byte version header
    cust = None
    cora = None
    prop = None
    for tag, hdr, length, bs, be in walk_sub_chunks(data, pos, nobj_body_end):
        if tag == b"CORA":
            cora = (hdr, length, bs, be)
        elif tag == b"PROP":
            prop = (hdr, length, bs, be)
        elif tag == b"CUST":
            cust = (hdr, length, bs, be)
    assert cust is not None, "No CUST chunk in GBM NOBJ"
    cust_header_off, cust_len, cust_body_start, cust_body_end = cust

    # CUST body: int32 TArray count + count bytes of raw data
    tarray_count = read_i32_le(data, cust_body_start)
    tarray_data_start = cust_body_start + 4
    tarray_data_end = tarray_data_start + tarray_count

    # Inside the TArray data we find: [1 byte prefix] Pces chunk
    # The prefix byte is 0 in our data, but search for Pces tag to be safe
    pces_search_start = tarray_data_start
    pces = find_chunk_by_tag(data, b"Pces", pces_search_start, tarray_data_end)
    assert pces is not None, "No Pces chunk inside GBM CUST"
    pces_header_off, pces_len, pces_body_start, pces_body_end = pces

    return {
        "save": {"header_off": save_header_off, "length": save_len, "body_start": save_body_start, "body_end": save_body_end},
        "lvls": {"header_off": lvls_header_off, "length": lvls_len, "body_start": lvls_body_start, "body_end": lvls_body_end},
        "levl": {"header_off": levl_header_off, "length": levl_len, "body_start": levl_body_start, "body_end": levl_body_end},
        "lats": {"header_off": lats_header_off, "length": lats_len, "body_start": lats_body_start, "body_end": lats_body_end},
        "nobj": {"header_off": nobj_header_off, "length": nobj_len, "body_start": nobj_body_start, "body_end": nobj_body_end, "name": nobj_name, "class_id": nobj_class_id},
        "cust": {"header_off": cust_header_off, "length": cust_len, "body_start": cust_body_start, "body_end": cust_body_end},
        "cust_tarray_count_off": cust_body_start,
        "cust_tarray_count": tarray_count,
        "cust_tarray_data_start": tarray_data_start,
        "cust_tarray_data_end": tarray_data_end,
        "pces": {"header_off": pces_header_off, "length": pces_len, "body_start": pces_body_start, "body_end": pces_body_end},
    }


# ---------- main transplant ----------

def main():
    print(f"Source: {SOURCE_SAV}")
    src_data = SOURCE_SAV.read_bytes()
    print(f"  size: {len(src_data):,} B")
    src = find_gbm_nobj(src_data)
    print(f"  GBM NOBJ @ 0x{src['nobj']['header_off']:x}, length {src['nobj']['length']}")
    print(f"  GBM Pces @ 0x{src['pces']['header_off']:x}, body length {src['pces']['length']}")

    print(f"\nTarget: {TARGET_SAV}")
    tgt_data = bytearray(TARGET_SAV.read_bytes())
    print(f"  size: {len(tgt_data):,} B")
    tgt = find_gbm_nobj(bytes(tgt_data))
    print(f"  GBM NOBJ @ 0x{tgt['nobj']['header_off']:x}, length {tgt['nobj']['length']}")
    print(f"  GBM Pces @ 0x{tgt['pces']['header_off']:x}, body length {tgt['pces']['length']}")

    # Extract source's Pces body (just the piece records)
    src_pces_body = src_data[src['pces']['body_start']:src['pces']['body_end']]
    tgt_pces_body = bytes(tgt_data[tgt['pces']['body_start']:tgt['pces']['body_end']])

    print(f"\nSource Pces body: {len(src_pces_body)} B")
    print(f"Target Pces body: {len(tgt_pces_body)} B")

    # Simplest merge strategy: append source's records to target's existing body.
    # Source is E (has cabin + 3 chests), target is Middle Eearth (has 1 anchor piece).
    # For the first test, just concatenate: target's existing + ALL of source's records.
    # This means the target will have the anchor + all source records.
    merged_pces_body = tgt_pces_body + src_pces_body
    delta = len(src_pces_body)
    print(f"\nMerged Pces body: {len(merged_pces_body)} B (delta +{delta})")

    # Backup target
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = TARGET_SAV.parent / f"{TARGET_SAV.name}.before_surgical_{timestamp}"
    shutil.copy(TARGET_SAV, backup_path)
    print(f"\nBacked up target to: {backup_path.name}")

    # Build the new target bytes.
    # The insertion point is the END of target's Pces body (= tgt['pces']['body_end']).
    # We insert `delta` bytes of source's Pces body content there.
    insert_point = tgt['pces']['body_end']
    insert_bytes = bytes(src_pces_body)

    out = bytearray()
    out.extend(tgt_data[:insert_point])
    out.extend(insert_bytes)
    out.extend(tgt_data[insert_point:])
    print(f"Inserted {len(insert_bytes)} bytes at offset 0x{insert_point:x}")
    print(f"New file size: {len(out):,} B (was {len(tgt_data):,} B)")

    # Now update all length fields up the chain.
    # Each chunk's length field is at header_off + 4.
    def bump_length(chunk_key, extra):
        old_len = struct.unpack_from("<I", out, tgt[chunk_key]["header_off"] + 4)[0]
        new_len = old_len + extra
        struct.pack_into("<I", out, tgt[chunk_key]["header_off"] + 4, new_len)
        print(f"  {chunk_key.upper():5s} @ 0x{tgt[chunk_key]['header_off']:x}  length: {old_len:,} → {new_len:,}")

    print(f"\nUpdating chunk lengths (all bumped by +{delta}):")
    bump_length("pces", delta)
    bump_length("cust", delta)

    # CUST TArray count is at cust_tarray_count_off (int32)
    old_tarray = struct.unpack_from("<i", out, tgt["cust_tarray_count_off"])[0]
    new_tarray = old_tarray + delta
    struct.pack_into("<i", out, tgt["cust_tarray_count_off"], new_tarray)
    print(f"  CUST TArray count @ 0x{tgt['cust_tarray_count_off']:x}: {old_tarray:,} → {new_tarray:,}")

    bump_length("nobj", delta)
    bump_length("lats", delta)
    bump_length("levl", delta)
    bump_length("lvls", delta)
    bump_length("save", delta)

    # Write to a _surgical_test file so the user can verify before replacing Middle Eearth.sav
    output_path = TARGET_SAV.parent / f"{TARGET_SAV.name}.surgical_test"
    output_path.write_bytes(bytes(out))
    print(f"\nWrote: {output_path}")
    print(f"  final size: {output_path.stat().st_size:,} B")

    # Clear SpudCache
    if SPUD_CACHE.exists():
        SPUD_CACHE.unlink()
        print(f"Cleared SpudCache: {SPUD_CACHE}")

    # Verification: re-parse the output
    print(f"\n=== Verification ===")
    out_data = bytes(out)
    verify = find_gbm_nobj(out_data)
    print(f"GBM NOBJ length: {verify['nobj']['length']} (was {tgt['nobj']['length']})")
    print(f"GBM Pces length: {verify['pces']['length']} (was {tgt['pces']['length']})")

    # Also re-parse as WorldSave and list pieces
    import sys
    sys.path.insert(0, str(PROJECT))
    from parser import WorldSave
    w = WorldSave(str(output_path))
    w.load()
    pieces = w.get_placed_pieces()
    print(f"Detected pieces: {len(pieces)}")
    from collections import Counter
    by_guid = Counter(p['guid'] for p in pieces)
    for g, c in by_guid.most_common():
        print(f"  {c:3d}x {g}")

    print(f"\n✅ Done. To test in-game:")
    print(f"   1. Rename {output_path.name} → {TARGET_SAV.name} (overwrite)")
    print(f"   2. Load Middle Eearth in-game")
    print(f"   3. Travel to cabin coords ~(13012, 184231, -3187)")


if __name__ == "__main__":
    main()
