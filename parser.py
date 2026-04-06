"""
RS Dragonwilds Save File Parser
Parses character JSON files and world .sav files from the Dominion Engine.

Save data locations:
  - Characters: AppData/Local/RSDragonwilds/Saved/SaveCharacters/*.json
  - World data: AppData/Local/RSDragonwilds/Saved/SaveGames/*.sav
"""

import json
import os
import shutil
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


# Known skill IDs mapped to names
SKILL_NAMES = {
    "Wf3i7Ha-B06DH719j1vtBw": "Mining",
    "4pefO9k1lUqfA6mvHNi1SA": "Woodcutting",
    "waK-8EyQFQ2xEjCGYmuTRQ": "Fishing",
    "Tn7t6DQyX0-Q0cM5K7B90A": "Smithing",
    "0hreSMRVXUihq9qjDO2CFA": "Runecrafting",
    "jqX0Gh6QI0GFFPCDFK_CJQ": "Cooking",
    "heq7u88Q2UuLXFqLGTVwQw": "Farming",
    "NOqC-z-2ckqi0El22qMFlw": "Fletching",
    "4zYUGF5u_0KbMLkWJmmBbQ": "Crafting",
    "PyUi-0LU_riFY46AnnFiWg": "Pottery",
}

# XP thresholds per level (RS-style curve)
XP_TABLE = [
    0, 0, 83, 174, 276, 388, 512, 650, 801, 969, 1154,
    1358, 1584, 1833, 2107, 2411, 2746, 3115, 3523, 3973, 4470,
    5018, 5624, 6291, 7028, 7842, 8740, 9730, 10824, 12031, 13363,
    14833, 16456, 18247, 20224, 22406, 24815, 27473, 30408, 33648, 37224,
    41171, 45529, 50339, 55649, 61512, 67983, 75127, 83014, 91721, 101333,
]


def xp_to_level(xp: int) -> int:
    for i in range(len(XP_TABLE) - 1, -1, -1):
        if xp >= XP_TABLE[i]:
            return i
    return 1


def level_to_xp(level: int) -> int:
    if level < 0:
        return 0
    if level >= len(XP_TABLE):
        return XP_TABLE[-1]
    return XP_TABLE[level]


@dataclass
class JsonSection:
    """A JSON blob embedded in the world save file."""
    offset: int
    length: int
    data: dict | list
    category: str = "unknown"


class CharacterSave:
    """Parser for character JSON save files."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: dict = {}
        self.filename = os.path.basename(filepath)

    def load(self):
        with open(self.filepath, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def save(self, output_path: Optional[str] = None, backup: bool = True):
        if output_path is None:
            output_path = self.filepath

        if backup and os.path.exists(output_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(output_path), "editor_backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{self.filename}.{timestamp}.bak")
            shutil.copy2(output_path, backup_path)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent="\t", ensure_ascii=False)

    def get_summary(self) -> dict:
        d = self.data
        character = d.get("Character", {})
        skills_raw = d.get("Skills", {}).get("Skills", [])

        skills = []
        for s in skills_raw:
            sid = s.get("Id", "")
            xp = s.get("Xp", 0)
            name = SKILL_NAMES.get(sid, f"Unknown ({sid[:12]})")
            level = xp_to_level(xp)
            xp_current_level = XP_TABLE[level] if level < len(XP_TABLE) else 0
            xp_next_level = XP_TABLE[level + 1] if level + 1 < len(XP_TABLE) else XP_TABLE[-1]
            xp_range = max(1, xp_next_level - xp_current_level)
            xp_pct = min(100, ((xp - xp_current_level) / xp_range) * 100)
            skills.append({
                "id": sid, "name": name, "xp": xp, "level": level,
                "xp_pct": round(xp_pct, 1),
                "xp_next": xp_next_level if level + 1 < len(XP_TABLE) else "MAX",
            })

        quests = []
        state_names = {0: "Not Started", 1: "In Progress", 2: "Completed"}
        for q in d.get("QuestProgress", {}).get("Quests", []):
            quests.append({
                "id": q.get("QuestId", ""),
                "state": q.get("QuestState", 0),
                "state_name": state_names.get(q.get("QuestState", 0), "Unknown"),
                "objective": q.get("QuestObjective", ""),
                "bools": q.get("QuestBools", []),
                "ints": q.get("QuestInts", []),
            })

        inventory_items = []
        inv = d.get("Inventory", {})
        for key in sorted(inv.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            if key.isdigit():
                item = inv[key]
                inventory_items.append({
                    "slot": int(key),
                    "guid": item.get("GUID", ""),
                    "item_data": item.get("ItemData", ""),
                    "durability": item.get("Durability", 0),
                    "vital_shield": item.get("VitalShield", 0),
                    "quantity": item.get("Quantity", 1),
                })

        loadout_items = []
        loadout = d.get("Loadout", {})
        slot_names = {0: "Head", 1: "Body", 2: "Legs", 3: "Cape", 4: "Ring",
                      5: "Weapon", 6: "Shield", 7: "Ammo", 8: "Amulet"}
        for key in sorted(loadout.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            if key.isdigit():
                item = loadout[key]
                loadout_items.append({
                    "slot": int(key),
                    "slot_name": slot_names.get(int(key), f"Slot {key}"),
                    "guid": item.get("GUID", ""),
                    "item_data": item.get("ItemData", ""),
                    "durability": item.get("Durability", 0),
                    "vital_shield": item.get("VitalShield", 0),
                })

        sustenance = character.get("Sustenance", {})
        hydration = character.get("Hydration", {})
        toxicity = character.get("Toxicity", {})
        endurance = character.get("Endurance", {})

        return {
            "file": self.filename,
            "meta": {
                "char_name": d.get("meta_data", {}).get("char_name", "Unknown"),
                "char_guid": d.get("meta_data", {}).get("char_guid", ""),
                "char_type": d.get("meta_data", {}).get("char_type", 0),
                "save_count": d.get("SaveCount", 0),
                "version": d.get("Version", 0),
            },
            "character": {
                "playtime_sim": round(character.get("Playtime_sim", 0), 1),
                "playtime_wall": round(character.get("Playtime_wall", 0), 1),
                "playtime_hours": round(character.get("Playtime_wall", 0) / 3600, 1),
                "health": character.get("Health", {}).get("CurrentValue", 0) if isinstance(character.get("Health"), dict) else 0,
                "stamina": character.get("Stamina", {}).get("CurrentValue", 0) if isinstance(character.get("Stamina"), dict) else 0,
                "sustenance": sustenance.get("CurrentValue", 0) if isinstance(sustenance, dict) else 0,
                "hydration": hydration.get("CurrentValue", 0) if isinstance(hydration, dict) else 0,
                "toxicity": toxicity.get("CurrentValue", 0) if isinstance(toxicity, dict) else 0,
                "endurance": endurance.get("CurrentValue", 0) if isinstance(endurance, dict) else 0,
                "is_hardcore": d.get("Hardcore", {}).get("IsHardcore", False),
                "customization": character.get("Customization", {}).get("CustomizationData", {}),
            },
            "skills": skills,
            "quests": quests,
            "inventory": inventory_items,
            "loadout": loadout_items,
            "spells": d.get("Spellcasting", {}).get("SelectedSpells", []),
            "progress": {
                "recipes_unlocked": len(d.get("Progress", {}).get("RecipesUnlocked", [])),
                "buildings_unlocked": len(d.get("Progress", {}).get("BuildingsUnlocked", [])),
                "spells_unlocked": len(d.get("Progress", {}).get("SpellsUnlocked", [])),
                "items_picked_up": len(d.get("Progress", {}).get("ItemsPickedUp", [])),
                "killed_ais": len(d.get("Progress", {}).get("KilledOnceAIs", [])),
                "actors_interacted": len(d.get("Progress", {}).get("ActorsInteractedWith", [])),
            },
            "journal": {
                "unlocked": len(d.get("Journal", {}).get("UnlockedEntries", [])),
                "unread": len(d.get("Journal", {}).get("UnreadEntries", [])),
            },
            "fog": {
                "revealed_bitmap": d.get("RevealedFog", {}).get("RevealedRegionsBitmap", 0),
            },
        }

    def update_skill_xp(self, skill_id: str, new_xp: int):
        skills = self.data.get("Skills", {}).get("Skills", [])
        for skill in skills:
            if skill["Id"] == skill_id:
                skill["Xp"] = max(0, int(new_xp))
                return True
        return False

    def update_health(self, value: int):
        self.data.setdefault("Character", {}).setdefault("Health", {})["CurrentValue"] = max(0, int(value))

    def update_stamina(self, value: int):
        self.data.setdefault("Character", {}).setdefault("Stamina", {})["CurrentValue"] = max(0, int(value))

    def update_stat(self, stat_name: str, value):
        """Update a character stat like Sustenance, Hydration, Toxicity, Endurance."""
        char = self.data.setdefault("Character", {})
        if isinstance(char.get(stat_name), dict):
            char[stat_name]["CurrentValue"] = value
        else:
            char[stat_name] = {"CurrentValue": value}

    def update_quest_state(self, quest_id: str, new_state: int):
        quests = self.data.get("QuestProgress", {}).get("Quests", [])
        for quest in quests:
            if quest["QuestId"] == quest_id:
                quest["QuestState"] = int(new_state)
                return True
        return False

    def update_item_durability(self, slot: int, durability: int, source: str = "Inventory"):
        container = self.data.get(source, {})
        key = str(slot)
        if key in container:
            container[key]["Durability"] = max(0, int(durability))
            return True
        return False

    def update_item_quantity(self, slot: int, quantity: int):
        inv = self.data.get("Inventory", {})
        key = str(slot)
        if key in inv:
            inv[key]["Quantity"] = max(1, int(quantity))
            return True
        return False

    def delete_inventory_item(self, slot: int):
        inv = self.data.get("Inventory", {})
        key = str(slot)
        if key in inv:
            del inv[key]
            return True
        return False

    def set_hardcore(self, enabled: bool):
        self.data.setdefault("Hardcore", {})["IsHardcore"] = enabled


class WorldSave:
    """Parser for world .sav files (binary Dominion Engine format with embedded JSON)."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.raw_data = bytearray()
        self.json_sections: list[JsonSection] = []
        self.filename = os.path.basename(filepath)

    def load(self):
        with open(self.filepath, "rb") as f:
            self.raw_data = bytearray(f.read())
        self._find_json_sections()
        self._categorize_sections()

    def _find_json_sections(self):
        self.json_sections = []
        data = self.raw_data
        i = 0
        while i < len(data):
            if data[i:i + 1] in (b"{", b"["):
                try:
                    text = data[i:min(i + 500000, len(data))].decode("utf-8", errors="replace")
                    if '"' in text[:20]:
                        obj, end_idx = json.JSONDecoder().raw_decode(text)
                        if end_idx > 30:
                            self.json_sections.append(JsonSection(
                                offset=i, length=end_idx, data=obj
                            ))
                            i += end_idx
                            continue
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    pass
            i += 1

    def _categorize_sections(self):
        for section in self.json_sections:
            d = section.data
            if not isinstance(d, dict):
                continue
            keys = set(d.keys())

            if "Definitions" in keys:
                defs = d.get("Definitions", [])
                if isinstance(defs, list) and defs and isinstance(defs[0], dict) and "EventName" in defs[0]:
                    section.category = "world_events"
            elif "EventName" in keys and "EventData" in keys:
                section.category = "world_event"
            elif "Resources" in keys or "Fuel" in keys or "Output" in keys:
                section.category = "station"
            elif "AllowAdds" in keys:
                section.category = "container"
            elif "MaxSlotIndex" in keys:
                section.category = "slot_data"

    def get_header_info(self) -> dict:
        data = self.raw_data
        info = {
            "filepath": self.filepath,
            "filename": self.filename,
            "filesize": len(data),
            "filesize_mb": round(len(data) / 1024 / 1024, 2),
            "json_sections": len(self.json_sections),
            "world_name": "",
            "save_timestamp": "",
        }

        # Extract timestamp
        for year in [b"2026-", b"2025-", b"2027-"]:
            ts_start = data.find(year)
            if ts_start != -1:
                ts_end = data.find(b"\x00", ts_start)
                info["save_timestamp"] = data[ts_start:ts_end].decode("utf-8", errors="replace")
                break

        # Extract world name
        wn = data.find(b"Gielinor")
        if wn != -1:
            info["world_name"] = "Gielinor"
        else:
            # Try to find world name from the PROP section
            import re
            names = re.findall(rb'[\x20-\x7e]{4,30}', data[:0x300])
            for n in names:
                if b"." not in n and b"/" not in n and b"_" not in n:
                    candidate = n.decode("ascii")
                    if candidate[0].isupper() and candidate not in ("SAVE", "INFO", "CINF", "GLOB", "VERSION"):
                        info["world_name"] = candidate
                        break

        return info

    def get_world_events(self) -> list[dict]:
        events = []
        for section in self.json_sections:
            if section.category == "world_events":
                for ev in section.data.get("Definitions", []):
                    triggers = []
                    for t in ev.get("EventData", {}).get("Triggers", []):
                        triggers.append({
                            "name": t.get("TriggerName", ""),
                            "active": t.get("TriggerData", {}).get("CurrentValue", False),
                            "time": t.get("TriggerData", {}).get("TriggerTime", ""),
                        })
                    events.append({"name": ev.get("EventName", ""), "triggers": triggers})
        return events

    def get_stations(self) -> list[dict]:
        stations = []
        for section in self.json_sections:
            if section.category == "station":
                d = section.data
                stations.append({
                    "offset": hex(section.offset),
                    "resources": d.get("Resources", {}),
                    "fuel": d.get("Fuel", {}),
                    "output": d.get("Output", {}),
                    "fuel_time": d.get("FuelTimeRemaining", 0),
                    "recipe_time": d.get("RecipeTimeRemaining", 0),
                    "running": d.get("StationRunning", False),
                })
        return stations

    def get_containers(self) -> list[dict]:
        containers = []
        for section in self.json_sections:
            if section.category == "container":
                d = section.data
                items = {}
                for k, v in d.items():
                    if k.isdigit():
                        items[k] = v
                containers.append({
                    "offset": hex(section.offset),
                    "items": items,
                    "max_slots": d.get("MaxSlotIndex", -1),
                    "allow_adds": d.get("AllowAdds", True),
                })
        return containers

    def save(self, output_path: Optional[str] = None, backup: bool = True):
        if output_path is None:
            output_path = self.filepath

        if backup and os.path.exists(output_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(output_path), "editor_backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{self.filename}.{timestamp}.bak")
            shutil.copy2(output_path, backup_path)

        modified_data = bytearray(self.raw_data)
        sections_to_write = sorted(self.json_sections, key=lambda s: s.offset, reverse=True)

        for section in sections_to_write:
            new_json = json.dumps(section.data, indent="\t", ensure_ascii=False).encode("utf-8")
            old_start = section.offset
            old_end = section.offset + section.length
            modified_data[old_start:old_end] = new_json

        with open(output_path, "wb") as f:
            f.write(modified_data)


def discover_saves(base_path: Optional[str] = None) -> dict:
    """Find all save files in the default or given location."""
    if base_path is None:
        # Try common locations
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\RSDragonwilds\Saved"),
            os.path.expanduser("~/AppData/Local/RSDragonwilds/Saved"),
            "~/AppData/Local/RSDragonwilds/Saved",
        ]
        for c in candidates:
            if os.path.isdir(c):
                base_path = c
                break

    if not base_path or not os.path.isdir(base_path):
        return {"error": "Save directory not found", "characters": [], "worlds": []}

    characters = []
    char_dir = os.path.join(base_path, "SaveCharacters")
    if os.path.isdir(char_dir):
        for f in os.listdir(char_dir):
            if f.endswith(".json") and not f.endswith(".backup"):
                fpath = os.path.join(char_dir, f)
                characters.append({
                    "filename": f,
                    "filepath": fpath,
                    "size": os.path.getsize(fpath),
                })

    worlds = []
    world_dir = os.path.join(base_path, "SaveGames")
    if os.path.isdir(world_dir):
        for f in os.listdir(world_dir):
            if f.endswith(".sav") and not f.endswith(".backup"):
                fpath = os.path.join(world_dir, f)
                worlds.append({
                    "filename": f,
                    "filepath": fpath,
                    "size": os.path.getsize(fpath),
                })

    return {
        "base_path": base_path,
        "characters": characters,
        "worlds": worlds,
    }


if __name__ == "__main__":
    saves = discover_saves()
    print(f"Save directory: {saves.get('base_path', 'Not found')}")
    print(f"\nCharacters ({len(saves['characters'])}):")
    for c in saves["characters"]:
        cs = CharacterSave(c["filepath"])
        cs.load()
        s = cs.get_summary()
        print(f"  {s['meta']['char_name']} - {s['character']['playtime_hours']}h, {len(s['skills'])} skills, {len(s['quests'])} quests")
        for sk in s["skills"]:
            print(f"    {sk['name']}: Lvl {sk['level']} ({sk['xp']} XP)")

    print(f"\nWorlds ({len(saves['worlds'])}):")
    for w in saves["worlds"]:
        ws = WorldSave(w["filepath"])
        ws.load()
        info = ws.get_header_info()
        print(f"  {info['world_name']} - {info['filesize_mb']} MB, {info['json_sections']} data sections")
