#!/usr/bin/env python3
"""
First transplant test: inject ONE cabin wall record from E_with_cabin.sav into
Middle Eearth.sav. Verifies the binary insertion + chunk length fixup approach.

Strategy:
1. Read E_with_cabin.sav and locate cabin wall #1 (143 bytes starting at piece[3])
2. Read Middle Eearth.sav
3. Find Pces, LVLS, SAVE chunk offsets in Middle Eearth
4. Insert the 143 bytes at the END of Middle Eearth's Pces body
5. Increment Pces, LVLS, SAVE chunk length headers by 143
6. Rewrite the inserted record's persistent_id to a safe new value (999999)
7. Write to a new file (Middle Eearth.sav.transplant_test) for the user to manually rename

The user will then rename the test file over Middle Eearth.sav and load in-game
to verify whether a cabin wall appears at the cabin coordinates.
"""
import struct
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent

sys.path.insert(0, str(HERE))
from _paths import find_saves_dir
# Override save dir at any time by setting RSDW_SAVES_DIR env var

SAVES_DIR = find_saves_dir()
SOURCE_SAV = PROJECT / "scripts/structure_research/E_with_cabin.sav"
TARGET_SAV = SAVES_DIR / "Middle Eearth.sav"
OUTPUT_SAV = TARGET_SAV.parent / "Middle Eearth.sav.transplant_test"

NEW_PERSISTENT_ID = 999999

def find_chunk(data, tag):
    """Find first occurrence of a chunk tag, return (header_offset, body_length, body_offset)."""
    i = data.find(tag)
    if i == -1:
        return None
    length = struct.unpack_from("<I", data, i + 4)[0]
    return (i, length, i + 8)

def main():
    print(f"Reading source: {SOURCE_SAV}")
    src = bytearray(SOURCE_SAV.read_bytes())
    print(f"  size: {len(src):,} B")

    src_pces = find_chunk(src, b"Pces")
    print(f"  Pces @ 0x{src_pces[0]:x}, length {src_pces[1]} B")

    # Cabin wall #1 in E starts at body offset 0x1fc (we found this earlier)
    # and is 143 bytes long. Verify by reading the persistent_id field.
    wall_body_offset = 0x1fc
    wall_length = 143
    wall_start = src_pces[2] + wall_body_offset
    wall_end = wall_start + wall_length
    wall_bytes = bytes(src[wall_start:wall_end])

    # Sanity check: first 4 bytes should be persistent_id = 4
    assert struct.unpack_from("<I", wall_bytes, 0)[0] == 4, \
        f"Expected pid=4 at start of wall record, got {struct.unpack_from('<I', wall_bytes, 0)[0]}"
    # Bytes 8..30 should be the cabin wall GUID (after the 4-byte pid + 4-byte FString length)
    guid = wall_bytes[8:30].decode("ascii", errors="replace")
    assert guid == "4AfTREj9KmVBOF-HvMtqhw", f"Expected wall GUID, got {guid!r}"

    # Decode the position from the source bytes for sanity
    px, py, pz = struct.unpack_from("<3d", wall_bytes, 0x1f)
    print(f"  Source wall: pid=4, guid={guid}")
    print(f"               position=({px:.2f}, {py:.2f}, {pz:.2f})")
    print(f"               record size {wall_length} B")

    # Now read target
    print(f"\nReading target: {TARGET_SAV}")
    tgt = bytearray(TARGET_SAV.read_bytes())
    print(f"  size: {len(tgt):,} B")

    save_chunk = find_chunk(tgt, b"SAVE")
    lvls_chunk = find_chunk(tgt, b"LVLS")
    pces_chunk = find_chunk(tgt, b"Pces")
    print(f"  SAVE @ 0x{save_chunk[0]:x}, length {save_chunk[1]:,} B")
    print(f"  LVLS @ 0x{lvls_chunk[0]:x}, length {lvls_chunk[1]:,} B")
    print(f"  Pces @ 0x{pces_chunk[0]:x}, length {pces_chunk[1]} B")

    # Insertion point: end of Pces body
    pces_body_end = pces_chunk[2] + pces_chunk[1]
    print(f"\nInsertion point: 0x{pces_body_end:x} (end of Pces body)")

    # Build the modified bytes
    # First, rewrite the persistent_id in our local copy of wall_bytes
    new_wall = bytearray(wall_bytes)
    struct.pack_into("<I", new_wall, 0, NEW_PERSISTENT_ID)
    print(f"\nRewrote inserted persistent_id to {NEW_PERSISTENT_ID}")

    # Insert the bytes
    out = bytearray()
    out.extend(tgt[:pces_body_end])
    out.extend(new_wall)
    out.extend(tgt[pces_body_end:])
    print(f"Inserted {len(new_wall)} bytes at offset 0x{pces_body_end:x}")
    print(f"New file size: {len(out):,} B (was {len(tgt):,} B, delta +{len(new_wall)})")

    # Update chunk length headers
    delta = len(new_wall)

    # Pces length is at pces_chunk[0] + 4
    new_pces_len = pces_chunk[1] + delta
    struct.pack_into("<I", out, pces_chunk[0] + 4, new_pces_len)
    print(f"  Pces length: {pces_chunk[1]} → {new_pces_len}")

    # LVLS length is at lvls_chunk[0] + 4
    new_lvls_len = lvls_chunk[1] + delta
    struct.pack_into("<I", out, lvls_chunk[0] + 4, new_lvls_len)
    print(f"  LVLS length: {lvls_chunk[1]:,} → {new_lvls_len:,}")

    # SAVE length is at save_chunk[0] + 4
    new_save_len = save_chunk[1] + delta
    struct.pack_into("<I", out, save_chunk[0] + 4, new_save_len)
    print(f"  SAVE length: {save_chunk[1]:,} → {new_save_len:,}")

    # Write to output file
    OUTPUT_SAV.write_bytes(out)
    print(f"\nWrote: {OUTPUT_SAV}")
    print(f"Final size: {OUTPUT_SAV.stat().st_size:,} B")

    # Verification: re-parse the output with our parser
    print(f"\n=== Verification: re-parse the output ===")
    import sys
    sys.path.insert(0, str(PROJECT))
    from parser import WorldSave
    w = WorldSave(str(OUTPUT_SAV))
    w.load()
    pieces = w.get_placed_pieces()
    print(f"Detected pieces: {len(pieces)}")
    for p in pieces:
        print(f"  pid={p['persistent_id']:8d}  {p['guid'][:22]}  pos=({p['position']['x']:.1f}, {p['position']['y']:.1f}, {p['position']['z']:.1f})")

    print(f"\n✅ Done. To test in-game:")
    print(f"   1. Back up Middle Eearth.sav (game's auto-backup should suffice)")
    print(f"   2. Rename {OUTPUT_SAV.name} → Middle Eearth.sav (overwriting)")
    print(f"   3. Load Middle Eearth in-game")
    print(f"   4. Travel to ({px:.0f}, {py:.0f}, {pz:.0f}) and look for a cabin wall")

if __name__ == "__main__":
    main()
