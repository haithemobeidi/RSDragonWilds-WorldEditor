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
        for key in sorted(inv.keys(), key=lambda x: int(x) if x.isdigit() else 99999):
            if key.isdigit():
                item = inv[key]
                # Items are EITHER stackable (Count) OR durable (Durability)
                is_stackable = "Count" in item
                inventory_items.append({
                    "slot": int(key),
                    "guid": item.get("GUID", ""),
                    "item_data": item.get("ItemData", ""),
                    "durability": item.get("Durability"),  # None for stackables
                    "count": item.get("Count"),              # None for non-stackables
                    "vital_shield": item.get("VitalShield"),
                    "is_stackable": is_stackable,
                })

        loadout_items = []
        loadout = d.get("Loadout", {})
        slot_names = {0: "Head", 1: "Body", 2: "Legs", 3: "Cape", 4: "Ring",
                      5: "Weapon", 6: "Shield", 7: "Ammo", 8: "Amulet"}
        for key in sorted(loadout.keys(), key=lambda x: int(x) if x.isdigit() else 99999):
            if key.isdigit():
                item = loadout[key]
                # Slots 5-8 reference inventory by index
                inv_ref = item.get("PlayerInventoryItemIndex")
                loadout_items.append({
                    "slot": int(key),
                    "slot_name": slot_names.get(int(key), f"Slot {key}"),
                    "guid": item.get("GUID", ""),
                    "item_data": item.get("ItemData", ""),
                    "durability": item.get("Durability"),
                    "vital_shield": item.get("VitalShield"),
                    "inv_ref": inv_ref,  # If set, item is in inventory at this index
                })

        sustenance = character.get("Sustenance", {}) if isinstance(character.get("Sustenance"), dict) else {}
        hydration = character.get("Hydration", {}) if isinstance(character.get("Hydration"), dict) else {}
        toxicity = character.get("Toxicity", {}) if isinstance(character.get("Toxicity"), dict) else {}
        endurance = character.get("Endurance", {}) if isinstance(character.get("Endurance"), dict) else {}

        # Status effects
        status_effects = []
        se_raw = character.get("StatusEffects", {})
        for effect_name in ["Cold", "Poison", "Burning", "Bleeding", "Slow", "WellRested", "Cosiness", "Wither"]:
            ef = se_raw.get(effect_name, {})
            if isinstance(ef, dict):
                active_list = ef.get("Active", [False])
                is_active = any(active_list) if isinstance(active_list, list) else False
                status_effects.append({
                    "name": effect_name,
                    "value": ef.get("Value", 0),
                    "active": is_active,
                })

        # Position - parse "V(X=11924.46, Y=184569.45, Z=-3183.06)" format
        pos_str = character.get("LastAccessibleLocation", {}).get("Position", "")
        position = self._parse_position(pos_str)

        # Mounts
        mount = character.get("Mount", {})

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
                "sustenance": round(sustenance.get("SustenanceValue", 0), 2),
                "hydration": round(hydration.get("HydrationValue", 0), 2),
                "toxicity": round(toxicity.get("ToxicityValue", 0), 2),
                "highest_toxicity": round(toxicity.get("HighestToxicityValue", 0), 2),
                "endurance": round(endurance.get("EnduranceValue", 0), 2),
                "is_hardcore": d.get("Hardcore", {}).get("IsHardcore", False),
                "customization": character.get("Customization", {}).get("CustomizationData", {}),
                "position": position,
                "mount_equipped": mount.get("MountEquipped", "None"),
                "mounts_unlocked": mount.get("MountsUnlockedList", []),
            },
            "status_effects": status_effects,
            "skills": skills,
            "quests": quests,
            "inventory": inventory_items,
            "loadout": loadout_items,
            "spells": d.get("Spellcasting", {}).get("SelectedSpells", []),
            "spells_unlocked": d.get("Progress", {}).get("SpellsUnlocked", []),
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

    @staticmethod
    def _parse_position(pos_str: str) -> dict:
        """Parse 'V(X=11924.46, Y=184569.45, Z=-3183.06)' into {x, y, z}."""
        import re
        if not pos_str or pos_str == "V(0)":
            return {"x": 0.0, "y": 0.0, "z": 0.0, "raw": pos_str, "is_set": False}
        match = re.search(r'X=(-?[\d.]+).*Y=(-?[\d.]+).*Z=(-?[\d.]+)', pos_str)
        if match:
            return {
                "x": float(match.group(1)),
                "y": float(match.group(2)),
                "z": float(match.group(3)),
                "raw": pos_str,
                "is_set": True,
            }
        return {"x": 0.0, "y": 0.0, "z": 0.0, "raw": pos_str, "is_set": False}

    @staticmethod
    def _format_position(x: float, y: float, z: float) -> str:
        return f"V(X={x:.6f}, Y={y:.6f}, Z={z:.6f})"

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

    # Maps friendly stat names to (container_key, value_key)
    STAT_FIELD_MAP = {
        "Sustenance": ("Sustenance", "SustenanceValue"),
        "Hydration":  ("Hydration",  "HydrationValue"),
        "Toxicity":   ("Toxicity",   "ToxicityValue"),
        "Endurance":  ("Endurance",  "EnduranceValue"),
    }

    def update_stat(self, stat_name: str, value):
        """Update Sustenance, Hydration, Toxicity, or Endurance."""
        char = self.data.setdefault("Character", {})
        if stat_name in self.STAT_FIELD_MAP:
            container_key, value_key = self.STAT_FIELD_MAP[stat_name]
            container = char.setdefault(container_key, {})
            container[value_key] = float(value)
            # Reset decay buffer when restoring
            if "DecayBuffer" in (container_key + "DecayBuffer"):
                buf_key = container_key + "DecayBuffer"
                if buf_key in container:
                    container[buf_key] = 0
        else:
            # Generic fallback
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
        if key in container and "Durability" in container[key]:
            container[key]["Durability"] = max(0, int(durability))
            return True
        return False

    def update_item_count(self, slot: int, count: int, source: str = "Inventory"):
        """Update stack count (Count field) for stackable items."""
        container = self.data.get(source, {})
        key = str(slot)
        if key in container and "Count" in container[key]:
            container[key]["Count"] = max(1, int(count))
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

    # ----- Status Effects -----

    def clear_status_effect(self, effect_name: str):
        """Clear a status effect (set Value=0, Active=[false])."""
        effects = self.data.get("Character", {}).get("StatusEffects", {})
        if effect_name in effects and isinstance(effects[effect_name], dict):
            effects[effect_name]["Value"] = 0
            effects[effect_name]["Active"] = [False]
            return True
        return False

    def clear_all_status_effects(self):
        """Clear all negative status effects."""
        cleared = []
        for name in ["Cold", "Poison", "Burning", "Bleeding", "Slow", "Wither"]:
            if self.clear_status_effect(name):
                cleared.append(name)
        return cleared

    # ----- Position / Teleport -----

    def update_position(self, x: float, y: float, z: float):
        """Update player's last accessible location (teleport on next load)."""
        char = self.data.setdefault("Character", {})
        char.setdefault("LastAccessibleLocation", {})["Position"] = self._format_position(x, y, z)

    # ----- Spell Loadout -----

    def update_spell_slot(self, slot: int, spell_id: str):
        """Update a spell loadout slot."""
        spells = self.data.setdefault("Spellcasting", {}).setdefault("SelectedSpells", [])
        while len(spells) <= slot:
            spells.append("")
        spells[slot] = spell_id
        return True

    def clear_spell_slot(self, slot: int):
        spells = self.data.get("Spellcasting", {}).get("SelectedSpells", [])
        if 0 <= slot < len(spells):
            spells[slot] = ""
            return True
        return False

    # ----- Mounts -----

    def add_mount(self, mount_id: str):
        mount = self.data.setdefault("Character", {}).setdefault("Mount", {
            "MountEquipped": "None", "MountsUnlockedList": []
        })
        if mount_id and mount_id not in mount.setdefault("MountsUnlockedList", []):
            mount["MountsUnlockedList"].append(mount_id)
            return True
        return False

    def remove_mount(self, mount_id: str):
        mount = self.data.get("Character", {}).get("Mount", {})
        unlocked = mount.get("MountsUnlockedList", [])
        if mount_id in unlocked:
            unlocked.remove(mount_id)
            return True
        return False

    def equip_mount(self, mount_id: str):
        mount = self.data.setdefault("Character", {}).setdefault("Mount", {
            "MountEquipped": "None", "MountsUnlockedList": []
        })
        mount["MountEquipped"] = mount_id or "None"
        return True

    # ----- Quest Variables -----

    def update_quest_bool(self, quest_id: str, var_name: str, value: bool):
        quests = self.data.get("QuestProgress", {}).get("Quests", [])
        for q in quests:
            if q.get("QuestId") == quest_id:
                for b in q.get("QuestBools", []):
                    if b.get("QuestVariableName") == var_name:
                        b["QuestVariableValue"] = bool(value)
                        return True
        return False

    def update_quest_int(self, quest_id: str, var_name: str, value: int):
        quests = self.data.get("QuestProgress", {}).get("Quests", [])
        for q in quests:
            if q.get("QuestId") == quest_id:
                for i in q.get("QuestInts", []):
                    if i.get("QuestVariableName") == var_name:
                        i["QuestVariableValue"] = int(value)
                        return True
        return False

    # ----- Fog of War -----

    def reveal_full_map(self):
        """Set fog bitmap to all 1s, revealing the entire map."""
        fog = self.data.setdefault("RevealedFog", {})
        fog["RevealedRegionsBitmap"] = 0xFFFFFFFF  # 32-bit max
        return True

    def hide_full_map(self):
        fog = self.data.setdefault("RevealedFog", {})
        fog["RevealedRegionsBitmap"] = 0
        return True

    # ----- Repair / Mass operations -----

    def repair_all_items(self, durability: int = 9999):
        """Set all items in inventory and loadout to max durability."""
        count = 0
        for container_name in ["Inventory", "Loadout"]:
            container = self.data.get(container_name, {})
            for k, item in container.items():
                if k.isdigit() and isinstance(item, dict) and "Durability" in item:
                    item["Durability"] = durability
                    count += 1
        return count

    def max_all_skills(self):
        """Max all skills to top of XP table."""
        max_xp = XP_TABLE[-1]
        skills = self.data.get("Skills", {}).get("Skills", [])
        for skill in skills:
            skill["Xp"] = max_xp
        return len(skills)

    def fill_all_spell_slots(self, spell_id: str):
        """Fill all 48 spell slots with the same spell."""
        spells = self.data.setdefault("Spellcasting", {}).setdefault("SelectedSpells", [])
        while len(spells) < 48:
            spells.append("")
        for i in range(min(48, len(spells))):
            spells[i] = spell_id
        return 48


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
                if isinstance(defs, list) and defs and isinstance(defs[0], dict):
                    first = defs[0]
                    if "EventName" in first:
                        section.category = "world_events"
                    elif "WeatherName" in first:
                        section.category = "weather"
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

    def get_containers(self, include_empty: bool = False) -> list[dict]:
        containers = []
        for idx, section in enumerate(self.json_sections):
            if section.category == "container":
                d = section.data
                items = []
                for k, v in d.items():
                    if k.isdigit() and isinstance(v, dict):
                        items.append({
                            "slot": int(k),
                            "guid": v.get("GUID", ""),
                            "item_data": v.get("ItemData", ""),
                            "count": v.get("Count"),
                            "durability": v.get("Durability"),
                            "vital_shield": v.get("VitalShield"),
                            "is_stackable": "Count" in v,
                        })
                if items or include_empty:
                    containers.append({
                        "section_index": idx,
                        "offset": hex(section.offset),
                        "items": sorted(items, key=lambda x: x["slot"]),
                        "item_count": len(items),
                        "max_slots": d.get("MaxSlotIndex", -1),
                        "allow_adds": d.get("AllowAdds", True),
                    })
        return containers

    def get_weather(self) -> list[dict]:
        weather = []
        for section in self.json_sections:
            if section.category == "weather":
                for w in section.data.get("Definitions", []):
                    wd = w.get("WeatherData", {})
                    weather.append({
                        "name": w.get("WeatherName", ""),
                        "type": wd.get("TYPE", ""),
                        "day_count": wd.get("DAY_COUNT", 0),
                        "remaining_time": wd.get("REMAINING_TIME", 0),
                        "alt_profile": wd.get("ALT_PROFILE", False),
                    })
        return weather

    # ----- Edit methods -----

    def update_container_item(self, section_index: int, slot: int, field: str, value):
        """Edit an item in a world container (chest)."""
        if section_index >= len(self.json_sections):
            return False
        section = self.json_sections[section_index]
        d = section.data
        key = str(slot)
        if key in d and isinstance(d[key], dict):
            if field in ("Count", "Durability", "VitalShield"):
                d[key][field] = max(0, int(value))
                return True
        return False

    def update_weather(self, weather_name: str, weather_type: str = None, remaining_time: float = None):
        """Update weather for a region. weather_type like 'EWeatherType::Sunny'."""
        for section in self.json_sections:
            if section.category == "weather":
                for w in section.data.get("Definitions", []):
                    if w.get("WeatherName") == weather_name:
                        wd = w.setdefault("WeatherData", {})
                        if weather_type is not None:
                            if not weather_type.startswith("EWeatherType::"):
                                weather_type = f"EWeatherType::{weather_type}"
                            wd["TYPE"] = weather_type
                        if remaining_time is not None:
                            wd["REMAINING_TIME"] = float(remaining_time)
                        return True
        return False

    def update_event_trigger(self, event_name: str, trigger_name: str, active: bool = None, trigger_time: str = None):
        """Toggle a world event trigger or update its time."""
        for section in self.json_sections:
            if section.category == "world_events":
                for ev in section.data.get("Definitions", []):
                    if ev.get("EventName") == event_name:
                        for t in ev.get("EventData", {}).get("Triggers", []):
                            if t.get("TriggerName") == trigger_name:
                                td = t.setdefault("TriggerData", {})
                                if active is not None:
                                    td["CurrentValue"] = bool(active)
                                if trigger_time is not None:
                                    td["TriggerTime"] = trigger_time
                                return True
        return False

    def disable_all_raids(self):
        """Disable all raid/ambush events by setting their cooldowns far in the future."""
        count = 0
        for section in self.json_sections:
            if section.category == "world_events":
                for ev in section.data.get("Definitions", []):
                    name = ev.get("EventName", "")
                    if "raid" in name.lower() or "ambush" in name.lower():
                        for t in ev.get("EventData", {}).get("Triggers", []):
                            if t.get("TriggerName", "").lower() in ("cooldown", "delay_at_start"):
                                td = t.setdefault("TriggerData", {})
                                td["CurrentValue"] = True
                                td["TriggerTime"] = "+999.00:00:00.000"
                        count += 1
        return count

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

        warnings = []
        for section in sections_to_write:
            new_json = json.dumps(section.data, indent="\t", ensure_ascii=False).encode("utf-8")
            old_length = section.length
            old_start = section.offset
            old_end = section.offset + section.length

            if len(new_json) == old_length:
                pass  # perfect fit
            elif len(new_json) < old_length:
                # Pad inside the JSON: insert spaces just before the final closing brace/bracket
                # The last char is `}` or `]`. JSON allows whitespace before it.
                pad_count = old_length - len(new_json)
                last = new_json[-1:]
                new_json = new_json[:-1] + (b" " * pad_count) + last
            else:
                # New JSON is larger. Try compacting (no indent) first
                compact = json.dumps(section.data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                if len(compact) <= old_length:
                    pad_count = old_length - len(compact)
                    new_json = compact[:-1] + (b" " * pad_count) + compact[-1:]
                else:
                    warnings.append(
                        f"Section at 0x{old_start:x}: even compact JSON ({len(compact)}b) > original "
                        f"({old_length}b). Skipped — edit too large for in-place rewrite."
                    )
                    continue

            assert len(new_json) == old_length, \
                f"Length mismatch: {len(new_json)} != {old_length}"
            modified_data[old_start:old_end] = new_json

        with open(output_path, "wb") as f:
            f.write(modified_data)

        return {"path": output_path, "warnings": warnings}


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
