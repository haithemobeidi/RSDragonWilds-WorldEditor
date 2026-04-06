# Quick Reference — Save File Flags Cheat Sheet

The "I just want to flip a flag" reference. For deeper detail see `SAVE_FORMAT.md` and `DIFFICULTY_SETTINGS.md`.

**ALWAYS close the game before editing. ALWAYS make 2 backups.**

---

## 🎭 Character Type (controls which world types a character can join)

**File:** `%LOCALAPPDATA%\RSDragonwilds\Saved\SaveCharacters\<CharName>.json`
**Field:** `meta_data.char_type` (integer)

| Value | Meaning | Can join |
|-------|---------|----------|
| `0`   | Standard character | Standard worlds only (Gielinor, default new worlds) |
| `3`   | Custom character | Custom worlds only (Middle Eearth, custom-difficulty worlds) |

**To change:** Edit the JSON, set `meta_data.char_type` to desired value, save with tab indentation (`json.dump(data, f, indent="\t")`).

**Trade-off:** Mutually exclusive — char_type=3 LOSES access to standard worlds and vice versa. Flippable any time, no data corruption.

**Verified:** ✅ Tested both directions; character data fully preserved.

---

## 🌍 World Difficulty Enum (controls difficulty preset AND custom mode)

**File:** `%LOCALAPPDATA%\RSDragonwilds\Saved\SaveGames\<WorldName>.sav`
**Location:** 4 bytes at offset `L_World+9` (find `b'L_World\x00'` then add 9 to get the offset)
**Type:** uint32 LE

| Value | Meaning | Effect |
|-------|---------|--------|
| `0`   | Standard | Default difficulty preset, standard world classification |
| `1`   | Hard     | Hard difficulty preset, still standard world classification |
| `2`   | (unknown — possibly Easy/Brutal) | Untested |
| `3`   | **Custom** | Converts world to "Custom World Settings" — unlocks all 5 difficulty categories in-game UI, requires `char_type=3` characters |

**To change:** Locate `L_World\0` byte sequence in the file, write 4 LE bytes at that offset + 9.

```python
import struct
data = bytearray(open(sav_path, 'rb').read())
p = data.find(b'L_World\x00')
data[p+9 : p+13] = struct.pack('<I', 3)  # 3 = Custom
open(sav_path, 'wb').write(bytes(data))
```

**No file size change** — just flips 1 of the 4 bytes.

**Verified:** ✅ Successfully converted Gielinor (standard) to Custom on 04-06-2026 evening session. Game accepted, in-game UI showed all custom difficulty categories, settings could be edited normally.

**Important:** After conversion, the game manages float data automatically when you edit settings via in-game UI. No need to inject float bytes manually.

---

## 🎯 Custom Difficulty Float Values (when world is already Custom)

**File:** `%LOCALAPPDATA%\RSDragonwilds\Saved\SaveGames\<WorldName>.sav`
**Location:** Starting at `L_World + 17` (after `pad + difficulty_enum + version`)
**Type:** N × float32 LE, where N = number of named entries in CustomDifficultySettings array

**Structure:**
```
[L_World\0]          ← 8 bytes
[1 byte pad = 0x00]
[uint32 difficulty_enum]   ← see table above
[uint32 version = 1]
[float32 value[0]]
[float32 value[1]]
...
[float32 value[N-1]]
[8-byte hash]
```

**Order:** Floats appear in the same order as the named TagName/NameProperty entries elsewhere in the file. Use the named-entry section to map tag → array index.

**Verified:** ✅ Edited Middle Eearth's secondary copy floats from 0.5 → 0.1; in-game UI and gameplay both reflect the change. Crafting cost dropped to 1 material per item.

**⚠️ The named TagName/NameProperty entries are read-only schema** — editing them alone has NO effect. The game reads from this secondary copy.

---

## ❤️ Hardcore Mode (character flag)

**File:** `<CharName>.json`
**Field:** `Hardcore.bIsHardcore` (or similar — see existing parser)

Already exposed in the editor UI. Skip this — not part of the recent discoveries.

---

## 📋 Tag Catalog (for the 35 difficulty tags)

See `DIFFICULTY_SETTINGS.md` for the full list of tag names and their friendly names. Categories:

- `Difficulty.Player.*` (e.g., NoBuildingStability)
- `Difficulty.Progression.*` (CraftingCostScale, BuildingMaterialCostScale)
- `Difficulty.Environment.*` (FriendlyFire, world event scales)
- `Difficulty.AI.<EnemyType>.*` (Damage, Health, Resistances per enemy type)

The game's UI exposes ALL of these only when world is `difficulty_enum=3` (Custom).

---

## 🛟 Backups

**Always 2 backups before any edit.** Standing rule.

```python
import shutil
from datetime import datetime
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy(target_file, f'research_backups/{name}_BEFORE_{action}_{ts}_A')
shutil.copy(target_file, f'research_backups/{name}_BEFORE_{action}_{ts}_B')
```

---

## ⚡ Recipe: "Convert standard world to custom (PERMANENT)"

✅ **Solved 04-06-2026.** Two bytes must be set together for the game to recognize and persist a custom-world classification:

### The two bytes

| Byte | Location | From | To | Notes |
|------|----------|------|-----|-------|
| **A** | `L_World + 9` (uint32 LE) | `0x00 00 00 00` (Standard) | `0x03 00 00 00` (Custom) | Display/UI cache byte |
| **B** | First byte of `CustomDifficultySettings` PROP field | `0x00` | `0x03` | **Persistent storage** in WorldSaveSettings PROP block |

**Critical finding:** Setting only ONE byte doesn't work — the game's load logic checks both. Setting BOTH makes the conversion **persist permanently across game saves and restarts**.

### How to find byte B (PROP field offset)

The CustomDifficultySettings field is index 8 in the WorldSaveSettings PROP block. Locate via:

```python
import struct
data = open(sav_path, 'rb').read()
prop_p = data.find(b'PROP')
count = struct.unpack('<I', data[prop_p+8:prop_p+12])[0]  # = 13
data_start = prop_p + 12 + count * 4
offsets = struct.unpack(f'<{count}I', data[prop_p+12 : prop_p+12 + count*4])
cds_pos = data_start + offsets[8]  # ← byte to flip is HERE
```

### Full conversion script

```python
import struct
sav_path = '.../Gielinor.sav'
data = bytearray(open(sav_path, 'rb').read())

# Byte A: L_World+9 enum
lw = data.find(b'L_World\x00')
data[lw+9 : lw+13] = struct.pack('<I', 3)

# Byte B: CustomDifficultySettings PROP field first byte
prop_p = data.find(b'PROP')
count = struct.unpack('<I', data[prop_p+8:prop_p+12])[0]
data_start = prop_p + 12 + count * 4
offsets = struct.unpack(f'<{count}I', data[prop_p+12 : prop_p+12 + count*4])
cds_pos = data_start + offsets[8]
data[cds_pos] = 0x03

open(sav_path, 'wb').write(bytes(data))
```

### To play Gielinor as custom with main character

**One-time setup (already done for Serious_Beans):**
1. Set `Serious_Beans.json` `meta_data.char_type` = 3
2. Convert Gielinor.sav using the script above (both bytes)

After both: launch game, pick Serious_Beans, join Gielinor → permanent custom mode.

**To revert:**
- Set `char_type` back to `0` (regains standard world access)
- Set BOTH bytes back to `0` in the world file (regains standard classification)

### Note on the L_World+9 byte alone

If you flip ONLY the L_World+9 enum (without the PROP byte), the game will:
- Show the world as Custom in the menu temporarily
- Let you join and the in-game settings UI will show Custom categories
- But gameplay will still use Standard difficulty values
- And the byte will be overwritten back to 0 on the next save

The PROP block byte is the source of truth. Always flip both.
