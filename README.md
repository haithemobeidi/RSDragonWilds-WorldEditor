# RS Dragonwilds Save Editor

A web-based save editor for **RuneScape: Dragonwilds**. Edit characters, inventory, skills, quests, spells, mounts, world chests, weather, and more — all from your browser.

**Two apps in this repo:**

1. **`app.py`** — the **main editor** (port **5000**) — character editing, inventory, quests, world JSON sections, the Database tab, etc.
2. **`world_editor.py`** — a **focused world editor** (port **5001**) — dedicated to binary world `.sav` operations: list placed structures, transplant buildings between worlds, clone worlds, toggle world mode

The two apps can run at the same time. Pick whichever fits your task.

---

## 🚀 Quick Start — Main Editor (One Click on Windows)

**Just double-click `run.bat`** in this folder.

That's it. The script will:
1. Create a Python virtual environment if it doesn't exist
2. Install dependencies (Flask)
3. Start the server
4. Print the URL to open

Then open **http://localhost:5000** in your browser.

To stop the server, close the terminal window (or press `Ctrl+C` inside it).

---

## 🏗️ Quick Start — Focused World Editor

The world editor is a separate, simpler UI dedicated to **binary `.sav` editing** — listing placed buildings, copying structures between worlds, cloning worlds, and toggling world mode. It's the right tool if you want to **move a cabin between two worlds** or duplicate a world to a new save slot.

### Run from a terminal

**Windows (cmd or PowerShell):**
```
cd path\to\RSDragonwildsSaveEditor
venv\Scripts\activate
python world_editor.py
```

**WSL or Linux:**
```bash
cd /path/to/RSDragonwildsSaveEditor
source venv/bin/activate
python3 world_editor.py
```

(If `venv/` doesn't exist yet, run `python -m venv venv` first, then `pip install -r requirements.txt` after activating.)

### What you'll see

The terminal prints something like:
```
============================================================
RS Dragonwilds World Editor
============================================================
Open: http://localhost:5001
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
 * Running on http://172.21.15.198:5001    ← WSL bridge address
```

**Open `http://localhost:5001` in your browser.**

If `localhost` doesn't work (rare on WSL2), try `http://127.0.0.1:5001` or the WSL bridge IP from the terminal output (the third URL).

### Features

- 📋 **World list** with piece counts, mode, and file size for each world
- 📊 **Per-world details** — full piece breakdown with friendly names where known
- 🔀 **Copy buildings INTO this world** — pick a donor world, click button, all walls/floors/roofs are copied across
- 📑 **Clone World** — duplicate any world with a new name and a fresh `WorldSaveGuid` (both saves coexist)
- ⚙️ **Set World Mode** — toggle Standard ↔ Custom

Every destructive action **auto-creates a timestamped backup** in `editor_backups/` next to the original file. Always close the game first.

### What works and what doesn't (transplant)

| Type | Result |
|---|---|
| Walls, floors, roofs, doorframes | ✅ Works fully |
| Doors (the swinging kind) | ⚠️ Visible but no collision (you walk through them) |
| Water barrels | ⚠️ Visible but no collision |
| Farming plots | ⚠️ Visible, partially functional (can be dug) |
| Chests, anvils, rune altars, crafting stations, "machines" | ❌ Silently dropped — these need additional work to transplant |

This is the **Category 1 vs Category 2** distinction documented in `docs/DRAGONWILDS_SAVE_FORMAT_GUIDE.md`. Pure mesh pieces work; stateful actors don't yet. See the guide for the technical details.

### Troubleshooting the world editor

**"Site can't be reached" / "Connection refused"** — The server isn't running. Start it with `python world_editor.py` from the project directory and leave that terminal open.

**"Failed to fetch" in the browser** — The server is bound to the wrong interface. Make sure you're running the latest version (it should print `Running on all addresses (0.0.0.0)`). If you see `Running on http://127.0.0.1:5001` only, your file is outdated — `git pull` and try again.

**"No module named 'flask'"** — You forgot to activate the virtual environment. Run `source venv/bin/activate` (Linux/WSL) or `venv\Scripts\activate` (Windows) first.

**"Port 5001 already in use"** — Another instance of `world_editor.py` is still running, or something else is on port 5001. Find and kill it, or close the other instance.

---

## ⚠️ Before You Edit Anything

1. **CLOSE THE GAME COMPLETELY** before editing any save file. The game holds locks and caches state in memory — editing while it's running will not work and may corrupt files.
2. The editor **auto-backs up** every save before writing — backups go to `editor_backups/` next to the original file. You can always restore.

## 📋 Requirements

- **Windows** with Python 3.10+ installed and on your PATH
- A web browser (Chrome, Edge, Firefox — anything modern)
- RS Dragonwilds save files in the default location:
  ```
  %LOCALAPPDATA%\RSDragonwilds\Saved\
  ```

If you don't have Python: install it from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH" during install.

## 🎯 What You Can Edit

### Characters (`SaveCharacters\*.json`)
- **Vitals** — Health, Stamina, Sustenance, Hydration, Toxicity, Endurance
- **Skills** — All 10 skills' XP, with one-click MAX buttons
- **Inventory** — Item durability, stack counts, delete items, "Repair All" / "Max Stacks"
- **Loadout** — Equipped gear durability
- **Quests** — Toggle state, edit individual quest variables, "Complete All Quests"
- **Status Effects** — Clear Cold, Poison, Burning, Bleeding, Slow, Wither
- **Position** — Teleport via X/Y/Z coords
- **Spells** — Edit all 48 spell slots, "Fill All" with selected spell
- **Mounts** — List/equip/remove/add by ID
- **Map** — "Reveal Full Map" (clear all fog of war)
- **Hardcore mode** toggle
- **"Full Restore"** — heal all vitals + clear all debuffs in one click

### Worlds (`SaveGames\*.sav`)
- **89 World Storage Containers** — edit chest contents
- **Weather** — change type and remaining time per region
- **24 World Events** — toggle raids/ambushes, "Disable All Raids"
- **Custom Difficulty Settings** *(Phase 1 — file-level edit works, in-game effect under investigation)*

## 🛟 Restoring a Backup

Every save creates a timestamped copy in `editor_backups/` next to the original:
```
%LOCALAPPDATA%\RSDragonwilds\Saved\SaveCharacters\editor_backups\
```

Just rename the backup back to the original filename if you need to roll back.

## 🐛 Troubleshooting

**"Python is not recognized"** — Install Python from python.org and check "Add Python to PATH".

**"Port 5000 already in use"** — Another app (or another instance of this editor) is using port 5000. Close it, or edit `app.py` to change the port.

**Edit doesn't appear in-game** — Did you close the game *before* editing? The game caches state in memory and overwrites the file on quit.

**"No saves found"** — The editor looks in `%LOCALAPPDATA%\RSDragonwilds\Saved\`. If your saves are elsewhere, the path is configured at the top of `parser.py`.

## 📁 Project Files

- `run.bat` — One-click launcher for the main editor (Windows)
- `run.sh` — Launcher for Linux/WSL
- `app.py` — Main editor Flask backend (port 5000)
- `world_editor.py` — Focused world editor Flask backend (port 5001) — see [Quick Start](#-quick-start--focused-world-editor-) above
- `parser.py` — Save file parser (read/write logic)
- `templates/index.html` — Main editor web UI
- `templates/world_editor.html` — Focused world editor web UI
- `scripts/structure_research/` — Reverse-engineering scripts and test corpus for the binary world format research
- `docs/DRAGONWILDS_SAVE_FORMAT_GUIDE.md` — Developer guide for the binary world `.sav` format (for modders / contributors)
- `CLAUDE.md`, `SAVE_FORMAT.md`, `DIFFICULTY_SETTINGS.md` — Reverse-engineering notes and project context

## ⚖️ Disclaimer

This is an unofficial fan-made tool. Use at your own risk. Always back up your saves (the editor does this automatically, but a manual copy never hurts). Not affiliated with Jagex.
