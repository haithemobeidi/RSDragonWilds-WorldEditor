# Codebase Index

A file-by-file map of the RS Dragonwilds Save Editor project. Read this with the latest handoff in `docs/handoffs/` to know exactly where everything lives.

## Top-level files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project overview, tech stack, file locations, dev guidelines, current status |
| `SESSION_PROTOCOLS.md` | Mandatory start/work/end session protocols |
| `SAVE_FORMAT.md` | Reverse-engineered save file format reference (character JSON + world binary) |
| `DIFFICULTY_SETTINGS.md` | Reverse-engineered notes on the custom difficulty system, all 35 known tags, binary layout |
| `CODEBASE_INDEX.md` | This file |
| `TODO_TOMORROW.md` | Carryover work for the next session (when present — may be deleted after the work is done) |
| `requirements.txt` | Python deps: just `flask>=3.0` |
| `run.sh` / `run.bat` | Launch helpers (creates venv if missing, starts Flask server) |
| `.gitignore` | Excludes `venv/`, `__pycache__/`, `editor_backups/` |

## Python source

### `parser.py` (~1000 lines)
The data layer. All save file reading and writing logic lives here.

**Module-level constants:**
- `SKILL_NAMES` — dict mapping the 10 known skill GUIDs to friendly names (Mining, Woodcutting, etc.)
- `XP_TABLE` — RS-style level XP thresholds (level 0–50)
- `xp_to_level(xp)` / `level_to_xp(level)` — conversion helpers
- `KNOWN_DIFFICULTY_TAGS` — list of all 35 difficulty tag strings (mined from game logs)
- `DIFFICULTY_TAG_INFO` — dict mapping tag → (friendly_name, type, hint_text)

**`@dataclass JsonSection`** — A JSON blob found embedded in a binary world save (offset, length, parsed data, category).

**`class CharacterSave`** — Plain JSON character files (`SaveCharacters/*.json`).
- `load()` — read the JSON file
- `save(backup=True)` — write back, creates timestamped backup in `editor_backups/`
- `get_summary()` — flatten all data for the UI (skills, quests, inventory, status effects, position parsed from `V(X=..., Y=..., Z=...)` string format, etc.)
- Editing methods: `update_skill_xp`, `max_all_skills`, `update_health`, `update_stamina`, `update_stat` (handles Sustenance/Hydration/Toxicity/Endurance with their **non-CurrentValue** field names — see `STAT_FIELD_MAP`), `update_quest_state`, `update_quest_bool`, `update_quest_int`, `update_item_durability`, `update_item_count` (uses `Count` not `Quantity`), `delete_inventory_item`, `set_hardcore`, `clear_status_effect`, `clear_all_status_effects`, `update_position`, `update_spell_slot`, `clear_spell_slot`, `fill_all_spell_slots`, `add_mount`, `remove_mount`, `equip_mount`, `reveal_full_map`, `hide_full_map`, `repair_all_items`, `_parse_position`, `_format_position`

**`class WorldSave`** — Binary `.sav` files (Dominion engine wrapping UE4 GVAS).
- `load()` — read raw bytes, scan for JSON sections, categorize them, parse difficulty entries
- `_find_json_sections()` — byte-scans for `{` followed by valid JSON, parses 168+ embedded blobs
- `_categorize_sections()` — tags each as `world_events`, `weather`, `station`, `container`, `slot_data`
- `_find_difficulty_entries()` — scans for the byte signature `\x08\x00\x00\x00TagName\x00\x0d\x00\x00\x00NameProperty\x00`, then walks the UE4 NameProperty structure to find each `(GameplayTag, float32)` pair. Records `tag`, `value`, `value_offset` for each.
- `get_header_info()` — file metadata (name, size, timestamp, world name, section count)
- `get_world_events()` — parsed event triggers from `world_events` JSON section
- `get_weather()` — weather definitions per region from the `weather` JSON section
- `get_stations()` — crafting station inventories
- `get_containers(include_empty=False)` — world chests with editable items
- `get_difficulty_settings()` — current entries (with friendly names + hints) and missing tags
- Editing methods: `update_container_item`, `update_weather`, `update_event_trigger`, `disable_all_raids`, `update_difficulty_value` (length-preserving 4-byte float swap)
- `save(backup=True)` — writes `raw_data` back to disk; for each JSON section, replaces in place with **length-preserving** JSON (pads with whitespace inside the JSON, falls back to compact format if grown). Binary edits (difficulty values) live directly in `raw_data` and survive automatically because they're outside any JSON section.

**`discover_saves()`** — Module-level function that finds all character JSONs and world `.sav` files in the default game save directory.

### `app.py` (~270 lines)
Flask web app. Thin layer over `parser.py`.

- Module globals: `characters`, `worlds` dicts holding loaded `CharacterSave` / `WorldSave` instances
- `init_saves()` — populate the dicts via `discover_saves()`

**Routes:**
- `GET /` — render `index.html` with all loaded data (`characters`, `active_char`, `worlds`)
- `GET /api/character/<filename>` — return character summary
- `POST /api/character/<filename>/update` — apply a batch of edit actions (matches on `action` field, dispatches to parser methods)
- `POST /api/character/<filename>/save` — call `cs.save()`
- `POST /api/reload` — re-discover all saves (refreshes in-memory state from disk)
- `GET /api/world/<filename>` — return world data including difficulty
- `POST /api/world/<filename>/update` — batch world edit actions (`container_item`, `weather`, `event_trigger`, `disable_all_raids`, `difficulty_value`)
- `POST /api/world/<filename>/save` — call `ws.save()`

## Templates

### `templates/index.html` (~1600 lines, MONOLITHIC — pending refactor)
Single-page UI. Embedded CSS at the top, Jinja2 templating in the body, JS at the bottom.

**Structure (in this order in the file):**
1. `<head>` with all CSS (RS-themed dark mode palette)
2. Header bar with title, save dir, Reload Files button, Save to Disk button
3. Character selector cards (one per loaded character)
4. Tabs row: Overview / Skills / Inventory / Quests / Spells / More / World Data
5. Tab contents:
   - **Overview:** Vitals (Health, Stamina, Sustenance, etc.), Status Effects panel, Position editor, Character info, Progress, Skills overview, Full Restore button
   - **Skills:** 10 skills with editable XP, MAX button, live XP bar
   - **Inventory:** Loadout (equipment slots) + Inventory grid with stackable/durable distinction, Repair All / Max All Stacks buttons
   - **Quests:** All quests with state dropdown + per-quest expandable variable editor (QuestBools / QuestInts)
   - **Spells:** 48-slot spell loadout with dropdowns from unlocked spells + Fill All / Clear All
   - **More:** Mount manager (equip/remove/add by ID), Map / Fog of War (Reveal Full Map button), Customization read-only display
   - **World Data:** Per-world card with "Load Editable Data" button. Loads weather, events, world chests/containers, crafting stations, AND custom difficulty settings (Phase 1 editor)
6. Toast notification element
7. `<script>` block with all JS:
   - State: `currentFile`, `pendingUpdates`, `isDirty`, `worldDirty`, `XP_TABLE`
   - Helpers: `switchTab`, `selectCharacter`, `showToast`, `markDirty`, `escapeHtml`, `xpToLevel`
   - Character edit queueing: `queueUpdate`, `queueStatUpdate`, `queueSkillUpdate`, `maxSkill`, `queueQuestUpdate`, `queueQuestBool`, `queueQuestInt`, `queueDurabilityUpdate`, `queueCountUpdate`, `queueHardcoreUpdate`, `queuePosition`, `clearEffect`, `clearAllDebuffs`, `fullRestore`, `maxAllStacks`, `queueSpellSlot`, `fillAllSpells`, `clearAllSpells`, `addMount`, `removeMount`, `equipMount`, `revealMap`, `hideMap`, `deleteItem`, `repairAllItems`, `completeAllQuests`
   - World edit functions: `loadWorldDetails` (huge — renders weather/events/containers/difficulty UI), `postWorldUpdate`, `updateContainerItem`, `updateDifficulty`, `updateWeather`, `toggleEventTrigger`, `disableAllRaids`, `saveWorld`
   - `applyUpdates` (POSTs the queue), `saveChanges`, `reloadSaves`

**Refactor target:** Split into separate template partials per tab, extract CSS to `static/style.css`, extract JS to `static/app.js`. Tracked as task #17.

## Documentation

### `SAVE_FORMAT.md` (~510 lines)
Authoritative reference for the save file format.

**Sections:**
- TL;DR table of what we can / can't edit
- File locations and structure
- Character JSON format (`SaveCharacters/*.json`) — every field documented including the gotchas (Sustenance uses `SustenanceValue` not `CurrentValue`, items use `Count` not `Quantity`, position is a string `V(X=..., Y=..., Z=...)`, slots 5-8 of Loadout reference inventory by index)
- Customization data table references
- Inventory/Loadout slot mappings
- Skill ID mappings
- Progress / Quest / Spellcasting / Hardcore structures
- World save format (`SaveGames/*.sav`)
- Section markers and offsets (SAVE, INFO, CINF, GLOB, METAL, VERS, CNIX, CLST, CDVE, CDEF, PNIX, GOBS, NOBJ, PROP, GLAI)
- UE4 property encoding overview
- Embedded JSON section catalog (events, weather, stations, containers)
- World entity types (binary, NOT editable yet)
- Editing strategy (safe/hard/unknown)

### `DIFFICULTY_SETTINGS.md` (~190 lines)
The complete reverse engineering of custom difficulty settings.

**Sections:**
- TL;DR
- How the discovery happened (compared Middle Earth save with Gielinor save)
- Complete list of all 35 difficulty tags grouped by category
- What's NOT in the list and why (gather yields not exposed)
- Binary format (per-entry layout, hex example, float interpretation cheat sheet)
- Confirmed values from Middle Earth save
- Editing strategy: Phase 1 (length-preserving) vs Phase 2 (binary injection)
- Useful difficulty value presets
- True drop rate multipliers (out of scope, requires .pak modding)
- Verification approach

## `.claude/commands/`

Slash commands for the project:

| Command | File | Purpose |
|---------|------|---------|
| `/start-session` | `start-session.md` | Run the start protocol (load context, check git, plan) |
| `/end-session` | `end-session.md` | Run the end protocol (handoff, master index, commit) |

## `docs/`

| Path | Purpose |
|------|---------|
| `docs/handoffs/` | Per-session handoff documents |
| `docs/MASTER_HANDOFF_INDEX.md` | Catalog of all handoffs (one-line summaries, newest first) |

## Runtime / generated (gitignored)

- `venv/` — Python venv with Flask
- `__pycache__/` — Python bytecode cache
- `editor_backups/` — auto-created backups when the editor saves a file (separate from the game's own `.backup` and `.verbackup` files)
