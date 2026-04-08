# RuneScape: Dragonwilds World Save Format — Developer Guide

A practical reference for developers who want to read, analyze, or modify Dragonwilds **world save** (`.sav`) files — specifically the binary world state files in `SaveGames/`, not the character JSON files.

**Scope of this guide:** binary `.sav` world editing. Character JSON editing (stats, inventory, quests) is much simpler and already well-documented elsewhere. This document focuses on the *hard* part: the undocumented chunked binary format for the world state, including placed structures, world actors, and global game state.

All information here is based on **dominion-live 189399** through **189251** (game versions from April 2026). Format may change in future updates.

**⚠️ Always back up save files before modifying. Never edit a save while the game is running. No warranties.**

---

## Table of Contents

1. [Save System Overview](#save-system-overview)
2. [File Layout and Chunk Format](#file-layout-and-chunk-format)
3. [Full Chunk Tag Reference](#full-chunk-tag-reference)
4. [World Identity](#world-identity)
5. [Level Data Structure](#level-data-structure)
6. [Named Objects (NOBJ)](#named-objects-nobj)
7. [Spawned Actors (SPWN)](#spawned-actors-spwn)
8. [GlobalBuildingManager — The Building State Container](#globalbuildingmanager--the-building-state-container)
9. [Pces Chunk — Building Piece Placements](#pces-chunk--building-piece-placements)
10. [The SpudCache Folder](#the-spudcache-folder)
11. [Empirical Format Quirks](#empirical-format-quirks)
12. [Safe Edit Operations](#safe-edit-operations)
13. [Risky Operations and Known Gotchas](#risky-operations-and-known-gotchas)
14. [Working Transplant Recipe](#working-transplant-recipe)
15. [Two Categories of Placed Structure](#two-categories-of-placed-structure)
16. [Reference Implementation](#reference-implementation)

---

## Save System Overview

Dragonwilds uses the **SPUD** (Steve's Persistent Unreal Data) plugin for save serialization, a publicly available open-source library for Unreal Engine 5 persistence:

- **Source:** https://github.com/sinbad/SPUD
- **Key files:** `Source/SPUD/Public/SpudData.h` (chunk format), `doc/tech.md`, `doc/props.md`, `doc/faq.md`, `doc/levelstreaming.md`

**Start there.** SPUD's source defines most of the chunk format. This guide documents Dragonwilds-specific additions and empirical quirks that differ from stock SPUD.

### Relevant file locations (Windows)

```
%LOCALAPPDATA%\RSDragonwilds\Saved\
├── SaveGames\                   ← World .sav files (this guide's focus)
│   ├── <WorldName>.sav          ← binary SPUD format
│   ├── <WorldName>.sav.backup   ← Game's auto-backup (from previous session)
│   └── <WorldName>.sav.<N>.verbackup   ← Versioned backups (keep a few)
├── SpudCache\                   ← Runtime streaming cache — important for editing
│   ├── L_World.lvl              ← Master level cache (main persistent map)
│   └── RSACell12800_X<x>_Y<y>.lvl   ← Per-cell streamed data (128m × 128m cells)
└── Logs\
    ├── RSDragonwilds.log        ← Current session log (check for load errors)
    └── RSDragonwilds-backup-*.log   ← Previous sessions
```

**Character data** (stats, inventory, quests) lives separately in `SaveCharacters/<name>.json` as plain JSON — straightforward to edit and not covered here. **World state** (placed buildings, chests, time of day, weather, difficulty settings) lives in `SaveGames/<world>.sav` as binary SPUD. That's what this guide is about.

---

## File Layout and Chunk Format

Every `.sav` file is a tree of IFF-style chunks. Each chunk has:

```
struct Chunk {
    char  Tag[4];     // 4-byte ASCII identifier (e.g., "SAVE", "INFO", "LVLS")
    uint32 Length;    // Body length in bytes (little-endian)
    byte  Body[Length];
}
```

Chunks can be nested — a chunk's body may contain child chunks. Top-level is always `SAVE`:

```
SAVE
├── INFO              ← Save metadata (description, timestamp)
│   └── CINF          ← Custom per-save info (WorldName, WorldSaveGuid, difficulty)
├── GLOB              ← Global game state
│   ├── META          ← Class metadata for global objects
│   └── GOBS          ← Global object list
│       └── NOBJ...   ← Named global objects (e.g., GameInstance state)
└── LVLS              ← Level data map
    ├── LEVL          ← Level "L_World" (the persistent main world)
    │   ├── <name FString>         ← e.g. "L_World"
    │   ├── <8-byte version header>  ← 0a 02 00 00 f9 03 00 00
    │   ├── META      ← Level's class metadata (CNIX, PNIX, CLST, CDEF)
    │   ├── LATS      ← Level actor list (NOBJ records for placed actors)
    │   │   └── NOBJ × N   ← Placed actors including GlobalBuildingManager
    │   ├── SATS      ← Spawned actor list (runtime-spawned actors)
    │   │   └── SPWN × N   ← Spawned actors (chests, mobs, etc.)
    │   └── DATS      ← Destroyed actor list
    └── LEVL × N      ← Streaming cell levels "RSACell12800_X*_Y*"
        └── (same structure)
```

### Reading a chunk

```python
import struct

def read_chunk_header(data, offset):
    tag = data[offset:offset+4]
    length = struct.unpack_from("<I", data, offset + 4)[0]
    body_start = offset + 8
    body_end = body_start + length
    return tag, length, body_start, body_end
```

### UE FString serialization

Strings are length-prefixed with a signed int32:

```python
def read_fstring(data, offset):
    length = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if length == 0:
        return "", offset
    if length > 0:
        # ANSI (ASCII), length includes null terminator
        raw = data[offset:offset + length - 1]
        return raw.decode("ascii"), offset + length
    else:
        # UTF-16LE, -length includes null terminator
        n = -length
        raw = data[offset:offset + (n - 1) * 2]
        return raw.decode("utf-16-le"), offset + n * 2
```

---

## Full Chunk Tag Reference

From SPUD's `SpudData.h`:

| Tag  | Meaning                | Notes |
|------|------------------------|-------|
| `SAVE` | Top-level savegame   | Always at offset 0 |
| `INFO` | Save info            | Contains file metadata |
| `SHOT` | Screenshot           | PNG data (if present) |
| `CINF` | Custom info          | WorldName, WorldSaveGuid, difficulty tags |
| `META` | Class metadata       | Per-level CNIX/CLST/CDEF/PNIX |
| `CLST` | Class definition list | Array of FSpudClassDef |
| `CDEF` | Class definition     | Single class with property layout |
| `CNIX` | Class name index     | Deduplicated class name string table |
| `PNIX` | Property name index  | Deduplicated property name string table |
| `VERS` | Version info         | |
| `NOBJ` | Named object         | Persistent actor/object with FString name |
| `SPWN` | Spawned actor        | Runtime-spawned actor with FGuid |
| `KILL` | Destroyed actor      | |
| `LVLS` | Level data map       | Contains LEVL chunks |
| `LEVL` | Level data           | Self-contained level segment |
| `GLOB` | Global data          | |
| `GOBS` | Global object list   | |
| `LATS` | Level actor list     | Contains NOBJ records |
| `SATS` | Spawned actor list   | Contains SPWN records |
| `DATS` | Destroyed actor list | |
| `PDEF` | Property definition  | |
| `PROP` | Property data        | Serialized UPROPERTYs |
| `CUST` | Custom data          | Game-defined blob inside an object |
| `CORA` | Core actor data      | Transform + core state per actor |

### Dragonwilds-custom (not in SPUD)

| Tag   | Meaning             | Notes |
|-------|---------------------|-------|
| `Pces` | Building pieces    | Placed structure list (walls, floors, etc.) |
| `Cmpl` | (unclear)          | Seen alongside Pces, possibly "complement" or reference list |

**Important:** `Pces` is **not a SPUD primitive**. It's a Dragonwilds-specific chunk that lives *inside* a SPUD `CUST` chunk inside the `GlobalBuildingManager` NOBJ. See [Pces Chunk](#pces-chunk--building-piece-placements).

---

## World Identity

A world save's identity is defined by **four** fields that must all be consistent:

1. **Filename** — the `.sav` file's name, e.g., `MyWorld.sav`
2. **`WorldName`** — FString inside the `CINF` chunk. Must match filename (minus extension) for the game to display it in the world list.
3. **`WorldSlotName`** — FString in `CINF`, usually same as `WorldName`.
4. **`WorldSaveGuid`** — 16-byte GUID stored as 4 × uint32 fields (`GUID_A` through `GUID_D`) in `CINF`. **Must be unique across all save files** or the game deduplicates and hides one.

### CINF chunk layout

The `CINF` chunk body is a list of **named properties** with a shared offset table, similar to UE custom info structures. Field order:

```
VERSION    (uint32)
GUID_A     (uint32)   ← first 4 bytes of WorldSaveGuid
GUID_B     (uint32)
GUID_C     (uint32)
GUID_D     (uint32)
WorldName       (FString)
WorldMapName    (FString)  ← always "L_World" in vanilla
FriendlyFire    (bool)
SurvivalDifficulty  (byte or uint32 enum)
HardcoreState   (byte)
CustomDifficultySettings  (complex — nested tags)
TimeOfSave      (string datetime)
SessionPrivacy  (enum)
SessionPasswd   (FString, usually empty)
WorldOwnerId    (FString — character ID)
WorldNameOwner  (FString — character display name)
LastSavedBy     (FString — build version)
Meta_SaveFileRevision  (uint32)
```

### Cloning a world

To create a new playable copy of an existing world:

1. Copy the `.sav` file to a new filename
2. Rewrite the `WorldName` and `WorldSlotName` FStrings to match the new filename
3. **Generate a new random UUID for `WorldSaveGuid`** and replace all 2 occurrences of the old GUID bytes with the new ones
4. Clear `SpudCache/L_World.lvl` (and any `RSACell*.lvl` files)

Skipping step 3 causes GUID collision — the game dedupes by GUID and hides one of the worlds.

---

## Level Data Structure

The `LVLS` chunk contains one or more `LEVL` chunks. Each `LEVL` is self-contained and represents a map or streaming cell.

Every `LEVL` body has this layout:

```
FString Name            (length-prefixed, e.g., "L_World")
8 bytes                  ← version header (two uint32 constants: 522 and 1017)
                           empirically: 0a 02 00 00 f9 03 00 00
META chunk              ← class metadata for this level
LATS chunk              ← level-placed actors
SATS chunk              ← runtime-spawned actors
DATS chunk              ← destroyed actors
```

**Critical empirical quirk:** after the FString name, there's an **undocumented 8-byte header** before the first sub-chunk. These 8 bytes contain two constant uint32s (`0x20a = 522` and `0x3f9 = 1017`). They appear to be SPUD system/user version markers that the SPUD header files don't document explicitly.

**Do not skip these 8 bytes.** A walker that goes straight from the FString name to the next chunk will misparse.

### L_World vs streaming cells

- **`L_World`** — the main persistent world. Contains the `GlobalBuildingManager` NOBJ and the Pces chunk with all player-built structures.
- **`RSACell12800_X<x>_Y<y>`** — per-cell streaming chunks for 128m × 128m grid regions. Contain environment state that's only loaded when the player is nearby.

**Player-built structures live in `L_World`, not in the cell chunks.** Cell chunks contain ore nodes, NPCs, rune essence, and other procedural world content.

---

## Named Objects (NOBJ)

NOBJ records represent level-placed persistent actors. Each NOBJ contains:

```
uint32 ClassID          ← index into the level's CNIX (class name index)
FString Name            ← unique per-level identifier (e.g., "BP_OreNode_Stone_C_UAID_ABC123..._456")
12 bytes                ← metadata (3 × uint32 — unknown precise meaning)
8 bytes                 ← version header (same as LEVL)
CORA chunk              ← core actor data (transform, etc.)
PROP chunk              ← SaveGame properties
CUST chunk              ← optional custom data blob
```

**Empirical quirk:** `ClassID` is at the **start** of the NOBJ body, not the end as the SPUD C++ header suggests. Field order in the serialized format doesn't always match declaration order in the C++ structs.

### Named actor identity format

Dragonwilds uses UE's standard `UAID_` format for actor names:
```
BP_<ClassName>_C_UAID_<hex>_<sequence>
```
Examples:
- `BP_OreNode_Stone_C_UAID_00BE4395530E87CE01_1931348542`
- `BP_NPC_Zanik_C_UAID_CC96E517328E5CF801_1686492240`
- `GlobalBuildingManager_UAID_CC96E50CA869C0EC01_1097795184`

The `UAID_` suffix is stable across saves (it's a persistent stable identifier). Transplanting a NOBJ with a UAID from one world to another is safe as long as no conflict exists.

---

## Spawned Actors (SPWN)

SPWN records represent runtime-spawned actors (e.g., chests the player built, mobs, temporary spawns). Structure is similar to NOBJ but uses an FGuid instead of an FString name:

```
uint32 (record version/marker)
16 bytes FGuid          ← unique per-instance GUID
... transform + component refs ...
CORA/PROP sub-chunks
```

Each chest/interactive actor placed by the player creates a SPWN record. **A SPWN record is separate from a Pces placement record** — both must exist for a chest to function. See [Two Categories of Placed Structure](#two-categories-of-placed-structure).

---

## GlobalBuildingManager — The Building State Container

All player-built **passive structures** (walls, tiles, roofs, doors) are stored inside a single NOBJ in `L_World`'s LATS chunk, named `GlobalBuildingManager_UAID_CC96E50CA869C0EC01_1097795184` (the `UAID` is a stable identifier — same across all Dragonwilds worlds of a given game version).

### Layout of the GlobalBuildingManager NOBJ body

```
uint32 ClassID = 13
FString Name                          ← "GlobalBuildingManager_UAID_..."
12 bytes metadata
8 bytes version header                ← 0a 02 00 00 f9 03 00 00
CORA sub-chunk (159 B)                ← manager's transform (mostly zeros)
PROP sub-chunk (53 B)                 ← 4 counter properties for the manager
  int32 offsets_count = 4
  4 × uint32 offsets [0, 12, 24, 28]
  int32 data_count = 29
  29 bytes property data:
    prop[0]: 12 bytes (int64 config value = 14)
    prop[1]: 12 bytes (int64 config value = 15)
    prop[2]: 4 bytes (uint32 counter)  ← THIS IS CRITICAL
    prop[3]: 1 byte (bool = true)
CUST sub-chunk (variable size)        ← wraps the Pces chunk
  int32 tarray_count
  byte prefix (= 0)                   ← one byte before Pces starts (purpose unclear)
  Pces chunk                          ← all placed piece records
```

### The PROP[2] counter (critical)

**`prop[2]` is a uint32 counter that must be kept in sync** with the number of placed pieces or the game may silently reject pieces on load. Observed values:
- Empty world with 1 placed piece: counter = 1
- World with ~45 placed pieces: counter = 50
- World with a single placed piece that was later duped: counter = 1 (game tolerated)

**Exact semantics unclear** — could be next-ID-to-assign, total-placed-count, or max-ID-seen. Empirically, setting it to `max(target_counter, source_counter)` when transplanting pieces allows the game to accept the imported pieces. Setting it too low causes pieces to be rejected.

When adding pieces via save editing: update `prop[2]` to at least match the count required by your new pieces.

---

## Pces Chunk — Building Piece Placements

Inside `GlobalBuildingManager`'s `CUST` chunk, the actual building piece data lives in a **Dragonwilds-custom chunk tagged `Pces`**. This is not a SPUD primitive; SPUD stores it as opaque custom data, and Dragonwilds parses it internally.

### Pces body format

A simple array of piece records, each with this layout:

```
uint32 persistent_id        ← per-piece ID (globally unique per world, may have gaps)
FString class_guid          ← length-prefixed base64 GUID string, always 23 bytes (22 chars + null)
double position_x           ← UE world coordinates in centimeters
double position_y
double position_z
float  rotation_yaw_deg     ← rotation around Z axis, 0–360 degrees
float  extra_b              ← per-class meaning; for walls often "length in cm" (e.g., 965, 1565)
float  extra_c              ← usually 1.0 (scale?)
uint32 ref_count            ← number of reference/anchor GUIDs that follow (1–5 typically)
FString refs[ref_count]     ← each is a 23-byte length-prefixed base64 GUID string
uint32 flags_a = 1          ← always 1 in observed records (purpose unclear)
uint32 flags_b = 1          ← always 1
uint8  flag_byte            ← 0 for "no slot data", 1 for "has slot data"
if flag_byte == 1:
    uint32 slot_count
    uint32 slots[slot_count]   ← connection point indices for this piece
uint8  terminator           ← usually 0 (optional, may be absent for some records)
```

### Class GUIDs are persistent

The `class_guid` field is a **23-byte length-prefixed base64 string** that identifies the piece class. These GUIDs are **stable across game installations and saves**:

| GUID (base64) | Display | Notes |
|---|---|---|
| `SEZxX0vWAzlYYDGkwphIsw` | Personal Chest | small chest |
| `PzsvXL09Q0KYg23WaYfRcg` | Ash Chest | larger storage chest |
| `4AfTREj9KmVBOF-HvMtqhw` | Cabin Wall | standard wall |
| `L9AIt0ZB6Q7GHPyDVM96iw` | Cabin Wall with Doorframe | |
| `ra70cEh9cDOb_leFJwQE2Q` | Square Floor Tile | cabin tile |
| `segcy0CHL7BmMbSlaE83dg` | Roof Support Wall (cottage) | |
| `2UsmOEgQqigQFcGR4Btfkg`, `rbQt1kvlqxc5kAS6Eabung`, `ybcu1EaJdCYIDHeLGhyIeg` | Roof variants | |
| `2rxJ495rm0GDn4h5OWKiyQ` | (anchor reference) | appears as ref on most pieces, meaning unclear |

**The class GUIDs are NOT world-local** — they're the same in every Dragonwilds save. You can safely copy a piece record between worlds without re-resolving class GUIDs.

### Parsing strategy

Because of gaps in `persistent_id` and variable-length trailing slot data, a naive sequential walk with "next index must be current+1" will fail. Robust parsing strategies:

1. **Scan for FString-23 occurrences.** Every record begins with `\x17\x00\x00\x00` (length=23) followed by 23 bytes of a base64 GUID + null.
2. **Classify each FString as "main record" or "ref"** by checking whether the bytes immediately after it form a plausible position (3 doubles within reasonable world coordinates) followed by a small uint32 ref_count.
3. **For each main record, parse fields in order** until you reach the next main record start or the end of the Pces body.

See the reference implementation for working code.

---

## The SpudCache Folder

Dragonwilds uses SPUD's "level streaming" mode. When a world is loaded, SPUD splits the `.sav` into separate per-level cache files in `SpudCache/`. At save time, it concatenates everything back into a single `.sav` file.

**Consequences for save modding:**

1. **When editing a `.sav` externally, clear `SpudCache/` files first.** Otherwise SPUD may favor stale cached data over your edits, or cause the game to re-serialize in unexpected ways.
2. **Never edit `.sav` files while the game is running** — the game has an exclusive lock, and its own save will overwrite your changes on exit.
3. **SpudCache files are disposable.** They're rebuilt from the `.sav` at load time. Deleting them is always safe (assuming the game is not running).

Files to watch for:
- `SpudCache/L_World.lvl` — the main world's cached level data
- `SpudCache/RSACell12800_X<x>_Y<y>.lvl` — streaming cell caches (created as player travels)

---

## Empirical Format Quirks

These are findings that differ from or extend beyond what SPUD's source code documents.

### 1. LEVL body has an 8-byte version header after the name

After the FString level name in a LEVL body, there are 8 bytes of constant data (`0a 02 00 00 f9 03 00 00`) before the first sub-chunk. These represent system and user version markers. A sub-chunk walker must skip these 8 bytes.

### 2. NOBJ body has ClassID at the start

The `FSpudObjectData` struct in SPUD's `SpudData.h` lists `ClassID` as the last field, but in the serialized format it appears at the **start** of the NOBJ body (before the Name FString). Field serialization order doesn't match declaration order.

### 3. The `0a 02 00 00 f9 03 00 00` sequence is universal

This 8-byte constant appears at the start of most SPUD-serialized objects: LEVL bodies, NOBJ bodies, and inside Pces records at offset 0x44. It's a reliable structural marker for locating SPUD content anchors.

### 4. `Pces` is not a SPUD chunk

It's a Dragonwilds custom chunk stored inside a SPUD `CUST` container inside the `GlobalBuildingManager` NOBJ. Searching for `Pces` as a top-level chunk will find it because it happens to be nested deeply enough that standalone tag scans still work, but formally it's an internal game chunk.

### 5. Persistent IDs have gaps

Piece `persistent_id` values aren't strictly sequential. A world with 45 placed pieces may have IDs in the range 1–50+ with gaps (e.g., 13, 14, 16, 17, ..., 50). Gaps likely represent pieces that were deleted or replaced during construction.

### 6. GBM PROP[2] counter must stay synchronized

If you add pieces to Pces without updating the GBM's PROP[2] counter, the game may silently reject the new pieces on load. The counter likely represents "next persistent ID" or "total piece count". When transplanting, set it to `max(target_counter, source_counter)`.

### 7. Chunk length chain must be updated up the hierarchy

When inserting or removing bytes inside a chunk, **every containing chunk's length field must be updated**. For adding N bytes to a Pces record, update (in any order):
- Pces chunk length
- CUST TArray count (signed int32)
- CUST chunk length
- NOBJ chunk length
- LATS chunk length
- LEVL chunk length
- LVLS chunk length
- SAVE chunk length

Eight length fields in the chain. Miss one and the game may load but show corrupt state.

---

## Safe Edit Operations

These world-file operations have been tested and verified working in-game:

- **Weather changes** — edit the embedded weather JSON section (length-preserving: replace with same or shorter text padded with whitespace)
- **World event triggers** — enable/disable timed events via the world events JSON section
- **Container contents** — modify item counts, durability, and slot contents in chest/station JSON sections
- **World Mode conversion** (Standard ↔ Custom) — flip two bytes atomically: the `L_World+9` enum byte AND the first byte of the `CustomDifficultySettings` PROP field. **Both must be set together** or the game reverts on save.
- **Custom difficulty tag values** — target the tagless float array at `L_World+17` (the secondary copy the game reads at runtime), not the named TagName/NameProperty entries (which the game ignores for runtime values)
- **Cloning a world** — copy file + rename filename and internal WorldName + generate new `WorldSaveGuid`, see [World Identity](#world-identity)
- **Transplanting passive building pieces** (walls, tiles, roofs, doors) between worlds via Pces injection + PROP[2] counter update, see [Working Transplant Recipe](#working-transplant-recipe). **This only works for Category 1 structures** — see [Two Categories of Placed Structure](#two-categories-of-placed-structure).

---

## Risky Operations and Known Gotchas

### Ownership persistence
Every chest carries an **`OwnerCharacterGuid`** baked into its PROP data. Changing the world owner (e.g., via Standard→Custom conversion) can orphan existing chests — they still reference the old owner and may become unusable. Workaround: rewrite all `OwnerCharacterGuid` fields to match the new owner during conversion.

### Spatial collision
Transplanted pieces at positions that overlap pre-existing structures in the target world may cause the game to silently remove one or the other. **Pre-check for bounding-box overlap** before transplanting, or place transplants in empty regions of the target world.

### World-local class table indices
Some fields (like the first uint32 of an SPWN body and certain class references in PROP) use **indices into the world's local CNIX/CDEF tables**, which are different between worlds. Copying SPWN records verbatim between worlds will produce dangling indices. Always use cross-world-portable identifiers (base64 class GUIDs) for transplant operations.

### SpudCache shadowing
Editing a `.sav` while its corresponding `SpudCache/*.lvl` files are present can cause the game to load stale cached data instead of your edits. Always clear SpudCache after external edits.

### Game save cycle strips unknown data
When the game loads a modified save and then saves again, it may prune data it doesn't recognize. Modified files should either be loaded and tested, or treated as read-only and never loaded. Don't expect the game to preserve arbitrary additions across load-save cycles.

### Accumulated GLOB bloat
Old world saves (especially those edited with earlier tool versions) can have bloated GLOB chunks (25 KB+ for an "empty" world). This is usually harmless, but can slow the world list load. The game cleans this up on its next save cycle.

---

## Working Transplant Recipe

**Use case:** copy placed structures (walls, floors, roof) from Source world into Target world, preserving Target's existing state.

**Steps:**

1. **Verify preconditions:**
   - Game is not running
   - Target's SpudCache is empty (delete if present)
   - Source and Target are from the same game version

2. **Find both worlds' `GlobalBuildingManager` NOBJ:**
   - Walk SAVE → LVLS → L_World LEVL → LATS
   - Find the NOBJ whose Name contains `"GlobalBuildingManager"`
   - Record its chunk boundaries

3. **Locate the Pces chunk inside each GBM NOBJ's CUST sub-chunk:**
   - Walk NOBJ body: skip ClassID(4) + Name FString + 12B metadata + 8B version header
   - Find the CORA, PROP, CUST sub-chunks
   - Inside CUST: skip 4-byte TArray count + 1-byte prefix, then find the Pces chunk header

4. **Extract source's Pces body bytes** (everything between the Pces header and its end).

5. **Read target's Pces body and append source's body to it.**

6. **Update all containing chunk lengths in the target:**
   - Pces chunk length += delta
   - CUST TArray count += delta
   - CUST chunk length += delta
   - NOBJ chunk length += delta
   - LATS chunk length += delta
   - LEVL chunk length += delta
   - LVLS chunk length += delta
   - SAVE chunk length += delta

7. **Update the target's GBM PROP[2] counter** to at least `max(target_counter, source_counter)`.

8. **Write out the modified target file with auto-backup.**

9. **Clear SpudCache.**

10. **Launch game and load target world.** Travel to the transplanted pieces' coordinates (they're at the source world's coordinates — same for same-seed worlds).

### Validation

Before writing, verify:
- `SAVE length + 8 == len(new_file)` (SAVE header itself is 8 bytes)
- Walking top-level chunks inside SAVE lands exactly at SAVE's end (no overrun or under-run)
- GBM NOBJ reparses cleanly with the new size

---

## Two Categories of Placed Structure

Not all placed structures use the same storage model. The save format distinguishes two fundamentally different cases, and **transplanting Category 2 structures via Pces-only injection doesn't work**.

### Category 1: Passive building pieces
Walls, floors, roofs, doors, decorations, structural supports.

- **Storage:** single Pces record inside `GlobalBuildingManager.CUST.Pces`
- **Instantiation:** the game reads the Pces record, resolves the base64 class GUID via its global class registry (loaded from the `.pak`), and spawns the mesh at the position. No other data needed.
- **Transplant:** copy the Pces record bytes + update the PROP[2] counter. Works — verified in-game.
- **Verified examples from dominion-live 189399:**
  - Cabin Wall (`4AfTREj9KmVBOF-HvMtqhw`) — 143 bytes per record (ref_count=1)
  - Floor Tile (`ra70cEh9cDOb_leFJwQE2Q`) — 111 bytes per record (ref_count=1)
  - Roof Support variants — 4 classes, various sizes with ref_count=4

### Category 2: Interactive actors
Chests, furnaces, cooking pots, crafting stations, any actor with state/inventory/ownership.

- **Storage (two places):**
  - A Pces record inside `GlobalBuildingManager.CUST.Pces` — placement metadata (position, rotation, class)
  - **A separate SPWN record** inside `L_World.SATS` — the actor's runtime state (inventory linkage, owner, health, ghost flag, etc.)
- **Instantiation:** the game reads the Pces record to know "a chest should exist at position X", then looks up the matching SPWN record in SATS to get the actor's state. **Without the SPWN record, there's nothing to instantiate** — the Pces entry becomes an orphaned placement marker that the game silently ignores.
- **Transplant:** **Pces alone is NOT enough.** You must also copy the corresponding SPWN record and ensure it ends up in the target's `L_World.SATS` chunk. Each chest's state crosses BOTH chunks.

### Hard evidence for the Category 2 split

In a working DiffTest.sav with 3 placed chests, the personal chest at position `(8553.33, 185509.18, -3230.51)` has its **3-double position bytes appearing twice in the file**:

- **First occurrence at offset `0xb342`** — inside the Pces chunk at the position doubles of a Pces record
- **Second occurrence at offset `0xef3f`** — inside a 589-byte SPWN chunk at offset `0xeeab-0xf100` (inside `L_World.SATS`)

That's the same 24 bytes (3 doubles) appearing at two completely different locations in the file. The placement is in Pces, the actor state is in SPWN. Both must be transplanted to get a working chest.

### Observed Pces record sizes (dominion-live 189399)

| Class GUID | Type | Record size | Components (refs) |
|---|---|---|---|
| `SEZxX0vWAzlYYDGkwphIsw` | Personal Chest | ~185 B | 3 |
| `PzsvXL09Q0KYg23WaYfRcg` | Ash Chest | ~146 B | 2 |
| `4AfTREj9KmVBOF-HvMtqhw` | Cabin Wall | 143 B | 1 |
| `L9AIt0ZB6Q7GHPyDVM96iw` | Cabin Wall (doorframe) | ~143 B | 1 |
| `ra70cEh9cDOb_leFJwQE2Q` | Square Floor Tile | 111 B | 1 |
| `segcy0CHL7BmMbSlaE83dg` | Roof Support (cottage) | varies | 1 |
| `2UsmOEgQqigQFcGR4Btfkg`, `rbQt1kvlqxc5kAS6Eabung`, `ybcu1EaJdCYIDHeLGhyIeg` | Roof variants | varies | 4 (complex slot data) |

Record size depends on ref_count and the trailing slot/connection data. Records with more connections to other pieces have larger slot arrays.

### Concrete Pces record example: a Floor Tile (111 bytes)

Raw bytes from a real save file (a solo placed floor tile, pid=1):

```
0000  01 00 00 00                         ← persistent_id = 1
0004  17 00 00 00                         ← FString length = 23
0008  72 61 37 30 63 45 68 39 63 44 4f 62 5f 6c 65 46 4a 77 51 45 32 51 00
      "ra70cEh9cDOb_leFJwQE2Q\0"          ← class GUID (base64 string)
001f  c3 2e ce 0c d8 3d c8 40             ← position X double = 12411.6875
0027  4e ce 84 13 6c 88 06 41             ← position Y double = 184589.5078
002f  d7 4a 56 a6 34 6c a9 c0             ← position Z double = -3254.0945
0037  00 80 8e 43                         ← rotation_yaw float = 285.0
003b  00 40 71 44                         ← extra_b float = 965.0
003f  00 00 80 3f                         ← extra_c float = 1.0
0043  01 00 00 00                         ← ref_count = 1
0047  17 00 00 00                         ← FString length = 23
004b  32 72 78 4a 34 39 35 72 6d 30 47 44 6e 34 68 35 4f 57 4b 69 79 51 00
      "2rxJ495rm0GDn4h5OWKiyQ\0"          ← ref GUID (anchor? meaning unclear)
0062  01 00 00 00                         ← flag_a = 1
0066  01 00 00 00                         ← flag_b = 1
006a  01 00 00 00                         ← flag_c or slot_count = 1 (varies)
006e  00                                  ← terminator/trailing byte
```

For classes with more complex slot connection data (like cottage walls that connect to multiple anchors), the trailing section after `ref_count` is larger and includes additional uint32 slot index arrays.

**This is the key distinction when planning any transplant operation.**

---

## Reference Implementation

A working implementation of everything in this guide is in the [RSDragonWilds-WorldEditor](https://github.com/haithemobeidi/RSDragonWilds-WorldEditor) project:

- **`parser.py`** — Python classes `CharacterSave` and `WorldSave` with read/edit/save methods
- **`parser.py` → `WorldSave.get_placed_pieces()`** — Pces chunk parser (the production version)
- **`scripts/structure_research/`** — Reverse-engineering scripts and test corpus
  - **`surgical_transplant.py`** / **`surgical_transplant_v3.py`** — working cross-world transplant
  - **`rename_world.py`** — in-place world rename with chunk-length fixup
  - **`diff14.py`** — recursive LEVL/LATS/NOBJ walker with empirical quirk handling
  - **`A.sav`** through **`E_with_cabin.sav`** — test corpus of progressive save states for diff-based analysis

The test corpus is useful for anyone doing save format research: it's a series of same-world snapshots at successive build stages, so diffs between them isolate exactly which bytes correspond to which player action (placing a chest, building a cabin, etc.).

---

## Contributing

If you find additional fields, chunk types, or empirical behaviors not documented here, please contribute them back to the project. Format research benefits the whole modding community.

**Be honest about limitations.** Many fields in this format are still unknown or only partially understood. This guide represents what's been verified empirically. Things that are guesses are marked as such.

---

*Last updated: April 2026. Game version dominion-live 189399 through 189251.*
