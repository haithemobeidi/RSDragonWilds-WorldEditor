#!/usr/bin/env python3
"""
Rename a world's internal WorldName (and filename) from one string to another.
Handles the case where the new name is shorter than the old one by updating
chunk length headers that contain the renamed FString.

Specifically for: "Middle Eearth" (13 chars) → "Middle Earth" (12 chars)
Each occurrence shrinks by 1 byte. Total shrink depends on occurrence count.
"""
import sys
import struct
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import find_saves_dir, find_cache_dir
# Override paths via RSDW_SAVES_DIR / RSDW_CACHE_DIR env vars if needed

SAVES_DIR = find_saves_dir()
SPUD_CACHE = find_cache_dir() / "L_World.lvl"

OLD_NAME = "Middle Eearth"
NEW_NAME = "Middle Earth"

SOURCE_FILE = SAVES_DIR / "Middle Eearth.sav"
TARGET_FILE = SAVES_DIR / "Middle Earth.sav"


def read_u32_le(data, off):
    return struct.unpack_from("<I", data, off)[0]


def write_u32_le(data, off, value):
    struct.pack_into("<I", data, off, value)


def find_chunk_offsets_containing(data, positions):
    """
    Find ancestor chunks whose body contains any of the target positions.
    Uses a strict whitelist of known SPUD chunk tags to avoid false positives
    from byte-walking random data as chunks.

    Returns dict: chunk_header_offset -> count of positions contained.
    """
    # Known SPUD container chunk tags — only these are considered real chunks
    VALID_TAGS = {
        b"SAVE", b"INFO", b"CINF", b"META", b"SHOT",
        b"CLST", b"CDEF", b"CNIX", b"PNIX", b"VERS",
        b"NOBJ", b"SPWN", b"KILL", b"LVLS", b"LEVL",
        b"GLOB", b"GOBS", b"LATS", b"SATS", b"DATS",
        b"PDEF", b"PROP", b"CUST", b"CORA",
    }
    # Chunks we should recurse INTO (containers). NOBJ is tricky: its body has
    # fixed fields before sub-chunks, so byte-walk doesn't work inside NOBJ.
    RECURSE_TAGS = {
        b"SAVE", b"INFO", b"CINF", b"CLST", b"CLSD", b"GLOB", b"GOBS",
        b"LVLS", b"LEVL", b"LATS", b"SATS", b"DATS", b"META",
    }

    chunk_counts = {}  # header_off -> positions contained count

    def recurse(body_start, body_end):
        pos = body_start
        while pos + 8 <= body_end:
            tag = bytes(data[pos:pos+4])
            length = read_u32_le(data, pos + 4)
            child_body_start = pos + 8
            child_body_end = child_body_start + length

            # Strict validation: must be a known tag AND length must be plausible
            if tag not in VALID_TAGS or length < 0 or length > 100_000_000 or child_body_end > body_end:
                # Not a valid chunk — skip forward one byte
                pos += 1
                continue

            # Count how many target positions fall within this chunk's body
            contained = sum(1 for p in positions if child_body_start <= p < child_body_end)
            if contained > 0:
                chunk_counts[pos] = contained

            # Recurse only into true container tags AND only if the container
            # holds target positions
            if contained > 0 and tag in RECURSE_TAGS:
                recurse(child_body_start, child_body_end)

            pos = child_body_end

    # SAVE is at offset 0
    save_length = read_u32_le(data, 4)
    save_body_start = 8
    save_body_end = save_body_start + save_length

    # SAVE itself
    contained = sum(1 for p in positions if save_body_start <= p < save_body_end)
    if contained > 0:
        chunk_counts[0] = contained
    recurse(save_body_start, save_body_end)

    return chunk_counts


def main():
    if not SOURCE_FILE.exists():
        print(f"ERROR: source not found: {SOURCE_FILE}")
        return

    print(f"Reading: {SOURCE_FILE}")
    data = bytearray(SOURCE_FILE.read_bytes())
    print(f"  size: {len(data):,} B")

    # Find all length-prefixed FString occurrences of OLD_NAME
    old_fstring = struct.pack("<I", len(OLD_NAME) + 1) + OLD_NAME.encode("ascii") + b"\x00"
    new_fstring = struct.pack("<I", len(NEW_NAME) + 1) + NEW_NAME.encode("ascii") + b"\x00"
    delta_per = len(new_fstring) - len(old_fstring)
    print(f"  Old FString: {len(old_fstring)} B")
    print(f"  New FString: {len(new_fstring)} B")
    print(f"  Delta per occurrence: {delta_per}")

    positions = []
    i = 0
    while True:
        i = bytes(data).find(old_fstring, i)
        if i == -1:
            break
        positions.append(i)
        i += 1

    print(f"  Occurrences of length-prefixed FString: {len(positions)}")
    for p in positions:
        print(f"    @ 0x{p:x}")

    if not positions:
        print("Nothing to rename. Exiting.")
        return

    # Find containing chunks for each occurrence
    string_start_positions = [p + 4 for p in positions]  # position of the actual string bytes inside the FString
    chunk_counts = find_chunk_offsets_containing(bytes(data), string_start_positions)
    print(f"\nChunks containing one or more occurrences: {len(chunk_counts)}")
    for hdr_off, count in sorted(chunk_counts.items()):
        tag = bytes(data[hdr_off:hdr_off+4]).decode("ascii", errors="replace")
        length = read_u32_le(bytes(data), hdr_off + 4)
        print(f"  {tag:6s} @ 0x{hdr_off:06x}  length={length:,}  contains={count} occurrences")

    total_delta = len(positions) * delta_per
    print(f"\nTotal file size delta: {total_delta} B")

    # Build the new file
    # Strategy:
    # 1. Replace each FString occurrence (in sorted order, tracking cumulative offset shift)
    # 2. After replacement, update each containing chunk's length field by (count * delta_per)
    #    The chunk's header offset shifts by the cumulative deltas of occurrences BEFORE it.
    #    The length field is updated to old_length + (count * delta_per).

    # Sort occurrences by position
    positions_sorted = sorted(positions)

    # Build new data by concatenation
    out = bytearray()
    last_end = 0
    for pos in positions_sorted:
        out.extend(data[last_end:pos])
        out.extend(new_fstring)
        last_end = pos + len(old_fstring)
    out.extend(data[last_end:])
    print(f"New data size: {len(out):,} B (was {len(data):,})")

    # Now fix up chunk lengths.
    # For each containing chunk: find its NEW header offset in `out` and update the length.
    # The new header offset = old header offset + cumulative shift for all occurrences before it.
    def cumulative_shift(old_offset):
        """How much does an old offset shift in the new data?"""
        shift = 0
        for p in positions_sorted:
            if p < old_offset:
                shift += delta_per
        return shift

    print(f"\nUpdating chunk length headers:")
    for hdr_off, count in sorted(chunk_counts.items()):
        old_length = read_u32_le(bytes(data), hdr_off + 4)
        new_length = old_length + count * delta_per
        new_hdr_off = hdr_off + cumulative_shift(hdr_off)
        # Verify tag matches
        tag_in_new = bytes(out[new_hdr_off:new_hdr_off+4]).decode("ascii", errors="replace")
        tag_in_old = bytes(data[hdr_off:hdr_off+4]).decode("ascii", errors="replace")
        if tag_in_new != tag_in_old:
            print(f"  ⚠️ Tag mismatch at new offset 0x{new_hdr_off:x}: expected {tag_in_old} got {tag_in_new}")
            continue
        write_u32_le(out, new_hdr_off + 4, new_length)
        print(f"  {tag_in_old:6s} old 0x{hdr_off:x} → new 0x{new_hdr_off:x}  length: {old_length:,} → {new_length:,}")

    # Backup source
    import datetime
    backup = SOURCE_FILE.parent / f"{SOURCE_FILE.name}.before_rename_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(SOURCE_FILE, backup)
    print(f"\nBacked up source: {backup.name}")

    # Write new file with new filename
    TARGET_FILE.write_bytes(bytes(out))
    print(f"Wrote: {TARGET_FILE}")
    print(f"  final size: {TARGET_FILE.stat().st_size:,} B")

    # Delete the old file
    SOURCE_FILE.unlink()
    print(f"Deleted old file: {SOURCE_FILE}")

    # Also delete the game's autosave backup for the old name if it exists
    old_backup = SAVES_DIR / "Middle Eearth.sav.backup"
    if old_backup.exists():
        old_backup.unlink()
        print(f"Deleted stale game backup: {old_backup.name}")

    # Clear SpudCache
    if SPUD_CACHE.exists():
        SPUD_CACHE.unlink()
        print(f"Cleared SpudCache: {SPUD_CACHE}")

    # Verify
    print(f"\n=== Verification ===")
    # Re-parse with WorldSave
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from parser import WorldSave
    w = WorldSave(str(TARGET_FILE))
    w.load()
    pieces = w.get_placed_pieces()
    print(f"Pieces detected: {len(pieces)}")

    # Confirm the new name is in the file
    with open(TARGET_FILE, "rb") as f:
        check_data = f.read()
    print(f"'Middle Earth' length-prefixed form present: {check_data.count(new_fstring)}")
    print(f"'Middle Eearth' length-prefixed form present: {check_data.count(old_fstring)} (should be 0)")


if __name__ == "__main__":
    main()
