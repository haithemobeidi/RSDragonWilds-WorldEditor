# RS Dragonwilds Save Editor — Project Documentation

## Project Overview

**Brief Description:** A web-based save editor for RuneScape: Dragonwilds. Reads and writes character JSON files and partially edits the binary world `.sav` files (Jagex Dominion Engine — custom UE5 fork).

**Technology Stack:**
- **Backend:** Python 3.12 + Flask
- **Frontend:** Vanilla HTML/CSS/JS (single-page app, currently monolithic in `templates/index.html`)
- **No build step** — venv + `python app.py`

**Key Goals:**
- Edit character vitals, skills, inventory, quests, spells, mounts, position, fog of war
- Edit world chests, crafting stations, weather, world events
- Edit custom difficulty settings (✅ DISCOVERED — secondary copy at L_World+10 is the real one)
- Unlock cross-world-type character compatibility (✅ DISCOVERED — `meta_data.char_type` flag)
- Be safe by default — auto-backup before every write

## Current Status

**Last session:** 2026-04-06 (4-session marathon)
**Build status:** ✅ Working — full feature set + refactored + publicly shipped
**Repo:** https://github.com/haithemobeidi/RSDragonWilds-WorldEditor (public)

**Major discoveries (in chronological order):**

1. **Difficulty "secondary copy"** — game reads runtime difficulty values from a tagless float array at `L_World+10`, NOT from named TagName/NameProperty entries.
2. **`char_type` field gates custom-world access** — `meta_data.char_type` in character JSON. `0` = standard-only, `3` = custom-only. **Mutually exclusive** (verified — there is no "both" value).
3. **L_World+9 enum byte** controls visible difficulty preset — `0`=Standard, `1`=Hard, `3`=Custom. **But this byte alone is just a UI cache** — the game's serializer overwrites it on save unless it matches the persistent storage.
4. **THE PERSISTENT World Mode flag** — first byte of the `CustomDifficultySettings` PROP field inside the WorldSaveSettings PROP block. `0x00`=Standard, `0x03`=Custom. **Both bytes (L_World+9 AND PROP byte) must be set together** for the game to recognize and persist a custom-world classification.
5. **Verified end-to-end:** Successfully converted Gielinor (a standard world that predated custom difficulty) to a Custom World. Played main character (Serious_Beans, char_type=3) on it with full custom difficulty applied. Conversion persists across game saves and restarts.

**Now exposed in the GUI:**
- World Mode display + "Convert to Custom" / "Revert to Standard" button per world
- Character "World Compat" (char_type) dropdown — Standard / Custom

**Open items:**
- `parser.py` `_find_difficulty_entries()` and `update_difficulty_value()` still edit the named entries (not the secondary copy). Need rewrite to target the L_World+17 floats.
- `templates/index.html` is monolithic (~1700 lines now) — refactor still pending
- Drop rate / loot multiplier modding (user request) — would require .pak modding, not save editing

## File Locations Reference

```
%LOCALAPPDATA%\RSDragonwilds\Saved\
├── SaveCharacters\
│   ├── <CharacterName>.json              ← Plain JSON, easy to edit
│   ├── <CharacterName>.json.backup       ← Game's auto-backup
│   └── <CharacterName>.json.NN.verbackup ← Version backups
├── SaveGames\
│   ├── <WorldName>.sav                   ← Binary + embedded JSON
│   └── <WorldName>.sav.backup            ← Game's auto-backup
└── Logs\                                 ← Useful for reverse engineering
```

## Project Structure

```
RSDragonwildsSaveEditor/
├── CLAUDE.md                  # This file
├── SESSION_PROTOCOLS.md       # Start/work/end session protocols
├── SAVE_FORMAT.md             # Reverse-engineered save format reference
├── DIFFICULTY_SETTINGS.md     # Difficulty system reverse engineering
├── TODO_TOMORROW.md           # Carryover work for next session (when present)
├── parser.py                  # CharacterSave + WorldSave classes (all read/write logic)
├── app.py                     # Flask app with all API routes
├── templates/index.html       # Single-page UI (monolithic — refactor pending)
├── requirements.txt           # flask>=3.0
├── run.sh / run.bat           # Convenience launchers
├── venv/                      # Python venv (gitignored)
├── docs/
│   ├── handoffs/              # Session handoff documents
│   └── MASTER_HANDOFF_INDEX.md
└── .claude/
    └── commands/
        ├── start-session.md   # /start-session slash command
        └── end-session.md     # /end-session slash command
```

## Key Architecture

### `parser.py`
Two main classes:

1. **`CharacterSave`** — Plain JSON character files. Simple read/write.
   - `get_summary()` returns flattened data for the UI
   - Editing methods: `update_skill_xp`, `update_health`, `update_stat`, `update_quest_state`, `update_quest_bool`, `update_position`, `update_spell_slot`, `add_mount`, `equip_mount`, `reveal_full_map`, `repair_all_items`, etc.
   - `save()` writes back with auto-backup to `editor_backups/`

2. **`WorldSave`** — Binary `.sav` files (Dominion engine).
   - `_find_json_sections()` byte-scans for embedded JSON blobs and parses them
   - `_categorize_sections()` tags each section as `world_events`, `weather`, `station`, `container`, etc.
   - `_find_difficulty_entries()` parses binary `CustomDifficultySettings` entries (UE4 NameProperty + float)
   - Editing methods: `update_container_item`, `update_weather`, `update_event_trigger`, `disable_all_raids`, `update_difficulty_value`
   - `save()` is **length-preserving** for JSON sections (pads with whitespace inside the JSON) and writes binary edits directly to `raw_data`

### `app.py`
Flask routes:
- `GET /` — main UI
- `GET /api/character/<filename>` — character summary JSON
- `POST /api/character/<filename>/update` — apply edits (batch)
- `POST /api/character/<filename>/save` — write to disk
- `GET /api/world/<filename>` — world data (events, weather, stations, containers, difficulty)
- `POST /api/world/<filename>/update` — apply world edits (batch)
- `POST /api/world/<filename>/save` — write world to disk
- `POST /api/reload` — re-discover all saves from disk

## Commands Reference

```bash
# Start server
cd "~/Documents/Vibe Projects/RSDragonwildsSaveEditor"
source venv/bin/activate
python app.py
# Open http://localhost:5000

# Quick parse test
python -c "from parser import discover_saves, CharacterSave; saves = discover_saves(); cs = CharacterSave(saves['characters'][0]['filepath']); cs.load(); print(cs.get_summary()['meta'])"
```

## Development Guidelines

- **Editing character JSON is safe** — plain JSON, well understood, all field names documented in `SAVE_FORMAT.md`
- **Editing world JSON sections is mostly safe** — length-preserving with padding fallback
- **Editing world binary (difficulty settings) is NEW and unproven** — Phase 1 file-level edit works but in-game effect TBD (see `TODO_TOMORROW.md`)
- **Always close the game** before editing world saves
- **Auto-backup is on by default** — every save creates a timestamped copy in `editor_backups/`
- **Be honest in handoffs** — if something doesn't work, say so. Don't paper over issues.

## Known Open Items

| Task | Status | Notes |
|------|--------|-------|
| Verify `char_type=3` keeps standard-world access | ✅ Resolved — it does NOT (mutually exclusive with 0) |
| Find persistent custom-mode flag for old worlds | ✅ Resolved — first byte of CustomDifficultySettings PROP field |
| Convert Gielinor to custom (use main char on custom Gielinor) | ✅ Done — verified working end-to-end |
| Add `char_type` editor to Flask UI | ✅ Done (this session) |
| Add World Mode conversion to Flask UI | ✅ Done (this session) |
| Update `parser.py` difficulty methods to target secondary copy | High | Currently edits wrong location — has no in-game effect |
| Refactor monolithic `index.html` | Pending | ~1700 lines |
| Loot/drop multiplier (trainer-style) | Future | Requires .pak modding; not save editing |
