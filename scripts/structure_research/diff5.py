#!/usr/bin/env python3
"""
Parse the two new SPWN records as float arrays. Find the position bytes.
"""
import struct
from pathlib import Path

HERE = Path(__file__).parent

# The two new SPWN bodies from diff4 output (590 bytes each)
B_RECORD_HEX = """
12 00 00 00 cc 28 2c a7 17 b8 14 4e a2 e8 4b 24
7c 9f b6 00 38 c8 7b e8 7e 28 c1 40 46 90 ef c6
0f 94 06 41 72 92 74 c9 49 f8 a2 c0 5c 13 39 8f
63 8e c1 40 fc f8 c2 b3 6b 9a 06 41 9c 4d 32 23
2a cd a1 c0 01 0a 02 00 00 f9 03 00 00 02 00 00
00 13 00 00 00 14 00 00 00 43 4f 52 41 9f 00 00
00 9b 00 00 00 01 00 00 26 a5 40 3a 38 2c c0 bf
8b 72 72 ec af 85 d3 bf 8b b5 ec f2 54 36 d7 bf
10 43 a5 d5 02 e3 eb 3f cf 7a 85 f9 ce 60 c1 40
20 ef ad 21 e7 96 06 41 7b 7a 1e 8c 2a 6e a2 c0
00 00 00 00 00 00 f0 3f 00 00 00 00 00 00 f0 3f
00 00 00 00 00 00 f0 3f 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
5e 3e f9 ce 22 9c 46 c0 54 cf c8 59 d2 ae b3 bf
50 52 4f 50 46 01 00 00 1e 00 00 00 00 00 00 00
0c 00 00 00 20 00 00 00 2c 00 00 00 2d 00 00 00
2f 00 00 00 3f 00 00 00 57 00 00 00 6f 00 00 00
78 00 00 00 7c 00 00 00 80 00 00 00 82 00 00 00
92 00 00 00 96 00 00 00 9a 00 00 00 9c 00 00 00
9d 00 00 00 a1 00 00 00 a3 00 00 00 a4 00 00 00
ac 00 00 00 b0 00 00 00 b1 00 00 00 b3 00 00 00
b5 00 00 00 b9 00 00 00 bd 00 00 00 c1 00 00 00
c5 00 00 00 c6 00 00 00 13 00 00 00 00 00 00 00
00 00 00 00 14 00 00 00 01 00 00 00 00 00 00 00
04 00 00 00 00 00 00 00 13 00 00 00 00 00 00 00
00 00 00 00 01 01 00 5f 74 2f 91 1c 96 6c 47 82
3d 32 a4 a4 c9 e3 5a 5d 28 29 7d e2 e9 bf 40 46
fe 5c fd a4 ad 06 41 a2 2c 58 9f e3 1f a9 c0 00
00 00 00 00 00 00 00 b5 50 3a 36 99 3d 57 c0 00
00 00 00 00 00 00 00 05 00 00 00 4e 6f 6e 65 00
00 00 80 bf 00 00 80 bf 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 80 bf 00 00
80 bf 00 00 00 01 00 00 00 06 00 01 00 e0 34 95
64 00 00 00 00 00 80 bf 00 02 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 01
"""

C_RECORD_HEX = """
12 00 00 00 8c 3e d9 4b cf ee 06 4d 94 b1 08 7a
80 5c 7e 36 09 b3 a7 cd df 35 c3 40 f2 ab d4 a0
b9 1d 07 41 0c db 9e 6c 47 ad a8 c0 99 7b d3 77
de 98 c3 40 68 92 f7 b8 cf 21 07 41 0c db c6 16
c1 d8 a7 c0 01 0a 02 00 00 f9 03 00 00 02 00 00
00 13 00 00 00 14 00 00 00 43 4f 52 41 9f 00 00
00 9b 00 00 00 01 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 80 99 38 62 46 1d e3 e8 3f
7c 99 bc 54 8a 1d e4 3f ed e0 92 61 d8 64 c3 40
d3 40 93 24 81 20 07 41 0c db c6 16 c1 6e a8 c0
00 00 00 00 00 00 f0 3f 00 00 00 00 00 00 f0 3f
00 00 00 00 00 00 f0 3f 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
5d 35 0f 38 bd 86 59 40 00 00 00 00 00 00 00 00
50 52 4f 50 46 01 00 00 1e 00 00 00 00 00 00 00
0c 00 00 00 20 00 00 00 2c 00 00 00 2d 00 00 00
2f 00 00 00 3f 00 00 00 57 00 00 00 6f 00 00 00
78 00 00 00 7c 00 00 00 80 00 00 00 82 00 00 00
92 00 00 00 96 00 00 00 9a 00 00 00 9c 00 00 00
9d 00 00 00 a1 00 00 00 a3 00 00 00 a4 00 00 00
ac 00 00 00 b0 00 00 00 b1 00 00 00 b3 00 00 00
b5 00 00 00 b9 00 00 00 bd 00 00 00 c1 00 00 00
c5 00 00 00 c6 00 00 00 13 00 00 00 00 00 00 00
00 00 00 00 14 00 00 00 01 00 00 00 00 00 00 00
04 00 00 00 00 00 00 00 13 00 00 00 00 00 00 00
00 00 00 00 01 01 00 02 e6 46 a6 bf cb 32 48 88
64 43 dd bc b5 01 f5 ed e0 92 61 d8 64 c3 40 d3
40 93 24 81 20 07 41 0c db 86 6e fd 94 a8 c0 00
00 00 00 00 00 00 00 57 35 0f 38 bd 86 59 40 00
00 00 00 00 00 00 00 05 00 00 00 4e 6f 6e 65 00
00 00 80 bf 00 00 80 bf 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 80 bf 00 00
80 bf 00 00 00 01 00 00 00 06 00 01 00 e0 34 95
64 00 00 00 00 00 80 bf 00 02 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 01
"""

def hex_to_bytes(s):
    return bytes(int(x, 16) for x in s.split())

def main():
    B = hex_to_bytes(B_RECORD_HEX)
    C = hex_to_bytes(C_RECORD_HEX)
    print(f"B record: {len(B)} bytes")
    print(f"C record: {len(C)} bytes")

    # Find every byte position where they differ
    diffs = [(i, B[i], C[i]) for i in range(min(len(B), len(C))) if B[i] != C[i]]
    print(f"\n{len(diffs)} differing bytes")

    # Group consecutive diffs into runs
    runs = []
    cur_start = None
    cur_end = None
    for i, _, _ in diffs:
        if cur_start is None:
            cur_start = cur_end = i
        elif i == cur_end + 1:
            cur_end = i
        else:
            runs.append((cur_start, cur_end))
            cur_start = cur_end = i
    if cur_start is not None:
        runs.append((cur_start, cur_end))

    print(f"\n{len(runs)} contiguous diff runs:")
    for start, end in runs:
        length = end - start + 1
        b_slice = B[start:end+1]
        c_slice = C[start:end+1]
        print(f"\n  offset 0x{start:03x}-0x{end:03x}  ({length} bytes)")
        print(f"    B: {b_slice.hex(' ')}")
        print(f"    C: {c_slice.hex(' ')}")

        # Try to interpret as floats if length is multiple of 4
        if length % 4 == 0:
            n_floats = length // 4
            try:
                b_floats = struct.unpack(f"<{n_floats}f", b_slice)
                c_floats = struct.unpack(f"<{n_floats}f", c_slice)
                print(f"    B floats: {[f'{f:>14.4f}' for f in b_floats]}")
                print(f"    C floats: {[f'{f:>14.4f}' for f in c_floats]}")
                deltas = [c - b for b, c in zip(b_floats, c_floats)]
                print(f"    Δ:        {[f'{d:>14.4f}' for d in deltas]}")
            except struct.error:
                pass

        # Also try as doubles if length is multiple of 8
        if length % 8 == 0 and length >= 8:
            n_doubles = length // 8
            try:
                b_doubles = struct.unpack(f"<{n_doubles}d", b_slice)
                c_doubles = struct.unpack(f"<{n_doubles}d", c_slice)
                print(f"    B doubles: {[f'{d:>14.4f}' for d in b_doubles]}")
                print(f"    C doubles: {[f'{d:>14.4f}' for d in c_doubles]}")
            except struct.error:
                pass

if __name__ == "__main__":
    main()
