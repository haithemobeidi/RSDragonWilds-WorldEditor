#!/usr/bin/env python3
"""
Surgical transplant v3 — with GBM PROP counter update.

Hypothesis: the GlobalBuildingManager NOBJ's PROP chunk contains 4 properties.
prop[2] is a uint32 counter (persistent_id counter or total pieces). If the
target's counter is too low, the game rejects transplanted pieces with higher
IDs.

v3 copies pieces AND updates the target's PROP[2] to max(target, source) so
transplanted piece IDs are all within the counter's range.

Usage: python surgical_transplant_v3.py <source> <target> [--output OUTPUT]
"""
import struct
import shutil
import sys
import datetime
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from surgical_transplant import find_gbm_nobj, read_u32_le, read_i32_le, walk_sub_chunks, read_fstring


def find_gbm_prop_counter_offset(data, gbm_info):
    """
    Find the offset of PROP[2] (the uint32 counter) inside the GBM NOBJ's PROP sub-chunk.
    Returns the absolute byte offset in the file.
    """
    pos = gbm_info['nobj']['body_start']
    pos += 4  # ClassID
    _, pos = read_fstring(data, pos)
    pos += 12 + 8  # metadata + version header

    for tag, hdr, length, bs, be in walk_sub_chunks(data, pos, gbm_info['nobj']['body_end']):
        if tag == b'PROP':
            # PROP body:
            #   int32 offsets_count
            #   N × uint32 offsets
            #   int32 data_count
            #   data bytes
            p = bs
            offsets_count = struct.unpack_from('<i', data, p)[0]
            p += 4
            offsets = list(struct.unpack_from(f'<{offsets_count}I', data, p))
            p += offsets_count * 4
            data_count = struct.unpack_from('<i', data, p)[0]
            p += 4
            data_start = p
            # prop[2] is at offsets[2] within the data blob
            if len(offsets) >= 3:
                prop2_abs = data_start + offsets[2]
                current = struct.unpack_from('<I', data, prop2_abs)[0]
                return prop2_abs, current
    return None, None


def transplant(source_path: Path, target_path: Path, output_path: Path):
    print(f"Source: {source_path.name}")
    src_data = source_path.read_bytes()
    src = find_gbm_nobj(src_data)
    src_prop2_off, src_prop2 = find_gbm_prop_counter_offset(src_data, src)
    print(f"  GBM Pces body length: {src['pces']['length']}")
    print(f"  GBM PROP[2] counter: {src_prop2}")

    print(f"\nTarget: {target_path.name}")
    tgt_data = bytearray(target_path.read_bytes())
    tgt = find_gbm_nobj(bytes(tgt_data))
    tgt_prop2_off, tgt_prop2 = find_gbm_prop_counter_offset(bytes(tgt_data), tgt)
    print(f"  GBM Pces body length: {tgt['pces']['length']}")
    print(f"  GBM PROP[2] counter: {tgt_prop2}")

    # Extract source Pces body
    src_pces_body = src_data[src['pces']['body_start']:src['pces']['body_end']]
    delta = len(src_pces_body)
    print(f"\nInserting {delta} B of Pces records into target...")

    # Insert at end of target's Pces body
    insert_point = tgt['pces']['body_end']
    out = bytearray()
    out.extend(tgt_data[:insert_point])
    out.extend(src_pces_body)
    out.extend(tgt_data[insert_point:])

    # Update chunk lengths up the tree
    def bump(chunk_key):
        hdr = tgt[chunk_key]["header_off"]
        old = struct.unpack_from("<I", out, hdr + 4)[0]
        new = old + delta
        struct.pack_into("<I", out, hdr + 4, new)

    bump("pces")
    bump("cust")
    cust_ct_off = tgt["cust_tarray_count_off"]
    struct.pack_into("<i", out, cust_ct_off,
                     struct.unpack_from("<i", out, cust_ct_off)[0] + delta)
    bump("nobj")
    bump("lats")
    bump("levl")
    bump("lvls")
    bump("save")

    # 🎯 v3: Update the GBM PROP[2] counter
    # Set to max(target_current, source_current). No headroom — we don't know
    # what the counter actually represents (next id? max id? total count?),
    # so the safest bet is to match the source value which we know the game
    # accepts, unless the target is already higher.
    new_prop2 = max(tgt_prop2, src_prop2)
    # The PROP[2] offset in the output is the same as in tgt_data because the
    # insertion happened AFTER it (Pces is after PROP in the NOBJ body).
    # Verify: tgt_prop2_off should be < insert_point
    assert tgt_prop2_off < insert_point, f"PROP[2] at 0x{tgt_prop2_off:x} is not before insert point 0x{insert_point:x}"
    struct.pack_into('<I', out, tgt_prop2_off, new_prop2)
    print(f"  Updated GBM PROP[2] counter: {tgt_prop2} → {new_prop2}")

    # Sanity check
    verify = find_gbm_nobj(bytes(out))
    print(f"\n✓ Reparse: Pces length = {verify['pces']['length']}")
    save_len = struct.unpack_from("<I", out, 4)[0]
    assert save_len + 8 == len(out), f"SAVE length mismatch"
    print(f"✓ SAVE length matches")

    # Walk top-level
    pos = 8
    end = 8 + save_len
    while pos + 8 <= end:
        length = struct.unpack_from("<I", out, pos+4)[0]
        pos += 8 + length
    assert pos == end, f"Top-level walk overrun"
    print(f"✓ Top-level walk clean")

    output_path.write_bytes(bytes(out))
    print(f"\nWrote: {output_path}  ({output_path.stat().st_size:,} B)")

    # Clear SpudCache
    sys.path.insert(0, str(HERE))
    from _paths import find_cache_dir
    cache = find_cache_dir() / "L_World.lvl"
    if cache.exists():
        cache.unlink()
        print(f"Cleared SpudCache")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("target", type=Path)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    output = args.output or (args.target.parent / f"{args.target.name}.surgical_v3")
    transplant(args.source, args.target, output)


if __name__ == "__main__":
    main()
