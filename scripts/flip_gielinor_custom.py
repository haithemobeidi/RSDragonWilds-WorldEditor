#!/usr/bin/env python3
"""
Flip Gielinor.sav difficulty enum to 3 (Custom) so a char_type=3 character can join.

WORKAROUND for the persistence bug: the game's auto-save resets this enum to 0
on every save cycle. So this script must be run BEFORE each play session where
you want Gielinor to be a Custom world.

Usage:
    python scripts/flip_gielinor_custom.py [--revert]

After running, immediately launch the game and join Gielinor with your
char_type=3 character. The enum will revert to 0 when the game next saves,
which is fine — your play session will work because the game read the file
at load time.
"""
import argparse
import os
import shutil
import struct
import sys
from datetime import datetime

GIELINOR_PATH = os.path.expanduser(
    "~/AppData/Local/RSDragonwilds/Saved/SaveGames/Gielinor.sav"
)
# WSL path conversion
if not os.path.exists(GIELINOR_PATH):
    GIELINOR_PATH = "~/AppData/Local/RSDragonwilds/Saved/SaveGames/Gielinor.sav"

BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "research_backups",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Revert to standard (enum=0) instead of flipping to custom (enum=3)",
    )
    args = parser.parse_args()

    if not os.path.exists(GIELINOR_PATH):
        print(f"ERROR: Gielinor.sav not found at {GIELINOR_PATH}")
        sys.exit(1)

    # 2 backups always (standing rule)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = "REVERT" if args.revert else "FLIP_CUSTOM"
    for suffix in ("A", "B"):
        dest = os.path.join(BACKUP_DIR, f"Gielinor_PRE_{label}_{ts}_{suffix}.sav")
        shutil.copy(GIELINOR_PATH, dest)
    print(f"Backups: 2 created in {BACKUP_DIR}")

    # Read, find L_World, flip enum
    data = bytearray(open(GIELINOR_PATH, "rb").read())
    p = data.find(b"L_World\x00")
    if p == -1:
        print("ERROR: L_World marker not found in Gielinor.sav")
        sys.exit(1)

    enum_offset = p + 9
    old_enum = struct.unpack("<I", data[enum_offset : enum_offset + 4])[0]
    new_enum = 0 if args.revert else 3

    if old_enum == new_enum:
        print(f"Already at desired state: enum = {old_enum}")
        return

    data[enum_offset : enum_offset + 4] = struct.pack("<I", new_enum)
    with open(GIELINOR_PATH, "wb") as f:
        f.write(bytes(data))

    # Verify
    verify = struct.unpack(
        "<I",
        open(GIELINOR_PATH, "rb").read()[enum_offset : enum_offset + 4],
    )[0]
    print(f"\nGielinor difficulty enum: {old_enum} → {verify}")
    print(f"  L_World at 0x{p:x}, enum at 0x{enum_offset:x}")
    print(f"  File size: {len(data):,} bytes (unchanged)")

    if args.revert:
        print("\nGielinor is now STANDARD. char_type=0 characters can join.")
    else:
        print(
            "\nGielinor is now CUSTOM. Launch the game NOW and join with a "
            "char_type=3 character."
        )
        print("Note: the game will reset enum to 0 on next save — this is the "
              "known persistence issue. Your play session will still work.")


if __name__ == "__main__":
    main()
