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

## ⚡ Recipe: "Play Gielinor as Custom with main character"

⚠️ **PERSISTENCE BUG (open issue):** The game's auto-save **resets the Gielinor enum byte to 0 every time**. The play session works because the game reads the file at load time, but the byte gets overwritten when the game saves. **You must re-flip the enum BEFORE every play session.**

**Pre-play (each session):**

1. Make sure game is closed
2. Run: `python scripts/flip_gielinor_custom.py`
3. Immediately launch the game
4. Pick Serious_Beans (must already be `char_type=3`)
5. Join Gielinor → play normally
6. Quit when done — game will reset enum to 0 (this is fine, it'll be re-flipped next session)

**One-time setup (already done):**
- `Serious_Beans.json` `meta_data.char_type` = 3 (custom-only access)

**To revert character to standard worlds (if needed):**
```python
import json
sb = json.load(open('.../Serious_Beans.json'))
sb['meta_data']['char_type'] = 0
json.dump(sb, open('.../Serious_Beans.json','w'), indent='\t')
```

**To revert Gielinor manually:**
```bash
python scripts/flip_gielinor_custom.py --revert
```

**Open question for next session:** Find the truly persistent custom-mode flag (somewhere other than `L_World+9`) so we don't have to re-flip every session.
