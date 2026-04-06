# RS Dragonwilds Save Editor

A web-based save editor for **RuneScape: Dragonwilds**. Edit characters, inventory, skills, quests, spells, mounts, world chests, weather, and more — all from your browser.

## 🚀 Quick Start (One Click)

**Just double-click `run.bat`** in this folder.

That's it. The script will:
1. Create a Python virtual environment if it doesn't exist
2. Install dependencies (Flask)
3. Start the server
4. Print the URL to open

Then open **http://localhost:5000** in your browser.

To stop the server, close the terminal window (or press `Ctrl+C` inside it).

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

- `run.bat` — One-click launcher (Windows)
- `run.sh` — Launcher for Linux/WSL
- `app.py` — Flask backend
- `parser.py` — Save file parser (read/write logic)
- `templates/index.html` — Web UI
- `CLAUDE.md`, `SAVE_FORMAT.md`, `DIFFICULTY_SETTINGS.md` — Developer/reverse-engineering docs

## ⚖️ Disclaimer

This is an unofficial fan-made tool. Use at your own risk. Always back up your saves (the editor does this automatically, but a manual copy never hurts). Not affiliated with Jagex.
