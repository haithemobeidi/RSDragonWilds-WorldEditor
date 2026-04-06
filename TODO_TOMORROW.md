# TODO Tomorrow — Difficulty Settings Investigation

**Context:** We built Phase 1 of the difficulty settings editor (length-preserving in-place edit). User tested it on `Middle Eearth.sav` and the change did **not** apply in-game. We need to figure out why before building Phase 2 (binary injection into Gielinor).

## What we know

- The editor app's in-memory state shows the user's edited value (e.g., 0)
- After playing and quitting, the disk file shows the **original** values back (0.5 / 0.5 / 1.0)
- The disk file size **doubled** (197KB → 412KB) on the in-game save — game completely re-serialized the world
- This means the game either ignored our edit when loading, OR overwrote it when saving

## Possible causes

1. **Game caches difficulty values at world load**, then writes the cached values back on save (overwriting our edit)
2. **Hidden checksum/CRC** — game detects tampering and falls back to a stored copy
3. **Secondary copy of the values** somewhere else in the file (or in another file) that takes precedence at runtime
4. **Game restored from `.sav.backup`** because our edit failed validation

## Clean test procedure (do this first thing tomorrow)

**Game must be CLOSED throughout setup.**

1. **Close the game completely** (verify no `RSDragonwilds.exe` processes)
2. **In the editor app**, click **"Reload Files"** at the top right (re-reads from disk so we're not looking at stale memory from previous session)
3. **Click "Load Editable Data"** on Middle Earth — confirm it shows **0.5 / 0.5 / 1.0**
4. **Edit Crafting Cost to 0.1** (use 0.1 not 0, so we can clearly distinguish "our value" vs "game default")
5. **Click "Save World"** in the editor
6. **From a separate terminal**, verify the disk file contains 0.1:
   ```bash
   cd "~/Documents/Vibe Projects/RSDragonwildsSaveEditor"
   source venv/bin/activate
   python3 -c "from parser import WorldSave; ws = WorldSave('~/AppData/Local/RSDragonwilds/Saved/SaveGames/Middle Eearth.sav'); ws.load(); print([(e['tag'], e['value']) for e in ws.get_difficulty_settings()['current']])"
   ```
   Expected: `Difficulty.Progression.CraftingCostScale = 0.10000000149011612`
7. **Launch the game**
8. **Load Middle Earth** but do **NOT play** — go straight to the world settings/edit menu
9. **What does the game show for Crafting Cost?**
   - **0.1** → game READS our edit. The issue is that it overwrites on save. → Phase 2 still viable, just need to advise user not to save in-game
   - **0.5** → game IGNORES our edit. There's a checksum, secondary copy, or our parse offset is wrong → need deeper investigation
10. **Quit without saving** in-game (don't let it auto-save)
11. **From terminal**, re-check the disk file with the same command from step 6
12. **Result interpretation:**
    - File still shows 0.1 → game read it but UI showed wrong value (means UI displays cached/default values, but file edit might still apply at gameplay level)
    - File reverted to 0.5 → game wrote over our edit just by loading the world (most likely a checksum issue)

## If the test reveals a checksum

Look for nearby float/int data that might be a CRC over the difficulty block:

```bash
cd "~/Documents/Vibe Projects/RSDragonwildsSaveEditor"
source venv/bin/activate
python3 << 'PYEOF'
data = open('~/AppData/Local/RSDragonwilds/Saved/SaveGames/Middle Eearth.sav', 'rb').read()
# Look at bytes 50 before and 100 after the first difficulty entry
import struct
idx = data.find(b'Difficulty.Player.NoBuildingStability')
print('Hex around first difficulty entry:')
chunk = data[idx-100:idx+300]
for i in range(0, len(chunk), 16):
    print(f"  0x{idx-100+i:04x}: {chunk[i:i+16].hex()}")
PYEOF
```

Look for 4-byte values that might change when we edit a float — those are checksum candidates. Then we'd need to recompute on write.

## If the test reveals values are read but not used (cached)

Then the game has a "first load" cache. Possible workarounds:
- Edit `.sav.backup` AND `.sav` — game might use backup as source of truth
- Find and edit the cached values directly (probably stored in a different binary structure)

## Other context preserved

- Phase 1 implementation (length-preserving 4-byte float swap) is committed and working at the file level
- All the parser/edit code is in `parser.py` `WorldSave.update_difficulty_value()` and `_find_difficulty_entries()`
- Catalog of all 35 known difficulty tags is in `parser.py` `KNOWN_DIFFICULTY_TAGS` constant
- Full reverse-engineering notes in `DIFFICULTY_SETTINGS.md`
- Refactor of monolithic `index.html` (~1500 lines) is also pending — task #17 in TaskList

## Reminder

Phase 2 (injecting new entries into Gielinor's empty `CustomDifficultySettings` array) is BLOCKED until we understand why Phase 1's in-place edit doesn't apply in-game. No point doing binary surgery on the main save until we know it would actually take effect.
