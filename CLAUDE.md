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

**Last session:** 2026-04-06 (evening)
**Build status:** ✅ Working
**Major discoveries this session:**
1. **Difficulty "secondary copy"** — game reads from raw float array at `L_World+10` (offset varies per file), NOT from the named TagName/NameProperty entries we were editing. Editing only the named entries had no effect; editing the secondary copy DOES affect both UI and gameplay (verified in Middle Eearth).
2. **`char_type` field unlocks custom worlds** — `meta_data.char_type` in character JSON gates custom-world access. `0` = standard-only, `3` = custom-compatible. Changing Serious_Beans from 0→3 allowed it to join Middle Eearth (the custom world) successfully — skills, inventory, everything intact.

**Open questions / risks:**
- ⚠️ **Does `char_type=3` retain access to standard worlds (Gielinor)?** UNTESTED. User suspects it does NOT. Possible values: 0=standard-only, 3=custom-only, OR a bitmask where `1`=standard, `2`=custom, `3`=both. Needs investigation.
- World state transfer (house, chests, exploration) from Gielinor → custom world is the next big goal
- `parser.py` `_find_difficulty_entries()` and `update_difficulty_value()` edit the WRONG location — they edit the named entries which the game ignores. Needs to be rewritten to target the L_World+10 secondary copy.
- `templates/index.html` is monolithic (~1500 lines) — refactor still pending

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
| Verify `char_type=3` keeps standard-world access | **CRITICAL — untested** | If broken, need to find correct value (maybe `1`?) |
| Update `parser.py` difficulty methods to target secondary copy | High | Currently edits wrong location — has no in-game effect |
| Transfer Gielinor world state → custom world (storage boxes priority) | **Next session main goal** | User wants at least storage chests transferred. Could potentially deserialize NOBJ entries. |
| Add `char_type` editor to Flask UI | Medium | Trivial JSON edit, big QoL win |
| Refactor monolithic `index.html` | Pending | ~1500 lines |
| `.pak` modding for true gather yields | Out of scope | Separate project |
