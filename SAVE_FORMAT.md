# RS Dragonwilds Save File Format - Reverse Engineering Notes

Reverse engineered from real save files. Game built on **Jagex Dominion Engine** (custom UE5 fork).

---

## TL;DR — What We Can vs Can't Edit

### ✅ EASY to edit (plain JSON in `SaveCharacters/*.json`)
- **Vitals**: Health, Stamina, Sustenance, Hydration, Toxicity, Endurance
- **Skills**: All 10 skills' XP (and thus levels)
- **Inventory**: item durability, stack count (`Count`), delete items
- **Loadout/Equipment**: durability, vital shield
- **Quest progress**: state (Not Started/In Progress/Completed), individual quest variable booleans/ints
- **Status effects**: Cold, Poison, Burning, Bleeding, Slow, WellRested, Cosiness, Wither (clear or set)
- **Player position** (`LastAccessibleLocation`) — string format `V(X=..., Y=..., Z=...)`
- **Hardcore mode** toggle
- **Mounts**: equipped mount, unlocked mounts list
- **Spell loadout** (48 slots)
- **Map pins** (custom waypoints)
- **Customization**: body type, hair, skin tone, eye color, etc. (DataTable row references)
- **Fog of war** (revealed regions bitmap)
- **Progress lists**: items picked up, recipes/buildings/spells unlocked, kill achievements, vendor reputations
- **Journal**: unlocked entries, unread flags
- **Playtime** (cosmetic — sim and wall clock)

### ✅ EDITABLE (embedded JSON inside `SaveGames/*.sav` binary)
- **89 world chests/storage** — full item contents (dupe items into chests!)
- **24 World Events** — base raids, ambushes (toggle triggers, modify cooldowns)
- **Weather per region** — type (Sunny/Cloudy/Rain/Storm), day count, remaining time
- **11 crafting stations** — fuel/output state, recipe time remaining
- Editing requires writing modified JSON back at the original byte offset (length-preserving or shift)

### ⚠️ HARD to edit (binary UE4 property data in `.sav`)
Requires writing a UE4 property serializer (~weeks of work). Possible but high effort:
- 5,893 individual world entities (ore nodes, NPCs, trees, treasure chests, geysers, teleporters)
- Their **positions, rotations, scales** (FTransform structs in CORA blocks)
- NPC health, ore node depletion state, lever/door states
- Adding/removing entities entirely
- World grid cell streaming data

### ❌ UNKNOWN / RISKY
- **`Backup` field** at end of character JSON (looks like a CRC/checksum) — game might detect tampering. Currently we leave it untouched and the game seems to accept edited files.
- **File header section sizes** in `INFO`/`CINF`/`GLOB` — if we change embedded JSON length, we may need to update size fields
- **Multiplayer worlds** — shared/server-validated state may revert
- **Hardcore characters** — may have stricter validation

### Edit Workflow Notes
- ALWAYS close the game before editing — it caches saves in memory
- The game itself rotates `.backup` and `.verbackup` files; our editor adds its own `editor_backups/` for safety
- Character JSON files use **tab indentation** (`\t`) — preserve when writing
- World save edits may shift byte offsets — handle carefully

---

## File Locations

```
%LOCALAPPDATA%\RSDragonwilds\Saved\
├── SaveCharacters\
│   ├── <CharacterName>.json              ← Plain JSON, easy to edit
│   ├── <CharacterName>.json.backup       ← Game's auto-backup
│   ├── <CharacterName>.json.NN.verbackup ← Version backups
│   └── backup\                           ← Additional backup folder
├── SaveGames\
│   ├── <WorldName>.sav                   ← Binary + embedded JSON
│   ├── <WorldName>.sav.backup            ← Game's auto-backup
│   └── <WorldName>.sav.N.verbackup       ← Version backups
└── EnhancedInputUserSettings.sav         ← Input settings (small)
```

**Critical**: Character data and world data are stored separately! Editing characters does not require touching the binary world file.

---

## Character Save Format (SaveCharacters/*.json)

Pure JSON, indented with tabs. Top-level structure:

```json
{
    "Version": 67,
    "meta_data": { ... },
    "SaveCount": 331,
    "Character": { ... },          // Vitals, position, customization
    "Inventory": { ... },          // 80+ slot personal inventory
    "PersonalInventory": { ... },  // Linked storage?
    "Loadout": { ... },            // Equipped gear (9 slots)
    "Progress": { ... },           // Unlocks, kills, recipes
    "QuestProgress": { ... },      // Quest states
    "RevealedLandmarks": { ... },
    "RevealedFog": { ... },        // Fog of war bitmap
    "Skills": { ... },             // All 10 skills + XP
    "Journal": { ... },            // Journal entries
    "MapCustomization": { ... },   // Custom map pins
    "Spellcasting": { ... },       // 48-slot spell loadout
    "Hardcore": { ... },
    "Backup": 1159903845           // CRC/checksum?
}
```

### `meta_data`
```json
{
    "char_guid": "BCFEDD0245A2B722433541AFA3E29927",
    "worlds_playtime": {
        "<WORLD_GUID>": <ms played>
    },
    "char_name": "Serious_Beans",
    "char_type": 0
}
```

### `Character`
```json
{
    "Playtime_sim": 79046.81,        // In-game playtime (seconds)
    "Playtime_wall": 107978.61,      // Real-world playtime (seconds)
    "Food": {},                       // Food buffs (when active)
    "Health": { "CurrentValue": 100 },
    "Stamina": { "CurrentValue": 100 },
    "Customization": { "CustomizationData": { ... } },
    "StatusEffects": {
        "Cold":      { "Hash": 1501092416, "Value": 0, "Active": [false] },
        "Poison":    { "Hash": 1673355410, "Value": 0, "Active": [false] },
        "Burning":   { "Hash": 1232270846, "Value": 0, "Active": [false] },
        "Bleeding":  { "Hash": 3836059435, "Value": 0, "Active": [false] },
        "Slow":      { "Hash": 897314269,  "Value": 0, "Active": [false] },
        "WellRested":{ "Hash": 2050017224, "Value": 0, "Active": [false] },
        "Cosiness":  { "Hash": 334594781,  "Value": 0, "Active": [false] },
        "Wither":    { "Hash": 2596365627, "Value": 0, "Active": [false] },
        "WellRestedDecayRate": 1,
        "LastMaxCosiness": 0
    },
    "LastAccessibleLocation": {
        "Position": "V(X=11924.46, Y=184569.45, Z=-3183.06)"  // STRING format!
    },
    "Sustenance": { "SustenanceValue": 29.9, "SustenanceDecayBuffer": 0 },
    "Hydration":  { "HydrationValue": 24.6, "HydrationDecayBuffer": 0 },
    "Toxicity":   { "ToxicityValue": 0,   "HighestToxicityValue": 0 },
    "Endurance":  { "EnduranceValue": 98.2, "EnduranceDecayBuffer": 0 },
    "Mount": {
        "MountEquipped": "None",
        "MountsUnlockedList": []
    },
    "SoulRift": {
        "SoulRiftedDuration": 0,
        "PlayingImaruEvent": false,
        "PreSoulRiftHydration": -1,
        "PreSoulRiftSustenance": -1,
        "PreSoulRiftEndurance": -1,
        "TrackedAI": []
    }
}
```

**IMPORTANT field name gotchas:**
- Sustenance uses `SustenanceValue`, NOT `CurrentValue`
- Hydration uses `HydrationValue`
- Toxicity uses `ToxicityValue` (also `HighestToxicityValue`)
- Endurance uses `EnduranceValue`
- Health/Stamina DO use `CurrentValue`
- Position is a STRING in format `V(X=..., Y=..., Z=...)` not numeric coords

### `Customization.CustomizationData`
DataTable references for visual customization:
```json
{
    "BodyType":          { "dataTable": "...DT_Customization_BodyType",        "rowName": "male_A_01" },
    "Head":              { "dataTable": "...DT_Customization_FaceType",        "rowName": "male_C_04" },
    "HairPreset":        { "dataTable": "...DT_Customization_HairPresets",     "rowName": "Preset8" },
    "FacialHairPreset":  { "dataTable": "...DT_Customization_FacialHairPresets","rowName": "M_C_Preset1" },
    "SkinTone":          { "dataTable": "...DT_Customization_SkinTone",        "rowName": "SkinTone3" },
    "HairColor":         { "dataTable": "...DT_Customization_HairColor",       "rowName": "Color2" },
    "EyeColor":          { "dataTable": "...DT_Customization_EyeColor",        "rowName": "Color3" },
    "EyebrowColor":      { "dataTable": "...DT_Customization_EyebrowColor",    "rowName": "Color2" }
}
```

### `Inventory` and `Loadout`
```json
{
    "0": {
        "GUID": "Pv_COUyui4Ki6aG-AhRRsw",   // Unique item instance GUID (base64-style)
        "ItemData": "ilFiZ9GcsUC5EOSxOrE74w", // Item type ID (base64-style)
        "Durability": 706,                    // For non-stackable items
        "VitalShield": 0,                     // Damage absorbed
        "Count": 22                           // For stackable items (not Quantity!)
    },
    "MaxSlotIndex": 81
}
```

Notes:
- Slot keys are stringified integers, but with **gaps** (e.g., 0,1,2,3,4,6,7,32,33...)
- Items are EITHER `Durability` (gear) OR `Count` (stackables) - rarely both
- `MaxSlotIndex` is the highest slot used, not the count

#### Loadout slots (equipment)
| Slot | Equipment |
|------|-----------|
| 0 | Head |
| 1 | Body |
| 2 | Legs |
| 3 | Cape |
| 4 | Ring |
| 5 | Weapon (uses `PlayerInventoryItemIndex` to reference inventory) |
| 6 | Shield (uses `PlayerInventoryItemIndex`) |
| 7 | Ammo (uses `PlayerInventoryItemIndex`) |
| 8 | Amulet (uses `PlayerInventoryItemIndex`) |

Slots 5-8 reference inventory by index, not by storing the item directly.

### `Skills.Skills`
```json
[
    { "Id": "Wf3i7Ha-B06DH719j1vtBw", "Xp": 22465 },
    ...
]
```

**Known skill ID mappings** (reverse-engineered):
| ID | Skill |
|----|-------|
| `Wf3i7Ha-B06DH719j1vtBw` | Mining |
| `4pefO9k1lUqfA6mvHNi1SA` | Woodcutting |
| `waK-8EyQFQ2xEjCGYmuTRQ` | Fishing |
| `Tn7t6DQyX0-Q0cM5K7B90A` | Smithing |
| `0hreSMRVXUihq9qjDO2CFA` | Runecrafting |
| `jqX0Gh6QI0GFFPCDFK_CJQ` | Cooking |
| `heq7u88Q2UuLXFqLGTVwQw` | Farming |
| `NOqC-z-2ckqi0El22qMFlw` | Fletching |
| `4zYUGF5u_0KbMLkWJmmBbQ` | Crafting |
| `PyUi-0LU_riFY46AnnFiWg` | Pottery |

XP curve appears to follow standard RuneScape exponential leveling.

### `Progress`
Tracks unlocks and history. All values are arrays of GUID strings.
```json
{
    "ItemsPickedUp":       [...],   // Items player has touched (162)
    "MilestoneMaterialsPickedUp": [...],
    "ActorsInteractedWith": [...],  // BP_Crafting_WeaponBench_C, etc. (26)
    "RecipesUnlocked":     [...],   // Crafting recipes (200)
    "RecipesNew":          [...],   // Unread/new recipes (97)
    "BuildingsUnlocked":   [...],   // Building pieces (334)
    "BuildingPiecesNew":   [...],
    "PlayerHooksTriggered":[...],   // Tutorial/scripted events (34)
    "SpellsUnlocked":      [...],   // Spells (23)
    "SpellsNew":           [...],
    "KilledOnceAIs":       [...],   // First-kill achievements (26)
    "BuildingsFavourited": [...],
    "VendorReputations":   []       // Vendor rep (likely vendor_id -> rep_value)
}
```

### `QuestProgress`
```json
{
    "QuestTracked": "jP8SfEP3QLjisgaHyBzCPw",  // Currently tracked quest GUID
    "Quests": [
        {
            "QuestId":    "AmuXOUitB08PYDCmdVA_Ug",
            "QuestState": 2,                      // 0=Not Started, 1=In Progress, 2=Completed
            "QuestObjective": "Objective3",
            "QuestInts":  [],
            "QuestBools": [
                { "QuestVariableName": "HasTriggeredEntryVolume", "QuestVariableValue": true },
                { "QuestVariableName": "SpokeToWOM",              "QuestVariableValue": true }
            ]
        }
    ],
    "QuestLocations": [
        { "QuestLocationId": "WOM_Objective_FTUE_GS", "QuestLocationsState": false }
    ]
}
```

### `RevealedFog`
```json
{
    "RevealedRegionsBitmap": 31,         // Bitmask of revealed regions (5 bits = 31)
    "RevealedRegionsDetectionActive": true
}
```

### `Spellcasting.SelectedSpells`
Array of 48 spell GUIDs (rune slot loadout). Empty slots are `""`.

### `MapCustomization.Pins`
```json
{
    "Pins": [
        {
            "PinType": 3,
            "PinLocation": [83583.52, 122723.01]  // X, Y world coords
        }
    ]
}
```

### `Hardcore`
```json
{
    "IsHardcore": false,
    "AssociatedWorld": "00000000000000000000000000000000"  // World GUID for HC characters
}
```

---

## World Save Format (SaveGames/*.sav)

Hybrid format: Binary UE4 property serialization framing **embedded JSON blobs** for component data.

### File Structure (3.31 MB example)

| Offset | Section | Purpose |
|--------|---------|---------|
| `0x00` | `SAVE` | Magic |
| `0x08` | `INFO` | File metadata block |
| `0x40` | `CINF` | Character info? |
| `0x35D` | `GLOB` | Global world data block |
| `0x371` | `METAL` | (unknown - "metadata"?) |
| `0x379` | `VERS` (×215) | Version markers |
| `0x385` | `CNIX` (×214) | Class name index |
| `0x3BB` | `CLST` (×214) | Class list |
| `0x3C3` | `CDVE` (×2106) | Class definition variant entries |
| `0x3CC` | `CDEF` (×2065) | Class definitions |
| `0x482` | `PNIX` (×214) | Property name index |
| `0x5C5` | `GOBS` | Game objects header (single occurrence) |
| `0x5CD` | `NOBJ` (×5893) | Named object entry |
| `0x5F8` | `PROP` (×6239) | Property block |
| `0xCEE` | `GLAI` | Global actor index |

### Section Header Format
- 4-byte magic ASCII
- 4-byte little-endian size
- Followed by data (often UE4 FString-prefixed strings: `<int32 length><utf8 bytes><null>`)

### UE4 Property Encoding (in PROP sections)
Standard UE4 GVAS-style property serialization:
- Property name (FString)
- Property type (`StrProperty`, `IntProperty`, `BoolProperty`, `StructProperty`, etc.)
- Size (int64)
- Index (int32)
- Type-specific data

Property type counts in a sample save:
- StructProperty: 100
- DoubleProperty: 63
- IntProperty: 33
- StrProperty: 13
- BoolProperty: 10
- NameProperty: 2
- FloatProperty: 2
- ByteProperty: 2

### Embedded JSON Sections

The binary format wraps JSON blobs for complex component data (this is where editing happens). Found via byte-by-byte scanning for `{` followed by valid JSON.

**Sample save: 168 JSON sections totaling ~250KB**

| Category | Count | Schema |
|----------|-------|--------|
| `world_events` | 1 | `{Version, Definitions:[{EventName, EventData:{Triggers:[...]}}]}` |
| `weather` | 1 | `{Version, Definitions:[{WeatherName, WeatherData:{TYPE, DAY_COUNT, REMAINING_TIME, ALT_PROFILE}}]}` |
| `station` | 11 | `{Version, Resources, Fuel, Output, FuelTimeRemaining, RecipeTimeRemaining, StationRunning?}` |
| `container` | 103 | `{Version, "0":{GUID, ItemData, Count?, Durability?}, ..., MaxSlotIndex, AllowAdds}` |
| `slot_data` | 52 | `{Version, MaxSlotIndex}` (mostly empty) |

**89 of the 103 containers actually contain items** — these are world chests, base storage, and station I/O containers.

### Container/Inventory Item Schema (in world)
```json
{
    "0": {
        "GUID":       "_hQ4jkKzHRb38JKwuVFG7g",
        "ItemData":   "pCUfN06B41MdpNqkjLEZqw",
        "Count":      22,            // Stackable items
        "VitalShield": 0,            // Optional
        "Durability": 1234           // Non-stackable items
    },
    "MaxSlotIndex": 4,
    "AllowAdds": true
}
```

### World Events Schema
```json
{
    "Definitions": [
        {
            "EventName": "base_raid_bm_1",
            "EventData": {
                "Triggers": [
                    {
                        "TriggerName": "delay_at_start",
                        "TriggerData": {
                            "CurrentValue": true,
                            "TriggerTime": "+9.05:30:00.000"   // ISO 8601 duration
                        }
                    },
                    { "TriggerName": "cooldown",         "TriggerData": { ... } },
                    { "TriggerName": "periodic_test",    "TriggerData": { ... } },
                    { "TriggerName": "DRAmbush_Zombies", "TriggerData": { ... } }
                ]
            }
        }
    ]
}
```

24 events found. Includes raids (`base_raid_bm_1`), ambushes (`dowdunreach_ambush_06`), etc.

### Weather Schema
```json
{
    "Definitions": [
        {
            "WeatherName": "base",
            "WeatherData": {
                "ALT_PROFILE": false,
                "TYPE": "EWeatherType::Sunny",   // Sunny, Cloudy, Rain, Storm, etc.
                "DAY_COUNT": 57,
                "REMAINING_TIME": 1460.28
            }
        },
        {
            "WeatherName": "dowdun",
            "WeatherData": { "TYPE": "EWeatherType::Cloudy", ... }
        }
    ]
}
```

Each region has its own weather state. `WeatherName` matches region IDs.

### World Entities (Binary, in NOBJ sections)

5,893 named objects in a sample save. Top types:

| Count | Type |
|-------|------|
| 2,283 | `BP_OreNode_Stone_C` |
| 916   | `BP_Spawner_Stone_C` |
| 337   | `BP_Spawner_AnimaInfusedBark_C` |
| 325   | `BP_OreNode_Sandstone_C` |
| 102   | `BP_Spawner_BittercapMushroom_C` |
| 84    | `BP_MiningRock_RuneEssence_Static_D_C` |
| 78    | `BP_AnimaVent_C` |
| 39    | `BP_LoreItem_C` |
| 38    | `BP_Spawner_Flax_C` |
| 22    | `BP_DwellberryBush_C` |
| 18    | `BP_InteractablePlayerTeleporter_C` |
| 18    | `BP_SwampRoot_C` |
| 11    | `BP_Dungeon_Treasure_Chest_BM_*` |
| 9     | `BP_RuneEssenceGeyser_*` |

Each object has a UAID (Unique Actor ID) like `BP_OreNode_Stone_C_UAID_00BE4395530E831002_1116877510` containing a hex location/instance hash.

Object instance positions are stored in `CORA` sub-blocks (likely transform/coordinate data) within each NOBJ entry — these are full UE4 binary FTransform structs (location, rotation, scale).

### Cell Grid System
World is divided into cells named `RSACell12800_X<n>_Y<n>` (12,800 unit grid). Each entity belongs to a cell, used for spatial streaming.

---

## Editing Strategy

### Safe to Edit (JSON-based)
1. **Character JSON files** — Direct JSON editing, low risk
2. **World save embedded JSON sections** — Replace bytes in-place; if new JSON ≠ old length, must shift offsets

### Important Edit Gotchas
- Character JSON uses **tab indentation** (`\t`) — Python `json.dump(..., indent="\t")`
- Position field is a **string**, not coords: `"V(X=11924.46, Y=184569.45, Z=-3183.06)"`
- Sustenance/Hydration/Toxicity/Endurance use `<Stat>Value` not `CurrentValue`
- Inventory stack count is `Count`, not `Quantity`
- Always create a backup before saving (game already creates `.backup` and `.verbackup` files but those rotate)
- The `Backup` field at the bottom is likely a CRC — game may detect tampering. If issues arise, try recomputing it

### Hard to Edit (Binary)
- **NOBJ object data** (positions, NPC health, ore states) — requires UE4 property serializer
- File header counts/checksums — need to understand `INFO`/`CINF`/`GLOB` block format
- Adding/removing entities — high risk, structure-dependent

### Untested / Unknown
- The `Backup` int at end of character JSON — possibly a checksum
- `meta_data.worlds_playtime` — may need updating if you transfer characters
- Modifying `MaxSlotIndex` when adding inventory items
- Effects of editing while game is running (always close game first!)

---

## Discovered Save Versions

Sample saves use `Version: 67`. Format may differ in earlier versions.

Save count `SaveCount` increments each save (useful as a heuristic for "freshness").

---

## Useful References for Future Work

- **UE4 GVAS spec**: https://github.com/trumank/uesave (Rust parser)
- **Python UE save tools**: `uetools`, `gvas`
- The game uses Jagex's "Dominion" engine — section markers (SAVE, GLOB, NOBJ, PROP, etc.) are Jagex-specific extensions on top of standard UE5 serialization
- World name `L_World` indicates this is the only level (game is single-map streaming)
