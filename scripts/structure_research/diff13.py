#!/usr/bin/env python3
"""
Walk LEVL → LATS → NOBJ chunks recursively and extract each NOBJ's Name field.
Diff D vs E to find the cabin's persistence IDs.

NOBJ chunk layout (from SPUD's SpudData.h FSpudNamedObjectData):
  <chunk header: 4 bytes tag "NOBJ" + 4 bytes length>
  <chunk body>:
    FString Name                 (length-prefixed, length includes null)
    FSpudCoreActorData CoreData  (CORA sub-chunk)
    FSpudPropertyData Properties (PROP sub-chunk)
    FSpudCustomData CustomData   (CUST sub-chunk, possibly empty)
    uint32 ClassID

FString in UE4 serialization:
  int32 Length  (positive = ASCII/ANSI, negative = UTF-16, includes null terminator)
  bytes Data    (abs(length) bytes)
"""
import struct
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def read_fstring(data, off):
    """Read a UE FString. Returns (string, new_offset)."""
    length = struct.unpack_from("<i", data, off)[0]
    off += 4
    if length == 0:
        return "", off
    if length > 0:
        # ANSI string, length includes null
        raw = data[off:off + length - 1]
        off += length
        try:
            return raw.decode("ascii"), off
        except UnicodeDecodeError:
            return f"<non-ascii {length}B>", off
    else:
        # UTF-16LE string, -length includes null
        n = -length
        raw = data[off:off + (n - 1) * 2]
        off += n * 2
        try:
            return raw.decode("utf-16-le"), off
        except UnicodeDecodeError:
            return f"<non-utf16 {n}W>", off

def walk_nobjs(data, start, end):
    """
    Walk raw bytes from start to end, finding every NOBJ chunk header.
    For each NOBJ, read the Name at the start of its body.
    Returns list of dicts with offset, length, name.
    """
    nobjs = []
    pos = start
    while pos < end - 8:
        # Look for "NOBJ" at this position
        if data[pos:pos+4] == b"NOBJ":
            try:
                length = struct.unpack_from("<I", data, pos+4)[0]
                if 0 < length < 100000 and pos + 8 + length <= end:
                    body_start = pos + 8
                    # Read FString Name at start of body
                    name, after_name = read_fstring(data, body_start)
                    nobjs.append({
                        "offset": pos,
                        "length": length,
                        "name": name,
                    })
                    # Skip to end of chunk
                    pos = body_start + length
                    continue
            except struct.error:
                pass
        pos += 1
    return nobjs

def main():
    for name, path in [
        ("D", "D_with_ash_chest.sav"),
        ("E", "E_with_cabin.sav"),
    ]:
        data = load(path)
        # Find L_World LEVL chunk
        i = data.find(b"LEVL")
        length = struct.unpack_from("<I", data, i + 4)[0]
        body_start = i + 8
        body_end = body_start + length
        # Check name
        name_field, _ = read_fstring(data, body_start)
        print(f"=== {name}.sav first LEVL: '{name_field}' (len={length:,}) ===")

        nobjs = walk_nobjs(data, body_start, body_end)
        print(f"NOBJ count: {len(nobjs)}")
        # Show names (may be numeric)
        name_samples = [n["name"] for n in nobjs[:15]]
        print(f"First 15 names: {name_samples}")
        print()

        # Store for later comparison
        if name == "D":
            d_nobjs = nobjs
            d_names = {n["name"] for n in nobjs}
        else:
            e_nobjs = nobjs
            e_names = {n["name"] for n in nobjs}

    # Diff
    print("=" * 70)
    print("NOBJ names in E's L_World but not in D's L_World")
    print("=" * 70)
    new_in_e = e_names - d_names
    print(f"Total new: {len(new_in_e)}")
    # Sample first 30
    for n in list(new_in_e)[:30]:
        print(f"  {n!r}")

    # Also count by rough category (if names have prefixes)
    prefixes = Counter()
    for n in new_in_e:
        # Try to get a prefix
        if "_" in n:
            prefixes[n.split("_")[0]] += 1
        else:
            prefixes["(no prefix)"] += 1
    print(f"\nPrefix breakdown:")
    for p, c in prefixes.most_common(20):
        print(f"  {c:4d}x  {p!r}")

if __name__ == "__main__":
    main()
