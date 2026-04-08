#!/usr/bin/env python3
"""
Parse Pces records into a structured list. Verify counts match expectations:
  D should have 3 records (3 chests)
  E should have 36 records (3 chests + 33 cabin pieces)

Record format (hypothesis from inspection):
  uint32   record_index            sequential 1, 2, 3, ...
  FString  guid                    length-prefixed (length always 23 = 22-char base64 + null)
  double   pos_x, pos_y, pos_z
  float    extra_a, extra_b, extra_c   (height/scale? 45.0, 1.0, 1.0 in record 1)
  uint32   ref_count
  FString  refs[ref_count]
  uint32   status_count
  uint32   status[status_count]
"""
import struct
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_pces(data):
    i = data.find(b"Pces")
    if i == -1:
        return None
    length = struct.unpack_from("<I", data, i + 4)[0]
    return (i, length, data[i + 8 : i + 8 + length])

def read_fstring(data, off):
    """Read a length-prefixed string. Returns (string, new_offset)."""
    length = struct.unpack_from("<I", data, off)[0]
    if length == 0 or length > 1024:
        return None, off
    s = data[off + 4 : off + 4 + length]
    if s.endswith(b"\x00"):
        s = s[:-1]
    try:
        return s.decode("ascii"), off + 4 + length
    except UnicodeDecodeError:
        return None, off

def parse_pces_records(body):
    """Walk Pces body and extract records. Returns list of dicts."""
    records = []
    pos = 0
    expected_index = 1
    while pos < len(body):
        # Try to read uint32 index
        if pos + 4 > len(body):
            break
        index = struct.unpack_from("<I", body, pos)[0]
        if index != expected_index:
            print(f"  ⚠️  expected index {expected_index} at offset 0x{pos:x}, got {index}")
            # Try to skip ahead — bail if we drift too far
            break
        pos += 4

        # Read GUID string
        guid, new_pos = read_fstring(body, pos)
        if guid is None:
            print(f"  ⚠️  failed to read GUID at offset 0x{pos:x}")
            break
        pos = new_pos

        # Read 3 doubles (position) + 3 floats (extra)
        if pos + 24 + 12 > len(body):
            break
        px, py, pz = struct.unpack_from("<3d", body, pos)
        pos += 24
        e1, e2, e3 = struct.unpack_from("<3f", body, pos)
        pos += 12

        # Read ref_count
        if pos + 4 > len(body):
            break
        ref_count = struct.unpack_from("<I", body, pos)[0]
        pos += 4
        if ref_count > 100:
            print(f"  ⚠️  insane ref_count {ref_count} at offset 0x{pos-4:x}")
            break

        refs = []
        for _ in range(ref_count):
            ref, new_pos = read_fstring(body, pos)
            if ref is None:
                print(f"  ⚠️  failed to read ref at offset 0x{pos:x}")
                break
            refs.append(ref)
            pos = new_pos

        # Trailing format (derived empirically from records 1-5):
        #   uint32 always_1_a   (probably "all refs valid" flag = 1)
        #   uint32 always_1_b
        #   byte   always_1     (only 1 byte, not aligned)
        #   uint32 slot_count
        #   uint32 slots[slot_count]   (connection point indices to other pieces)
        if pos + 9 + 4 > len(body):
            break
        flag_a = struct.unpack_from("<I", body, pos)[0]
        flag_b = struct.unpack_from("<I", body, pos + 4)[0]
        flag_byte = body[pos + 8]
        slot_count = struct.unpack_from("<I", body, pos + 9)[0]
        if slot_count > 100:
            print(f"  ⚠️  insane slot_count {slot_count} at offset 0x{pos+9:x}, record {expected_index}")
            print(f"      bytes around: {body[pos:pos+32].hex(' ')}")
            break
        pos += 9 + 4
        slots = []
        for _ in range(slot_count):
            if pos + 4 > len(body):
                break
            slots.append(struct.unpack_from("<I", body, pos)[0])
            pos += 4

        records.append({
            "index": index,
            "guid": guid,
            "pos": (px, py, pz),
            "extra": (e1, e2, e3),
            "ref_count": ref_count,
            "refs": refs,
            "flags": (flag_a, flag_b, flag_byte),
            "slot_count": slot_count,
            "slots": slots,
        })
        expected_index += 1

    return records

def main():
    for name in ["D_with_ash_chest", "E_with_cabin"]:
        data = load(f"{name}.sav")
        pces = find_pces(data)
        body = pces[2]
        print(f"\n{'='*70}\n{name}.sav — Pces body {len(body)} B\n{'='*70}")

        records = parse_pces_records(body)
        print(f"Parsed {len(records)} records")

        # Group by GUID
        guid_counts = Counter(r["guid"] for r in records)
        print(f"\nDistinct GUIDs: {len(guid_counts)}")
        for g, c in guid_counts.most_common():
            print(f"  {c:3d}x  {g}")

        # Show all records (truncated info)
        print(f"\nAll {len(records)} records (compact):")
        for r in records:
            print(f"  [{r['index']:3d}] {r['guid'][:22]}  pos=({r['pos'][0]:9.1f},{r['pos'][1]:9.1f},{r['pos'][2]:9.1f})  extras=({r['extra'][0]:6.1f},{r['extra'][1]:6.1f},{r['extra'][2]:6.1f})  refs={r['ref_count']}  slots={r['slot_count']}")

        # Show first 5 with refs and slot detail
        print(f"\nFirst {min(5, len(records))} records (detailed):")
        for r in records[:5]:
            print(f"  [{r['index']:3d}] {r['guid']}")
            print(f"        pos = ({r['pos'][0]:10.2f}, {r['pos'][1]:10.2f}, {r['pos'][2]:10.2f})")
            print(f"        extra = ({r['extra'][0]:.4f}, {r['extra'][1]:.4f}, {r['extra'][2]:.4f})")
            print(f"        refs ({r['ref_count']}): {r['refs']}")
            print(f"        flags = {r['flags']}  slots ({r['slot_count']}): {r['slots']}")

if __name__ == "__main__":
    main()
