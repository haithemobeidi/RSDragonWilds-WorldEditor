# Custom Difficulty Settings - Reverse Engineering Notes

This document captures everything we learned about the **Custom Difficulty Settings** system in RuneScape: Dragonwilds.

## ⚠️ CRITICAL UPDATE (04-06-2026 evening session)

**The named TagName/NameProperty entries in the `WorldSaveSettings` block are NOT what the game reads at runtime.** There is a **secondary copy** stored as a tagless float array immediately after the `L_World\0` string near the top of the file. **The game reads from the secondary copy.** Editing only the named entries has no in-game effect (this is why Phase 1 of the editor failed).

### Secondary copy structure (verified working in Middle Eearth)

```
[L_World\0]                  ← 8 bytes
[1 byte padding (0x00)]
[uint32 count]               ← number of difficulty entries (LE)
[uint32 version]             ← always 1 so far
[float32 value[0]]           ← LE
[float32 value[1]]
...
[float32 value[count-1]]
[8-byte hash/GUID]           ← marks end of difficulty block
```

**Order of values matches** the order of named TagName entries in the `WorldSaveSettings` block. Use the named entries (which are still parseable) as the **tag → array index** map.

### Worlds without custom difficulty (e.g. Gielinor)

For worlds created BEFORE the custom difficulty feature shipped, `count = 0` and there are no float values, but the structure exists with `version = 1` and 4 bytes of zero padding before the hash. Adding values to these worlds requires **inserting bytes** which shifts downstream offsets — risky on large saves.

### Verification done this session
- Edited Middle Eearth's secondary copy floats from 0.5/0.5 → 0.1/0.1 (BuildingMaterialCostScale and CraftingCostScale)
- Game launched, world settings UI showed 0.1
- In-game crafting actually used reduced material cost (1 material per item, vs normal recipes)
- Confirmed both **UI display** AND **gameplay logic** read from the secondary copy

### Concrete offsets (Middle Eearth.sav reference)
- `L_World\0` at `0x026d`
- count at `0x0276` = 3
- version at `0x027a` = 1
- float[0] (NoBuildingStability) at `0x027e`
- float[1] (BuildingMaterialCostScale) at `0x0282`
- float[2] (CraftingCostScale) at `0x0286`
- next data starts at `0x028a`

(Offsets vary per file — always re-find via `L_World\0` byte search.)

---

## TL;DR

- The game has **35 customizable difficulty tags** that can be set when creating a world.
- The UI **only allows setting these at world creation**, not after — but the values can be edited externally via the **secondary copy** described above.
- Settings are stored in TWO places: the named `(GameplayTag, FloatValue)` entries inside `CustomDifficultySettings` array (which the game **doesn't read** for runtime), AND the tagless secondary float array after `L_World\0` (which the game **does read**).
- **No gather/yield/loot multipliers exist** in the custom settings — those are baked into the game's `.pak` files.
- **Workarounds for "more materials"**: lower `CraftingCostScale` and `BuildingMaterialCostScale` (you need less to craft), or lower enemy `Health` (faster kills = more drops/hour).

## How the discovery happened

1. The user's **Middle Earth** save was created with custom settings; the **Gielinor** save (main world) was not.
2. We dumped strings from both saves and found Middle Earth had three `Difficulty.*` tag names in its binary that Gielinor lacked.
3. We mined the game's `*.log` files and extracted **35 unique difficulty tags** the engine registers at startup (in `LogGameplayTags` and similar entries).
4. We hex-dumped Middle Earth around each tag and parsed the binary structure of the value.

## Complete list of 35 Difficulty Tags

### Combat — AI scaling (32 tags)

For each enemy category, three settings exist (Damage, Health, Resistances). Lower values = easier enemies.

| Category | Tags |
|----------|------|
| **Beast**     | `Difficulty.AI.Beast.Damage`, `.Health`, `.Resistances` |
| **Boss**      | `Difficulty.AI.Boss.Damage`, `.Health`, `.Resistances` |
| **Construct** | `Difficulty.AI.Construct.Damage`, `.Health`, `.Resistances` |
| **Critter**   | `Difficulty.AI.Critter.Damage`, `.Health`, `.Resistances` |
| **Garou**     | `Difficulty.AI.Garou.Damage`, `.Health`, `.Resistances` |
| **Goblin**    | `Difficulty.AI.Goblin.Damage`, `.Health`, `.Resistances` |
| **MiniBoss**  | `Difficulty.AI.MiniBoss.Damage`, `.Health`, `.Resistances` |
| **Skeleton**  | `Difficulty.AI.Skeleton.Damage`, `.Health`, `.Resistances` |
| **Undead**    | `Difficulty.AI.Undead.Damage`, `.Health`, `.Resistances` |
| **Zamorak**   | `Difficulty.AI.Zamorak.Damage`, `.Health`, `.Resistances` |
| **Toggle**    | `Difficulty.AI.DisableAggressiveAI` (boolean — 1.0 = on) |

### Environment

| Tag | Type | Notes |
|-----|------|-------|
| `Difficulty.Environment.FriendlyFire` | bool (1.0 / 0.0) | Whether you can damage allies |

### Player

| Tag | Type | Notes |
|-----|------|-------|
| `Difficulty.Player.NoBuildingStability` | bool (1.0 / 0.0) | If 1.0, buildings don't need structural support |

### Progression

| Tag | Type | Notes |
|-----|------|-------|
| `Difficulty.Progression.BuildingMaterialCostScale` | float | 1.0 = normal, 0.5 = half cost, 2.0 = double cost |
| `Difficulty.Progression.CraftingCostScale`         | float | 1.0 = normal, 0.5 = half cost, 2.0 = double cost |

### What's NOT in the list (and why this matters)

These DO NOT exist as custom difficulty tags. Anything in this list requires modding the game's `.pak` files:

- ❌ Mining yield / ore quantities
- ❌ Woodcutting yield / log quantities
- ❌ Fishing catch rates
- ❌ Foraging yields
- ❌ Monster loot drop multipliers
- ❌ Gold drop multipliers
- ❌ XP rate multipliers
- ❌ Anything else gathering-related

## Binary format

The `WorldSaveSettings` PROP block contains a field called `CustomDifficultySettings`, which is a UE4 `TArray<FStruct>` of difficulty entries. Each entry is a struct of `(GameplayTag, float)`.

### Per-entry binary layout

```
[FString "TagName"        ] : property name        ─┐
[FString "NameProperty"   ] : property type        ─┤  UE4 GVAS-style property header
[uint64  data_size        ]                         │
[uint32  array_index      ]                         │
[FString <difficulty_tag> ] : the actual tag       ─┘
[FString "None"           ] : end of inner struct
[float32 <value>          ] : the float value (4 bytes, little-endian IEEE 754)
```

### Hex example from Middle Earth (`Difficulty.Player.NoBuildingStability` at `0x646`)

```
44 69 66 66 69 63 75 6c 74 79 2e 50 6c 61 79 65   Difficulty.Playe
72 2e 4e 6f 42 75 69 6c 64 69 6e 67 53 74 61 62   r.NoBuildingStab
69 6c 69 74 79 00                                 ility.
05 00 00 00 4e 6f 6e 65 00                        FString "None"
00 00 80 3f                                       ← float 1.0 (LE)
08 00 00 00 54 61 67 4e 61 6d 65 00               next entry: FString "TagName"
```

### Float interpretation cheat sheet (little-endian IEEE 754)

| Hex bytes (LE) | Value |
|---------------|-------|
| `00 00 00 00` | 0.0 |
| `cd cc cc 3d` | 0.1 |
| `00 00 00 3f` | 0.5 |
| `00 00 80 3f` | 1.0  *(default)* |
| `00 00 00 40` | 2.0 |
| `00 00 80 40` | 4.0 |
| `00 00 20 41` | 10.0 |

### Confirmed values from Middle Earth save

| Tag | Hex | Float |
|-----|-----|-------|
| `Difficulty.Player.NoBuildingStability` | `00 00 80 3f` | **1.0** (toggle on) |
| `Difficulty.Progression.BuildingMaterialCostScale` | `00 00 00 3f` | **0.5** (half cost) |
| `Difficulty.Progression.CraftingCostScale` | `00 00 00 3f` | **0.5** (half cost) |

The user created this world with halved building/crafting costs and no-stability buildings.

## Editing strategy

### Phase 1 — Edit existing entries (length-preserving, SAFE)

If a world already has at least one custom difficulty entry (like Middle Earth), we can:
1. Find the entry by tag name
2. Locate the float bytes (4 bytes after the inner `None\x00` marker)
3. Replace with new float bytes — same length, no offset shifts

This is **trivial and safe**. No binary surgery needed.

### Phase 2 — Inject new entries (length-changing, RISKY)

If a world has zero custom difficulty entries (like Gielinor), the array is empty and we need to:
1. Find the empty `CustomDifficultySettings` array marker in the WorldSaveSettings PROP block
2. Compute the byte size of the new entries to inject
3. Insert the bytes
4. **Update the PROP block size header** (`PROP\xee\x06\x00\x00` → larger size)
5. **Possibly update the file's outer size headers** (INFO/CINF/GLOB blocks may have aggregate sizes)
6. **Possibly update the array element count** stored at the start of the array

This is binary surgery and requires understanding more of the Dominion engine wrapper format. **First test with Phase 1 to confirm the game actually applies modified values.**

## Useful difficulty value presets

### "Easy survival" (recommended starting point for grinding)
```
Difficulty.AI.*.Health        = 0.5    (all enemies half HP)
Difficulty.AI.*.Damage        = 0.5    (all enemies half damage)
Difficulty.Progression.CraftingCostScale         = 0.5
Difficulty.Progression.BuildingMaterialCostScale = 0.5
```

### "Creative-ish mode"
```
Difficulty.AI.DisableAggressiveAI                = 1.0   (no enemies attack you)
Difficulty.Progression.CraftingCostScale         = 0.1   (1/10th cost)
Difficulty.Progression.BuildingMaterialCostScale = 0.1
Difficulty.Player.NoBuildingStability            = 1.0
```

### "Effective resource doubling" (closest to user's original ask)
```
Difficulty.Progression.CraftingCostScale         = 0.5   (need half the materials)
Difficulty.AI.Beast.Health    = 0.5
Difficulty.AI.Goblin.Health   = 0.5
Difficulty.AI.Skeleton.Health = 0.5
# ... etc for all AI categories — kill enemies in half the time = effectively 2x drops/hour
```

## True drop rate multipliers (out of scope for save editing)

To **actually** double the loot from a single ore node / tree / monster, you need to mod the game's `.pak` files:

1. Locate `RSDragonwilds-Windows.pak` in `<SteamApps>/common/RSDragonwilds/Content/Paks/`
2. Extract with **UnrealPak** or **FModel**
3. Find the loot DataTables (likely under `/Game/Gameplay/World/Mining/`, `/Game/Gameplay/World/Trees/`, `/Game/Gameplay/AI/<EnemyType>/Loot/`)
4. Edit drop quantities in DataTable rows
5. Repack as a mod `.pak` and load via a UE5 mod loader (e.g., **UE4SS** or game-specific loader)

This is a separate, much larger project than save editing.

## Debugging / verification approach

To verify a modified custom difficulty setting actually applies in-game:

1. Make a backup of your save (the editor does this automatically)
2. Edit the value (e.g., change `CraftingCostScale` from 1.0 to 0.1)
3. Launch the game and load the modified world
4. Try to craft something — if it costs 10x less than normal, the edit worked
5. Check the game logs at `%LOCALAPPDATA%\RSDragonwilds\Saved\Logs\RSDragonwilds.log` after launch — they may log the loaded difficulty values
