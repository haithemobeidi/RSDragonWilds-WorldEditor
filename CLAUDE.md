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
- Edit custom difficulty settings (in progress — Phase 1 done at file level, in-game effect TBD)
- Be safe by default — auto-backup before every write

## Current Status

**Last session:** 2026-04-06
**Build status:** ✅ Working (Flask server runs, all character editing features functional)
**Open questions:**
- Difficulty settings edit doesn't apply in-game (test plan in `TODO_TOMORROW.md`)
- `templates/index.html` is monolithic (~1500 lines) — refactor pending (task #17)

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
| Difficulty in-game test | Pending tomorrow | See `TODO_TOMORROW.md` |
| Phase 2 (inject difficulty into Gielinor) | Blocked | Waiting on test results |
| Refactor monolithic `index.html` | Pending | ~1500 lines, needs splitting into partials/modules |
| `.pak` modding for true gather yields | Out of scope (separate project) | Game's data tables, not save data |
