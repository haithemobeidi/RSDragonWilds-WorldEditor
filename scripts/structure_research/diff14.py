#!/usr/bin/env python3
"""
Proper recursive SPUD chunk walker.

Format: every chunk = 4-byte tag + 4-byte uint32 length + length bytes of body.
Some chunks contain nested sub-chunks (like LEVL, LATS, SATS).

Strategy:
  - Walk a parent chunk's body byte-by-byte, treating it as a sequence of
    sub-chunks (each sub-chunk starts at the current position)
  - For each sub-chunk, read tag + length, advance past it
  - Keep going until we hit the end of the parent body
  - For LATS: each sub-chunk is NOBJ (FSpudNamedObjectData)
  - For LEVL: sub-chunks include META, VERS, CNIX, CLST, PNIX, GOBS, LATS, SATS, DATS, Pces, etc.

Goal: extract all NOBJ names from the LATS chunk inside each LEVL chunk,
diff D vs E, find the cabin's added NOBJ names.
"""
import struct
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent

# Chunk tags known to contain nested sub-chunks (per SpudData.h)
CONTAINER_TAGS = {b"SAVE", b"LVLS", b"LEVL", b"LATS", b"SATS", b"DATS", b"GOBS", b"CLST"}

def read_fstring(data, off):
    """Read a UE FString. Returns (string, new_offset)."""
    length = struct.unpack_from("<i", data, off)[0]
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
        try:
            return raw.decode("utf-16-le"), off
        except UnicodeDecodeError:
            return f"<non-utf16 {n}W>", off

def walk_chunk_body(data, body_start, body_end):
    """
    Yield (tag, sub_body_start, sub_body_length, sub_chunk_end) for each
    direct sub-chunk in the given body range.
    """
    pos = body_start
    while pos < body_end:
        if pos + 8 > len(data):
            return
        tag = bytes(data[pos:pos+4])
        length = struct.unpack_from("<I", data, pos+4)[0]
        sub_body_start = pos + 8
        sub_body_end = sub_body_start + length
        if sub_body_end > body_end:
            # Malformed or not a real chunk
            return
        yield tag, sub_body_start, length, sub_body_end
        pos = sub_body_end

def walk_lats(data, lats_body_start, lats_body_end):
    """
    Walk a LATS chunk body. Each sub-chunk is an NOBJ (FSpudNamedObjectData).
    NOBJ body layout (from SpudData.h):
      FString Name
      CORA sub-chunk (CoreActorData)
      PROP sub-chunk (PropertyData)
      CUST sub-chunk (CustomData, may be empty)
      uint32 ClassID
    Returns list of dicts.
    """
    nobjs = []
    for tag, body_start, length, body_end in walk_chunk_body(data, lats_body_start, lats_body_end):
        if tag != b"NOBJ":
            continue
        # NOBJ body layout (empirically):
        #   uint32 ClassID (at start, NOT end as SpudData.h header suggests)
        #   FString Name
        #   ...more fields...
        class_id = struct.unpack_from("<I", data, body_start)[0]
        name, name_end = read_fstring(data, body_start + 4)
        # Walk the rest — CORA, PROP, CUST, then uint32 ClassID
        sub_tags = []
        pos = name_end
        while pos < body_end - 4:
            if pos + 8 > len(data): break
            stag = bytes(data[pos:pos+4])
            if stag not in (b"CORA", b"PROP", b"CUST"):
                break
            slen = struct.unpack_from("<I", data, pos+4)[0]
            if slen < 0 or pos + 8 + slen > body_end:
                break
            sub_tags.append((stag.decode(), slen))
            pos += 8 + slen
        # ClassID is the last uint32
        class_id = None
        if pos + 4 <= body_end:
            class_id = struct.unpack_from("<I", data, pos)[0]
        nobjs.append({
            "offset": body_start - 8,
            "length": length,
            "body_end": body_end,
            "name": name,
            "sub_tags": sub_tags,
            "class_id": class_id,
        })
    return nobjs

def find_lats_in_levl(data, levl_body_start, levl_body_end):
    """
    Walk the LEVL body to find the LATS sub-chunk.
    LEVL body layout (empirically derived):
      FString Name                (length-prefixed)
      8 bytes of system/user version (two uint32s, constants 0x20a and 0x3f9)
      sub-chunks: META, LATS, SATS, DATS, Pces, etc.
    Returns (name, (lats_body_start, lats_body_end)) or (name, None).
    """
    name, pos = read_fstring(data, levl_body_start)
    # Skip the 8-byte version header
    pos += 8
    for tag, body_start, length, body_end in walk_chunk_body(data, pos, levl_body_end):
        if tag == b"LATS":
            return name, (body_start, body_end)
    return name, None

def list_levl_subchunks(data, levl_body_start, levl_body_end):
    """Debugging helper: list all sub-chunks inside a LEVL body."""
    name, pos = read_fstring(data, levl_body_start)
    pos += 8
    subs = []
    for tag, body_start, length, body_end in walk_chunk_body(data, pos, levl_body_end):
        subs.append((tag.decode(errors='replace'), body_start, length))
    return name, subs

def find_all_levls(data):
    """Find all LEVL chunks at the top level (inside SAVE → LVLS). Returns list of (name, body_start, body_end)."""
    # SAVE is at offset 0
    save_tag = data[0:4]
    if save_tag != b"SAVE":
        return []
    save_len = struct.unpack_from("<I", data, 4)[0]
    save_body_start = 8
    save_body_end = save_body_start + save_len

    # Walk SAVE to find LVLS
    lvls_body = None
    for tag, bs, length, be in walk_chunk_body(data, save_body_start, save_body_end):
        if tag == b"LVLS":
            lvls_body = (bs, be)
            break
    if lvls_body is None:
        return []

    # LVLS contains LEVL chunks directly (per FSpudStructMapData pattern)
    levls = []
    for tag, bs, length, be in walk_chunk_body(data, lvls_body[0], lvls_body[1]):
        if tag == b"LEVL":
            name, _ = read_fstring(data, bs)
            levls.append((name, bs, be))
    return levls

def main():
    for name, path in [
        ("D", "D_with_ash_chest.sav"),
        ("E", "E_with_cabin.sav"),
    ]:
        with open(HERE / path, "rb") as f:
            data = bytes(f.read())
        print(f"=== {name}.sav ({len(data):,} B) ===")

        levls = find_all_levls(data)
        print(f"Found {len(levls)} LEVL chunks")

        total_nobjs = 0
        all_names = {}
        for levl_name, bs, be in levls:
            lname, lats = find_lats_in_levl(data, bs, be)
            if lats is None:
                continue
            nobjs = walk_lats(data, lats[0], lats[1])
            total_nobjs += len(nobjs)
            all_names[levl_name] = [n["name"] for n in nobjs]

        print(f"Total NOBJs across all LEVLs: {total_nobjs}")
        # Print per-level NOBJ counts
        for levl_name, names in all_names.items():
            non_empty = [n for n in names if n]
            print(f"  {levl_name:35s}: {len(names):4d} NOBJs ({len(non_empty)} named)")

        if name == "D":
            d_names_per_levl = all_names
        else:
            e_names_per_levl = all_names

    # Diff
    print()
    print("=" * 70)
    print("NOBJ name diff (E - D) per LEVL")
    print("=" * 70)
    all_levl_names = set(d_names_per_levl.keys()) | set(e_names_per_levl.keys())
    for lname in sorted(all_levl_names):
        d_set = set(d_names_per_levl.get(lname, []))
        e_set = set(e_names_per_levl.get(lname, []))
        new = e_set - d_set
        if new:
            print(f"\n{lname}: +{len(new)} new NOBJ names")
            for n in sorted(new)[:15]:
                print(f"  {n!r}")
            if len(new) > 15:
                print(f"  ... +{len(new)-15} more")

if __name__ == "__main__":
    main()
