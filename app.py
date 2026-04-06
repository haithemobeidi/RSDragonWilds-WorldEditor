"""
RS Dragonwilds Save Editor - Flask Web App
"""

import json
import os
from flask import Flask, render_template, request, jsonify
from parser import (
    CharacterSave, WorldSave, discover_saves,
    SKILL_NAMES, XP_TABLE, xp_to_level, level_to_xp,
)

app = Flask(__name__)

SAVE_DIR = None
characters: dict[str, CharacterSave] = {}
worlds: dict[str, WorldSave] = {}

# Static reference catalogs (imported from Ashenfall's Completionist Log XLSX
# via scripts/import_catalog.py — community-sourced reference data)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
catalog: dict = {"quests": [], "items": [], "meta": {}}


def load_catalog():
    """Load reference catalog JSONs into memory. Optional — file may not exist."""
    global catalog
    for key, fname in [("quests", "quests.json"), ("items", "items.json"), ("meta", "catalog_meta.json")]:
        p = os.path.join(DATA_DIR, fname)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    catalog[key] = json.load(f)
            except Exception as e:
                print(f"Failed to load catalog {fname}: {e}")


def init_saves():
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
                           xp_table=XP_TABLE,
                           catalog=catalog)


@app.route("/api/catalog")
def get_catalog():
    """Return the full reference catalog (quests + items + meta)."""
    return jsonify(catalog)


@app.route("/api/character/<filename>")
def get_character(filename):
    cs = characters.get(filename)
    if not cs:
        return jsonify({"error": "Character not found"}), 404
    return jsonify(cs.get_summary())


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

            elif action == "max_all_skills":
                count = cs.max_all_skills()
                results.append({"ok": True, "action": action, "count": count})
                continue

            elif action == "health":
                cs.update_health(update["value"])

            elif action == "stamina":
                cs.update_stamina(update["value"])

            elif action == "stat":
                cs.update_stat(update["stat"], update["value"])

            elif action == "quest_state":
                cs.update_quest_state(update["quest_id"], update["state"])

            elif action == "complete_all_quests":
                quests = cs.data.get("QuestProgress", {}).get("Quests", [])
                for q in quests:
                    q["QuestState"] = 2
                results.append({"ok": True, "action": action, "count": len(quests)})
                continue

            elif action == "item_durability":
                ok = cs.update_item_durability(update["slot"], update["durability"], update.get("source", "Inventory"))
                if not ok:
                    results.append({"ok": False, "action": action, "error": "Item not found or not durable"})
                    continue

            elif action == "item_count":
                ok = cs.update_item_count(update["slot"], update["count"], update.get("source", "Inventory"))
                if not ok:
                    results.append({"ok": False, "action": action, "error": "Item not found or not stackable"})
                    continue

            elif action == "delete_item":
                cs.delete_inventory_item(update["slot"])

            elif action == "repair_all":
                count = cs.repair_all_items(update.get("durability", 9999))
                results.append({"ok": True, "action": action, "count": count})
                continue

            elif action == "hardcore":
                cs.set_hardcore(update["enabled"])

            elif action == "clear_status_effect":
                cs.clear_status_effect(update["effect"])

            elif action == "clear_all_status_effects":
                cleared = cs.clear_all_status_effects()
                results.append({"ok": True, "action": action, "cleared": cleared})
                continue

            elif action == "position":
                cs.update_position(update["x"], update["y"], update["z"])

            elif action == "full_restore":
                cs.update_health(100)
                cs.update_stamina(100)
                cs.update_stat("Sustenance", 100)
                cs.update_stat("Hydration", 100)
                cs.update_stat("Toxicity", 0)
                cs.update_stat("Endurance", 100)
                cs.clear_all_status_effects()
                results.append({"ok": True, "action": action})
                continue

            elif action == "spell_slot":
                cs.update_spell_slot(int(update["slot"]), update.get("spell_id", ""))

            elif action == "fill_all_spell_slots":
                cs.fill_all_spell_slots(update["spell_id"])

            elif action == "add_mount":
                cs.add_mount(update["mount_id"])

            elif action == "remove_mount":
                cs.remove_mount(update["mount_id"])

            elif action == "equip_mount":
                cs.equip_mount(update.get("mount_id", "None"))

            elif action == "quest_bool":
                cs.update_quest_bool(update["quest_id"], update["var_name"], update["value"])

            elif action == "quest_int":
                cs.update_quest_int(update["quest_id"], update["var_name"], update["value"])

            elif action == "reveal_map":
                cs.reveal_full_map()

            elif action == "hide_map":
                cs.hide_full_map()

            elif action == "char_type":
                cs.set_char_type(int(update["value"]))

            else:
                results.append({"ok": False, "error": f"Unknown action: {action}"})
                continue

            results.append({"ok": True, "action": action})

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
        "weather": ws.get_weather(),
        "stations": ws.get_stations(),
        "containers": ws.get_containers(),
        "difficulty": ws.get_difficulty_settings(),
    })


@app.route("/api/world/<filename>/update", methods=["POST"])
def update_world(filename):
    ws = worlds.get(filename)
    if not ws:
        return jsonify({"error": "World not found"}), 404

    updates = request.json
    results = []

    for update in updates:
        action = update.get("action")
        try:
            if action == "container_item":
                ok = ws.update_container_item(
                    update["section_index"],
                    update["slot"],
                    update["field"],
                    update["value"],
                )
                results.append({"ok": ok, "action": action})

            elif action == "weather":
                ok = ws.update_weather(
                    update["weather_name"],
                    update.get("type"),
                    update.get("remaining_time"),
                )
                results.append({"ok": ok, "action": action})

            elif action == "event_trigger":
                ok = ws.update_event_trigger(
                    update["event_name"],
                    update["trigger_name"],
                    active=update.get("active"),
                    trigger_time=update.get("trigger_time"),
                )
                results.append({"ok": ok, "action": action})

            elif action == "disable_all_raids":
                count = ws.disable_all_raids()
                results.append({"ok": True, "action": action, "count": count})

            elif action == "difficulty_value":
                ok = ws.update_difficulty_value(update["tag"], float(update["value"]))
                results.append({"ok": ok, "action": action, "tag": update.get("tag")})

            elif action == "convert_to_custom":
                ok = ws.convert_to_custom()
                results.append({"ok": ok, "action": action, "new_mode": ws.get_world_mode()})

            elif action == "revert_to_standard":
                ok = ws.revert_to_standard()
                results.append({"ok": ok, "action": action, "new_mode": ws.get_world_mode()})

            else:
                results.append({"ok": False, "error": f"Unknown action: {action}"})

        except Exception as e:
            results.append({"ok": False, "action": action, "error": str(e)})

    return jsonify({"results": results})


@app.route("/api/world/<filename>/save", methods=["POST"])
def save_world(filename):
    ws = worlds.get(filename)
    if not ws:
        return jsonify({"error": "World not found"}), 404

    try:
        result = ws.save(backup=True)
        return jsonify({
            "ok": True,
            "message": f"Saved {filename} (backup created)",
            "warnings": result.get("warnings", []),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("RS Dragonwilds Save Editor")
    print("=" * 40)
    init_saves()
    load_catalog()
    print(f"\nLoaded {len(characters)} characters, {len(worlds)} worlds")
    print(f"Catalog: {len(catalog['quests'])} quests, {len(catalog['items'])} items")
    print(f"Save directory: {SAVE_DIR}")
    print(f"\nStarting web server at http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    app.run(debug=True, host="127.0.0.1", port=5000)
