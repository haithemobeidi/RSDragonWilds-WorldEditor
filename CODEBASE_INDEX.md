# Codebase Index

A file-by-file map of the RS Dragonwilds Save Editor project. Read this with the latest handoff in `docs/handoffs/` to know exactly where everything lives.

## Top-level files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project overview, tech stack, file locations, dev guidelines, current status |
| `README.md` | End-user-facing setup guide and feature list (one-click run.bat instructions) |
| `QUICK_REFERENCE.md` | Cheat sheet for save flags (char_type, world mode bytes, conversion recipes) |
| `BUGS.md` | Known bugs tracker — format: ID, severity, status, root cause hypothesis, fix plan |
| `SESSION_PROTOCOLS.md` | Mandatory start/work/end session protocols |
| `SAVE_FORMAT.md` | Reverse-engineered save file format reference (character JSON + world binary) |
| `DIFFICULTY_SETTINGS.md` | Reverse-engineered notes on the custom difficulty system, all 35 known tags, binary layout, secondary copy structure |
| `CODEBASE_INDEX.md` | This file |
| `requirements.txt` | Python deps: `flask>=3.0`, `openpyxl` (for XLSX import) |
| `run.sh` / `run.bat` | Launch helpers (creates venv if missing, starts Flask server) |
| `.gitignore` | Excludes `venv/`, `__pycache__/`, `editor_backups/`, `research_backups/` |

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
- `get_summary()` — flatten all data for the UI (skills, quests, inventory, status effects, position parsed from `V(X=..., Y=..., Z=...)` string format, etc.). Includes `meta.char_type`.
- Editing methods: `update_skill_xp`, `max_all_skills`, `update_health`, `update_stamina`, `update_stat` (handles Sustenance/Hydration/Toxicity/Endurance with their **non-CurrentValue** field names — see `STAT_FIELD_MAP`), `update_quest_state`, `update_quest_bool`, `update_quest_int`, `update_item_durability`, `update_item_count` (uses `Count` not `Quantity`), `delete_inventory_item`, `set_hardcore`, `clear_status_effect`, `clear_all_status_effects`, `update_position`, `update_spell_slot`, `clear_spell_slot`, `fill_all_spell_slots`, `add_mount`, `remove_mount`, `equip_mount`, `reveal_full_map`, `hide_full_map`, `repair_all_items`, `set_char_type` (controls custom-world access — 0=standard, 3=custom)

**`class WorldSave`** — Binary `.sav` files (Dominion engine wrapping UE4 GVAS).
- `load()` — read raw bytes, scan for JSON sections, categorize them, parse difficulty entries
- `_find_json_sections()` — byte-scans for `{` followed by valid JSON, parses 168+ embedded blobs
- `_categorize_sections()` — tags each as `world_events`, `weather`, `station`, `container`, `slot_data`
- `_find_difficulty_entries()` — ⚠️ Currently targets the WRONG location (named TagName/NameProperty entries which the game doesn't read). Needs rewrite to target the L_World+17 secondary copy floats.
- `_find_mode_byte_offsets()` — Returns (l_world+9 offset, CustomDifficultySettings PROP byte offset) for world mode bytes
- `get_world_mode()` — Returns 'standard', 'custom', or 'mixed/unknown' based on both mode bytes
- `convert_to_custom()` — Sets both mode bytes to 3/0x03 (one-shot conversion). Caller must call `save()` afterward.
- `revert_to_standard()` — Sets both mode bytes back to 0/0x00.
- `get_header_info()` — file metadata (name, size, timestamp, world name, section count, **world_mode**)
- `get_world_events()` — parsed event triggers from `world_events` JSON section
- `get_weather()` — weather definitions per region from the `weather` JSON section
- `get_stations()` — crafting station inventories
- `get_containers(include_empty=False)` — world chests with editable items
- `get_difficulty_settings()` — current entries (with friendly names + hints) and missing tags
- `get_placed_pieces()` — **CROSS-WORLD-PORTABLE parser for the `Pces` chunk** (added 04-07-2026 PM3). Walks the Dragonwilds-custom `Pces` chunk, identifies each placed structure record by the pattern (FString-length-23 + 3 doubles position + 3 floats extras + uint32 ref_count), extracts per-piece `persistent_id`, class GUID (base64 string), position vec3, rotation in degrees, extras, and ref_count. **Verified on test corpus (0/3/45 pieces for A/D/E) and real Gielinor save (318 pieces, 35 distinct classes, 7 ash chests matching user's memory, 86 cabin walls, 40 floor tiles).** This is the authoritative source for detected built structures — use this over `get_placed_structures()` for cross-world work. The `Pces` chunk is Dragonwilds-custom, not a SPUD primitive, but lives inside the SPUD-managed `L_World` LEVL chunk.
- `KNOWN_STRUCTURES` — class table for placed-actor detection. **Cross-world portable signature** (verified 04-07-2026 against Gielinor): matches by `body_length` + `component_count` (uint32 at offset 0x4d, after the constant 9-byte property header `01 0a 02 00 00 f9 03 00 00` at offset 0x44). Class-table indices that follow the count are world-local and intentionally ignored. Currently knows: Personal Chest (589 B, 3 components) and Ash Chest (625 B, 5 components). Add more building types by capturing one specimen and noting its body length + component count.
- `PROPERTY_HEADER_PREFIX`, `PROPERTY_HEADER_OFFSET`, `COMPONENT_COUNT_OFFSET` — module constants used by the portable detector
- `get_placed_structures()` — walks every `SPWN` chunk in `raw_data`, matches against `KNOWN_STRUCTURES` using the cross-world-portable signature (length + component count + constant header), returns list with `spwn_offset`, `body_length`, `class_name`, `display_name`, `instance_guid_hex`, `position` (vec3 from 6 doubles at offset 0x14), `transform_extra` (last 3 doubles), and `raw_record_hex`. **Verified cross-world**: detects fresh empty Ash Chest in both DiffTest AND Gielinor (different worlds with different CDEF/CNIX layouts) with zero false positives.
- Editing methods: `update_container_item`, `update_weather`, `update_event_trigger`, `disable_all_raids`, `update_difficulty_value` (still broken — wrong location), `convert_to_custom`, `revert_to_standard`
- `save(backup=True)` — writes `raw_data` back to disk; for each JSON section, replaces in place with **length-preserving** JSON. Binary edits (mode bytes, difficulty floats) live directly in `raw_data` and survive automatically.

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

## Templates (refactored 2026-04-06 — was a 1743-line monolith)

### `templates/index.html` (62 lines — shell only)
Entry point. Contains: `<head>` with CSS/font `<link>`s, header bar, char selector include, tabs row, tab partial includes, toast element, JS `<script>` tags. Server-rendered globals (`currentFile`, `XP_TABLE`) set inline before JS loads.

### `templates/partials/*.html` (8 files, 17-196 lines each)
| Partial | Purpose |
|---------|---------|
| `_char_selector.html` | Character card grid at the top |
| `tab_overview.html` | Vitals, char info, status effects, position, progress, skills overview, Full Restore |
| `tab_skills.html` | Editable skills table with XP bars and MAX buttons |
| `tab_inventory.html` | Loadout + inventory grid (stackable/gear split) |
| `tab_quests.html` | Quest list with state dropdowns and per-quest variable editors |
| `tab_spells.html` | 48-slot spell loadout with Fill All / Clear All |
| `tab_more.html` | Mounts, Map/Fog, Customization read-only |
| `tab_world.html` | Per-world cards with load/save buttons + World Mode Conversion controls |
| `tab_database.html` | Reference catalog browser (items + quests from the XLSX) |

## Static assets

### `static/css/` (5 files)
| File | Purpose |
|------|---------|
| `base.css` | CSS variables, body, layout containers, grid |
| `components.css` | Buttons, cards, inputs, stat rows, badges, toast, char selector |
| `tabs.css` | Tab layout + per-tab specific styles (skill rows, quest rows, inv slots, events) |
| `database.css` | Database tab styles (grid, cards with icons, search controls, type tags) |
| `theme.css` | **RSDW game-style override layer.** Fantasy-serif fonts (Cinzel + EB Garamond), warmer dark-amber palette, aggressive `!important` font-size overrides for readability. Layered LAST so it overrides the base CSS. |

### `static/js/` (5 files)
| File | Purpose |
|------|---------|
| `api.js` | DRY HTTP helpers: `apiPost(url, body)`, `apiGet(url)` — one place for fetch boilerplate + error handling |
| `core.js` | Global state, UI primitives (`switchTab`, `showToast`, `markDirty`, `escapeHtml`, `xpToLevel`), `applyUpdates`, `saveChanges`, `reloadSaves` |
| `character.js` | All character editing queue functions (skills, vitals, inventory, quests, spells, mounts, map, char_type) |
| `world.js` | World data loading, per-section render helpers (`renderDifficultySection`, `renderWeatherSection`, etc), world edit actions, mode conversion |
| `database.js` | Reference database tab — load catalog, render item/quest cards with icons, live search filter |

### `static/images/items/` — 159 PNG files
Wiki-sourced item icons (256×256). Downloaded by `scripts/fetch_icons.py`. Referenced by `data/icon_map.json` which is merged into `data/items.json` at app startup.

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

## `data/`

Reference catalogs imported from external sources. Generated by scripts in `scripts/`. All files checked into git — small enough and give a working out-of-the-box experience.

| File | Purpose |
|------|---------|
| `quests.json` | All known quests (22). Imported from Ashenfall's Completionist Log. Has title, type, region, sub-region, start NPC, reward info. |
| `items.json` | All known items (197). Imported from same source. Has display name, vestige name, type, sub-type, region, source (chest/drop/etc), soul fragment cost (where applicable). |
| `catalog_meta.json` | Versioning info — source, import date, counts, notes |
| `icon_map.json` | Per-item icon fetch results — each entry has status, queried name, resolved wiki title, image URL, local path. Used by `app.load_catalog()` to merge icon paths into items. |
| `icon_manual_overrides.json` | Map of `item_id → wiki_title` for fixing XLSX typos (e.g. L003 "Leggins" → "Leggings Of Lightness"). Consumed by `scripts/fetch_icons.py`. |

**Important:** these catalogs use community IDs (MQ01, L001) NOT the game's internal GUIDs. The Database tab in the editor uses them as a browse-only reference. Auto-linking save data to catalog entries is **Phase 2** — would require extracting `.pak` files for the GUID→name mapping.

## `scripts/`

Standalone utilities not part of the Flask app.

| File | Purpose |
|------|---------|
| `flip_gielinor_custom.py` | One-shot CLI to convert Gielinor.sav between Standard and Custom mode. Has `--revert` flag. Auto-detects file location. Built-in backups per standing rule. |
| `import_catalog.py` | Reads the Ashenfall Completionist Log XLSX and writes `data/quests.json` + `data/items.json` + `data/catalog_meta.json`. Re-run when the source XLSX is updated. |
| `fetch_icons.py` | Scrapes item icons from the RS Dragonwilds wiki via MediaWiki API. Direct `pageimages` lookup → search fallback → manual override support. Polite rate limit (0.5s). Resumable cache in `icon_map.json`. Downloads PNGs to `static/images/items/`. Usage: `python scripts/fetch_icons.py [--limit N] [--force]`. |

### `scripts/structure_research/`
Reverse-engineering corpus + diff scripts for the **placed-structure transplant feature** (started 04-07-2026). Established the binary layout of `SPWN`+`PROP` actor records by diffing three same-world snapshots.

| File | Purpose |
|------|---------|
| `README.md` | Full notes on the chunked save format (`SAVE`/`INFO`/`CINF`/`GLOB`/`CNIX`/`PNIX`/`CDEF`/`CDVE`/`LVLS`/`SPWN`/`PROP`/`Pces`/`SATS`/`CORA` chunk tags), the SPWN record layout, the chest schema strings, and **the root cause of bug #001** (chests carry `OwnerCharacterGuid` baked in — converting world owner orphans them) |
| `A.sav` | Empty test world (no player builds) — 201,105 B, 15 baseline SPWN records (system entities — NOT trees/rocks; world props are seed-generated, not serialized) |
| `B.sav` | A + 1 Personal Chest in front of church — 202,805 B, 16 SPWN records |
| `C.sav` | B + 1 more Personal Chest near tent — 203,588 B, 17 SPWN records |
| `D_with_ash_chest.sav` | C + 1 Ash Chest — 205,088 B, 18 SPWN records (introduced the second known structure class) |
| `diff.py` | Naive prefix/suffix diff (failed — too noisy because byte insertions reshuffle offset tables) |
| `diff2.py` | String-counter diff that revealed the chest schema strings (BP_BaseBuilding_PersonalChest_C, BuildingPieceID, OwnerCharacterGuid, etc.) |
| `diff3.py` | Chunk-tag locator that mapped the entire file format |
| `diff4.py` | SPWN record extractor with bytewise novelty detection |
| `diff5.py` | Float interpretation of diff between two SPWN records (false-positive — was diffing trees, not chests) |
| `diff6.py` | SPWN class-ref signature analyzer (revealed chests are 589 bytes with `17 00 00 00` first4, NOT 590 bytes) |
| `diff7.py` | Diff of the *actual* chest records — proved same chest in two saves of same world differs by only 2 tick/hash bytes |
| `diff8.py` | Diff of D vs C to capture the Ash Chest's class-ref signature for `KNOWN_STRUCTURES` |
| `diff9.py` | Diff of D vs E Pces chunks — revealed the per-record FString layout and constant class GUIDs |
| `diff10.py` | First Pces record parser attempt — succeeded for chests and first 14 cabin records, failed at gap-indexed records (abandoned; see diff12 for the working approach) |
| `diff11.py` | FString-23 scanner — lists every length-prefixed 23-byte string in the Pces body and what precedes it |
| `diff12.py` | **Position-validated record extractor** — the working approach. Scans for FString-23 followed by a plausible (in-range) position vec3 + plausible ref_count, which uniquely identifies "main piece records" vs "ref GUIDs". Detected all 45 pieces in E. The logic from this is what got promoted into `parser.py`'s `get_placed_pieces()`. |
| `transplant_test.py` | **First (failed) surgical transplant attempt** — injected one cabin wall's 143 bytes into Middle Eearth's Pces with chunk-length fixups. Game loaded the file but the wall didn't instantiate because the piece's sibling NOBJ/PROP/CORA records weren't also injected. Useful as a reference for the eventual surgical transplant implementation. |

## `docs/`

| Path | Purpose |
|------|---------|
| `docs/handoffs/` | Per-session handoff documents (one per session, timestamped filename) |
| `docs/MASTER_HANDOFF_INDEX.md` | Catalog of all handoffs (one-line summaries, newest first) |

## Runtime / generated (gitignored)

- `venv/` — Python venv with Flask + openpyxl
- `__pycache__/` — Python bytecode cache
- `editor_backups/` — auto-created backups when the editor saves a file (separate from the game's own `.backup` and `.verbackup` files)
- `research_backups/` — pristine save files + original pre-refactor code (load-bearing safety net for experimentation — don't delete)
