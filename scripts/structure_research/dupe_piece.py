#!/usr/bin/env python3
"""
Dupe test: copy the user's single placed piece in TransplantTest.sav,
modify it slightly (new persistent_id, offset position), append to the same
file's Pces chunk, update chunk lengths up the tree.

Expected outcome: user reloads and sees TWO of the same piece, ~2m apart.
This validates that our Pces injection mechanics work when the source piece
is known-good (placed by the user with valid ownership/state).
"""
import struct
import shutil
import sys
import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from surgical_transplant import find_gbm_nobj

TARGET = Path("~/AppData/Local/RSDragonwilds/Saved/SaveGames/TransplantTest.sav")
SPUD_CACHE = Path("~/AppData/Local/RSDragonwilds/Saved/SpudCache/L_World.lvl")
OUTPUT = TARGET.parent / f"{TARGET.name}.dupe_test"

POSITION_OFFSET_X = 200.0  # cm — 2 meters east
NEW_PERSISTENT_ID = 2


def main():
    data = bytearray(TARGET.read_bytes())
    print(f"Read: {TARGET.name}  {len(data):,} B")

    info = find_gbm_nobj(bytes(data))
    pces_start = info['pces']['body_start']
    pces_end = info['pces']['body_end']
    pces_len = pces_end - pces_start
    print(f"Pces body: 0x{pces_start:x}-0x{pces_end:x} ({pces_len} B)")

    # Extract the single piece record (it's the entire Pces body)
    piece_bytes = bytearray(data[pces_start:pces_end])
    print(f"\nOriginal piece ({len(piece_bytes)} B):")

    # Parse fields
    pid = struct.unpack_from("<I", piece_bytes, 0)[0]
    fstr_len = struct.unpack_from("<I", piece_bytes, 4)[0]
    guid = piece_bytes[8:8 + fstr_len - 1].decode('ascii')
    px, py, pz = struct.unpack_from("<3d", piece_bytes, 8 + fstr_len)
    print(f"  pid={pid}  guid={guid}")
    print(f"  pos=({px:.2f}, {py:.2f}, {pz:.2f})")

    # Modify the copy
    new_piece = bytearray(piece_bytes)
    # Set new persistent_id
    struct.pack_into("<I", new_piece, 0, NEW_PERSISTENT_ID)
    # Offset X position
    new_px = px + POSITION_OFFSET_X
    struct.pack_into("<d", new_piece, 8 + fstr_len, new_px)
    print(f"\nNew piece:")
    print(f"  pid={NEW_PERSISTENT_ID}  (was {pid})")
    print(f"  pos=({new_px:.2f}, {py:.2f}, {pz:.2f})  (X offset +{POSITION_OFFSET_X})")

    # Append to Pces body
    delta = len(new_piece)
    insert_point = pces_end
    out = bytearray()
    out.extend(data[:insert_point])
    out.extend(new_piece)
    out.extend(data[insert_point:])
    print(f"\nInserted {delta} B at 0x{insert_point:x}")
    print(f"New file size: {len(out):,} B (was {len(data):,})")

    # Update chunk lengths up the tree
    def bump(chunk_key):
        hdr = info[chunk_key]["header_off"]
        old = struct.unpack_from("<I", out, hdr + 4)[0]
        new = old + delta
        struct.pack_into("<I", out, hdr + 4, new)
        print(f"  {chunk_key.upper():5s} @ 0x{hdr:06x}  {old:,} → {new:,}")

    print(f"\nUpdating chunk lengths (all +{delta}):")
    bump("pces")
    bump("cust")

    # CUST TArray count
    ct_off = info["cust_tarray_count_off"]
    old_ct = struct.unpack_from("<i", out, ct_off)[0]
    new_ct = old_ct + delta
    struct.pack_into("<i", out, ct_off, new_ct)
    print(f"  CUST TArray count @ 0x{ct_off:06x}: {old_ct:,} → {new_ct:,}")

    bump("nobj")
    bump("lats")
    bump("levl")
    bump("lvls")
    bump("save")

    # Sanity check: re-parse
    try:
        verify = find_gbm_nobj(bytes(out))
        print(f"\n✓ Reparse: Pces body length = {verify['pces']['length']} (expected {pces_len + delta})")
    except Exception as e:
        print(f"\n✗ Reparse failed: {e}")
        raise

    # Verify SAVE length matches file size
    save_len = struct.unpack_from("<I", out, 4)[0]
    if save_len + 8 != len(out):
        print(f"✗ SAVE length mismatch!")
        raise ValueError("SAVE length mismatch")
    print(f"✓ SAVE length matches file size")

    # Walk top-level chunks
    pos = 8
    end = 8 + save_len
    while pos + 8 <= end:
        tag = bytes(out[pos:pos+4])
        length = struct.unpack_from("<I", out, pos+4)[0]
        pos += 8 + length
    if pos != end:
        print(f"✗ Top-level walk overrun: ended at 0x{pos:x}, expected 0x{end:x}")
        raise ValueError("chunk walk overrun")
    print(f"✓ Top-level chunks walk cleanly")

    OUTPUT.write_bytes(bytes(out))
    print(f"\nWrote: {OUTPUT}  ({OUTPUT.stat().st_size:,} B)")

    if SPUD_CACHE.exists():
        SPUD_CACHE.unlink()
        print(f"Cleared SpudCache: {SPUD_CACHE}")

    # Verify with parser
    sys.path.insert(0, str(HERE.parent.parent))
    from parser import WorldSave
    w = WorldSave(str(OUTPUT))
    w.load()
    pieces = w.get_placed_pieces()
    print(f"\nParser detects {len(pieces)} pieces:")
    for p in pieces:
        print(f"  pid={p['persistent_id']}  pos=({p['position']['x']:.2f}, {p['position']['y']:.2f}, {p['position']['z']:.2f})")


if __name__ == "__main__":
    main()
