#!/usr/bin/env python3
"""
Parameterized surgical cabin transplant.

Copies structure pieces from source world's GlobalBuildingManager NOBJ into
target world's GBM NOBJ, preserving target's existing state.

Usage:
  python surgical_transplant_v2.py <source_save> <target_save> [--output OUTPUT]

By default writes to <target_save>.surgical_test so you can manually verify
before overwriting.
"""
import struct
import shutil
import sys
import datetime
import argparse
from pathlib import Path

# Import the GBM locator from the original script
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from surgical_transplant import find_gbm_nobj, read_u32_le, read_i32_le


def transplant(source_path: Path, target_path: Path, output_path: Path, verbose: bool = True):
    """
    Extract Pces records from source's GBM NOBJ and append to target's GBM NOBJ.
    Updates all 8 chunk length headers up the tree. Writes result to output_path.
    """
    def log(msg):
        if verbose:
            print(msg)

    # Read source
    src_data = source_path.read_bytes()
    log(f"Source: {source_path.name}  size: {len(src_data):,} B")
    src = find_gbm_nobj(src_data)
    log(f"  GBM NOBJ @ 0x{src['nobj']['header_off']:x}  length={src['nobj']['length']}")
    log(f"  GBM Pces body length: {src['pces']['length']}")

    # Read target
    tgt_data = bytearray(target_path.read_bytes())
    log(f"\nTarget: {target_path.name}  size: {len(tgt_data):,} B")
    tgt = find_gbm_nobj(bytes(tgt_data))
    log(f"  GBM NOBJ @ 0x{tgt['nobj']['header_off']:x}  length={tgt['nobj']['length']}")
    log(f"  GBM Pces body length: {tgt['pces']['length']}")

    # Extract source Pces body bytes
    src_pces_body = src_data[src['pces']['body_start']:src['pces']['body_end']]
    delta = len(src_pces_body)
    log(f"\nSource Pces body: {delta} B (will be appended to target)")

    # Insert at end of target's Pces body
    insert_point = tgt['pces']['body_end']
    out = bytearray()
    out.extend(tgt_data[:insert_point])
    out.extend(src_pces_body)
    out.extend(tgt_data[insert_point:])
    log(f"Inserted {delta} B at offset 0x{insert_point:x}")
    log(f"New size: {len(out):,} B (was {len(tgt_data):,})")

    # Update chunk lengths up the tree
    def bump(chunk_key):
        hdr = tgt[chunk_key]["header_off"]
        old = struct.unpack_from("<I", out, hdr + 4)[0]
        new = old + delta
        struct.pack_into("<I", out, hdr + 4, new)
        log(f"  {chunk_key.upper():5s} @ 0x{hdr:06x}  length: {old:,} → {new:,}")

    log(f"\nUpdating chunk lengths (all +{delta}):")
    bump("pces")
    bump("cust")

    # Update CUST TArray count
    cust_ct_off = tgt["cust_tarray_count_off"]
    old_ct = struct.unpack_from("<i", out, cust_ct_off)[0]
    new_ct = old_ct + delta
    struct.pack_into("<i", out, cust_ct_off, new_ct)
    log(f"  CUST TArray count @ 0x{cust_ct_off:06x}: {old_ct:,} → {new_ct:,}")

    bump("nobj")
    bump("lats")
    bump("levl")
    bump("lvls")
    bump("save")

    # Sanity check: verify the output parses cleanly
    log(f"\nSanity check — re-parse the output:")
    try:
        verify = find_gbm_nobj(bytes(out))
        log(f"  ✓ GBM NOBJ reparsed @ 0x{verify['nobj']['header_off']:x}  length={verify['nobj']['length']}")
        log(f"  ✓ Pces body length: {verify['pces']['length']} (expected {tgt['pces']['length'] + delta})")
    except Exception as e:
        log(f"  ✗ Reparse failed: {e}")
        raise

    # Deep sanity check: walk the entire top-level SAVE and verify chunk hierarchy
    save_len_new = struct.unpack_from("<I", out, 4)[0]
    if save_len_new + 8 != len(out):
        log(f"  ✗ SAVE length mismatch: {save_len_new} + 8 = {save_len_new+8}, file is {len(out)}")
        raise ValueError("SAVE length mismatch")
    log(f"  ✓ SAVE length matches file size")

    # Also verify that walking top-level chunks reaches the end cleanly
    pos = 8
    end = 8 + save_len_new
    chunks_walked = []
    while pos + 8 <= end:
        tag = bytes(out[pos:pos+4])
        length = struct.unpack_from("<I", out, pos+4)[0]
        chunks_walked.append((tag, length))
        pos += 8 + length
    if pos != end:
        log(f"  ✗ Top-level chunk walk ended at 0x{pos:x}, expected 0x{end:x}")
        raise ValueError("chunk walk overrun")
    log(f"  ✓ Top-level chunks walk cleanly ({len(chunks_walked)} chunks): {[t[0].decode() for t in chunks_walked]}")

    # Backup target
    if output_path.exists() and output_path != target_path:
        pass  # output is a test file, overwrite fine
    if output_path == target_path:
        # Overwriting in place — make a backup first
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = target_path.parent / f"{target_path.name}.before_transplant_{ts}"
        shutil.copy(target_path, backup)
        log(f"\nBacked up target to: {backup.name}")

    # Write output
    output_path.write_bytes(bytes(out))
    log(f"\nWrote: {output_path}")
    log(f"  size: {output_path.stat().st_size:,} B")

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("target", type=Path)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--clear-cache", action="store_true")
    args = ap.parse_args()

    output = args.output or (args.target.parent / f"{args.target.name}.surgical_test")
    transplant(args.source, args.target, output)

    if args.clear_cache:
        cache = Path("~/AppData/Local/RSDragonwilds/Saved/SpudCache/L_World.lvl")
        if cache.exists():
            cache.unlink()
            print(f"\nCleared SpudCache: {cache}")


if __name__ == "__main__":
    main()
