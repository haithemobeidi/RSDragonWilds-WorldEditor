"""
RS Dragonwilds Save Editor - Flask Web App
"""

import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from parser import CharacterSave, WorldSave, discover_saves, SKILL_NAMES, xp_to_level, level_to_xp, XP_TABLE

app = Flask(__name__)

# Global state
SAVE_DIR = None
characters: dict[str, CharacterSave] = {}
worlds: dict[str, WorldSave] = {}


def init_saves():
    """Discover and load all saves."""
    global SAVE_DIR
    saves = discover_saves()
    SAVE_DIR = saves.get("base_path", "")

    characters.clear()
    worlds.clear()

    for c in saves.get("characters", []):
        try:
            cs = CharacterSave(c["filepath"])
            cs.load()
            characters[c["filename"]] = cs
        except Exception as e:
            print(f"Failed to load {c['filename']}: {e}")

    for w in saves.get("worlds", []):
        try:
            ws = WorldSave(w["filepath"])
            ws.load()
            worlds[w["filename"]] = ws
        except Exception as e:
            print(f"Failed to load {w['filename']}: {e}")


@app.route("/")
def index():
    selected = request.args.get("char", "")

    char_summaries = []
    for fname, cs in characters.items():
        summary = cs.get_summary()
        summary["_filename"] = fname
        char_summaries.append(summary)

    # Pick the active character
    active_char = None
    for s in char_summaries:
        if s["_filename"] == selected:
            active_char = s
            break
    if active_char is None and char_summaries:
        active_char = char_summaries[0]

    world_infos = []
    for fname, ws in worlds.items():
        info = ws.get_header_info()
        world_infos.append(info)

    return render_template("index.html",
                           characters=char_summaries,
                           active_char=active_char,
                           worlds=world_infos,
                           save_dir=SAVE_DIR,
                           skill_names=SKILL_NAMES,
                           xp_table=XP_TABLE)


@app.route("/api/character/<filename>")
def get_character(filename):
    cs = characters.get(filename)
    if not cs:
        return jsonify({"error": "Character not found"}), 404
    return jsonify(cs.get_summary())


@app.route("/api/character/<filename>/raw")
def get_character_raw(filename):
    cs = characters.get(filename)
    if not cs:
        return jsonify({"error": "Character not found"}), 404
    return jsonify(cs.data)


@app.route("/api/character/<filename>/update", methods=["POST"])
def update_character(filename):
    cs = characters.get(filename)
    if not cs:
        return jsonify({"error": "Character not found"}), 404

    updates = request.json
    results = []

    for update in updates:
        action = update.get("action")
        try:
            if action == "skill_xp":
                cs.update_skill_xp(update["skill_id"], update["xp"])
                results.append({"ok": True, "action": action, "skill": update["skill_id"]})

            elif action == "health":
                cs.update_health(update["value"])
                results.append({"ok": True, "action": action})

            elif action == "stamina":
                cs.update_stamina(update["value"])
                results.append({"ok": True, "action": action})

            elif action == "stat":
                cs.update_stat(update["stat"], update["value"])
                results.append({"ok": True, "action": action, "stat": update["stat"]})

            elif action == "quest_state":
                cs.update_quest_state(update["quest_id"], update["state"])
                results.append({"ok": True, "action": action})

            elif action == "item_durability":
                cs.update_item_durability(update["slot"], update["durability"], update.get("source", "Inventory"))
                results.append({"ok": True, "action": action})

            elif action == "item_quantity":
                cs.update_item_quantity(update["slot"], update["quantity"])
                results.append({"ok": True, "action": action})

            elif action == "delete_item":
                cs.delete_inventory_item(update["slot"])
                results.append({"ok": True, "action": action})

            elif action == "hardcore":
                cs.set_hardcore(update["enabled"])
                results.append({"ok": True, "action": action})

            else:
                results.append({"ok": False, "error": f"Unknown action: {action}"})

        except Exception as e:
            results.append({"ok": False, "action": action, "error": str(e)})

    return jsonify({"results": results})


@app.route("/api/character/<filename>/save", methods=["POST"])
def save_character(filename):
    cs = characters.get(filename)
    if not cs:
        return jsonify({"error": "Character not found"}), 404

    try:
        cs.save(backup=True)
        return jsonify({"ok": True, "message": f"Saved {filename} (backup created)"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/reload", methods=["POST"])
def reload_saves():
    init_saves()
    return jsonify({"ok": True, "characters": len(characters), "worlds": len(worlds)})


@app.route("/api/world/<filename>")
def get_world(filename):
    ws = worlds.get(filename)
    if not ws:
        return jsonify({"error": "World not found"}), 404

    return jsonify({
        "info": ws.get_header_info(),
        "events": ws.get_world_events(),
        "stations": ws.get_stations()[:20],
        "containers": ws.get_containers()[:20],
    })


@app.route("/api/xp_table")
def get_xp_table():
    return jsonify({
        "table": XP_TABLE,
        "skill_names": SKILL_NAMES,
    })


if __name__ == "__main__":
    print("RS Dragonwilds Save Editor")
    print("=" * 40)
    init_saves()
    print(f"\nLoaded {len(characters)} characters, {len(worlds)} worlds")
    print(f"Save directory: {SAVE_DIR}")
    print(f"\nStarting web server at http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    app.run(debug=True, host="127.0.0.1", port=5000)
