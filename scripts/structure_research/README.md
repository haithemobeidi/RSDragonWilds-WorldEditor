# Structure Transplant Research

Test data and diff scripts for the "move placed structures between worlds"
feature. This directory exists to preserve the reverse-engineering experiment
that established the binary layout of placed-actor records.

## Test corpus

Three snapshots of the same world `DiffTest`, captured at three points in
time, with no other state changes between them:

- `A.sav` — empty world (no player-built structures, only environment props)
- `B.sav` — A + one Personal Chest placed in front of the church
- `C.sav` — B + one more Personal Chest placed next to the tent

Both chests are the **same exact class** (`BP_BaseBuilding_PersonalChest_C`),
both empty (no items inside).

## File sizes (informational)

| File | Bytes | Δ from previous |
|---|---|---|
| A | 201,105 | — |
| B | 202,805 | +1,700 |
| C | 203,588 | +783 |

The first chest added 1,700 bytes (record itself + a class added to `CNIX` +
related table growth). The second chest only added 783 bytes — close to the
size of one bare SPWN+PROP record — because the class was already in `CNIX`.

## Save format observations

The .sav file is a chunked UE-style binary with 4-byte ASCII tags:

- `SAVE` — top-level container
- `INFO` / `CINF` — file metadata (version, timestamps, world name)
- `GLOB` — globals
- `CNIX` — Class Name IndeX (deduplicated class name string table)
- `PNIX` — Property Name IndeX (deduplicated property name string table)
- `CDEF` / `CDVE` — Class Definition / Class Default Value Entry
- `LVLS` — Levels (the chunk that holds all per-level data including spawn lists)
- `SPWN` — Spawn record (one per placed actor — trees, rocks, AND player builds)
- `PROP` — Property block (per-actor property values, follows each SPWN)
- `CLST` — Class List
- `Pces` — Building pieces (player-built structural mesh placements)
- `SATS` — Spawn ATtribute Set (?)

Each chunk: 4-byte ASCII tag, 4-byte little-endian uint32 length, then `length`
bytes of body.

## SPWN record layout (Personal Chest, 590 bytes)

| Offset | Size | Field |
|---|---|---|
| 0x00 | 4 | record type / version (`12 00 00 00`) |
| 0x04 | 16 | per-instance actor GUID (unique per placed actor) |
| 0x14 | 48 | transform — 6 doubles (likely position vec3 + rotation/scale vec3) |
| 0x44 | 4-9 | class table reference (`01 0a 02 00 00 f9 03 00 00`) |
| 0x4d+ | … | SubObject IDs (e.g. `13 00 00 00 14 00 00 00`) |
| 0x59 | 4 | `CORA` chunk (Component Object Reference Array?) |
| 0x68-0x9e | ~56 | secondary float region (component-level transforms) |
| 0xa0-0xbf | 24 | three doubles set to 1.0 (`00 00 00 00 00 00 f0 3f` x3) — uniform scale? |
| 0xc0-0xef | 48 | zeros (reserved or unused for chests?) |
| 0xf0-0xff | 16 | two doubles — copy of one position component |
| 0x100 | 8 | inline `PROPF` start tag for the embedded property block |
| 0x100+ | … | property name table indices, then property values |
| 0x1b7-0x1ee | … | secondary GUID + position copy (component child transform) |
| 0x1ef | 8 | inline string `\x05\x00\x00\x00None\x00` — terminator |
| 0x1f7-end | … | trailing zeros + final state byte |

## Key findings (verified by diff)

1. The transform doubles at offset **0x0f0** and **0x1e7** changed predictably
   when the chest moved (-92.96 → 102.11 in B → C). These are real positions.
2. The bytes at offset **0x44-0x67** (class/component refs) are byte-identical
   between B and C — confirming they encode the actor *class*, not the
   instance, and any two same-class actors share that prefix.
3. The 16-byte instance GUID at offset 0x04 is regenerated per placed actor.
4. Player-built structures and environment props (trees, rocks) all live in
   the same `SPWN` chunk array. They're distinguished only by their class
   reference. The "filter to player builds" rule is: class name starts with
   `BP_BaseBuilding_`.

## Strings unique to a chest record (vs an empty world)

These appear in B but not A — the schema for a single Personal Chest:

```
/Game/Gameplay/BaseBuilding/Actors/Props/BP_BaseBuilding_PersonalChest.BP_BaseBuilding_PersonalChest_C
/Game/Gameplay/World/Components/BP_Components_WorldItemInventory.BP_Components_WorldItemInventory_C
/Script/Dominion.FurnitureBonusComponent
/Script/Dominion.HealthComponent
BuildingPieceID
OwnerCharacterGuid  ← THIS IS WHY BUG #001 HAPPENS — chests carry an explicit owner GUID
StabilityValue
bIsGhosted
FurnitureBonus
```

`OwnerCharacterGuid` is the smoking gun for Bug #001 (locked chests/totems
break on world conversion): when a world is converted from Standard to
Custom, the `WorldSaveSettings/PlayerOwnerGuid` changes, but every placed
chest still has its old `OwnerCharacterGuid` baked in — so the game no
longer recognizes the player as the owner. Fix: rewrite all chest
`OwnerCharacterGuid` fields to match the new world owner. (Out of scope for
this feature; logged for later.)

## Diff scripts

- `diff.py` — naive prefix/suffix diff (failed — too noisy because adding
  bytes reshuffles offset tables across the file)
- `diff2.py` — string-counter diff (revealed the chest schema strings)
- `diff3.py` — chunk-tag locator (mapped the file format)
- `diff4.py` — SPWN-record extractor and per-record diff (isolated the new
  records and confirmed they're the same length)
- `diff5.py` — float interpretation of the byte-level diff between the two
  chest records (confirmed position doubles at 0xf0 and 0x1e7)

Run any of them with `python3 diffN.py` from this directory.
