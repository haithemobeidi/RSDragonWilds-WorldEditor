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
import struct
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


# GUID → name mapping extracted from game .pak files via scripts/build_guid_map.py
# Module-level singleton — loaded once at import time. If the file is missing
# the editor still works, just with raw GUIDs.
#
# Manual overrides in data/guid_map_overrides.json are applied ON TOP of the
# extracted map at load time — used for runtime-instance GUIDs that don't match
# any template (tutorial quests, etc.).
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_GUID_MAP: dict = {"by_persistence_id": {}, "by_internal_name": {}}
try:
    _main_path = os.path.join(_DATA_DIR, "guid_map.json")
    if os.path.exists(_main_path):
        with open(_main_path) as _f:
            _GUID_MAP = json.load(_f)

    _override_path = os.path.join(_DATA_DIR, "guid_map_overrides.json")
    if os.path.exists(_override_path):
        with open(_override_path) as _f:
            _overrides = json.load(_f)
        _by_pid = _GUID_MAP.setdefault("by_persistence_id", {})
        for guid, entry in _overrides.items():
            if guid.startswith("_"):  # skip _comment / _meta keys
                continue
            _by_pid[guid] = entry  # overrides win
except Exception as _e:
    print(f"Warning: failed to load GUID map: {_e}")


def lookup_guid(guid: str) -> Optional[dict]:
    """Return the catalog entry for a save-file GUID, or None if not mapped."""
    if not guid:
        return None
    return _GUID_MAP.get("by_persistence_id", {}).get(guid)


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


# Complete catalog of all 35 known custom difficulty tags (mined from game logs).
# See DIFFICULTY_SETTINGS.md for details.
KNOWN_DIFFICULTY_TAGS = [
    # Combat - AI Damage/Health/Resistances per enemy category
    "Difficulty.AI.Beast.Damage", "Difficulty.AI.Beast.Health", "Difficulty.AI.Beast.Resistances",
    "Difficulty.AI.Boss.Damage", "Difficulty.AI.Boss.Health", "Difficulty.AI.Boss.Resistances",
    "Difficulty.AI.Construct.Damage", "Difficulty.AI.Construct.Health", "Difficulty.AI.Construct.Resistances",
    "Difficulty.AI.Critter.Damage", "Difficulty.AI.Critter.Health", "Difficulty.AI.Critter.Resistances",
    "Difficulty.AI.Garou.Damage", "Difficulty.AI.Garou.Health", "Difficulty.AI.Garou.Resistances",
    "Difficulty.AI.Goblin.Damage", "Difficulty.AI.Goblin.Health", "Difficulty.AI.Goblin.Resistances",
    "Difficulty.AI.MiniBoss.Damage", "Difficulty.AI.MiniBoss.Health", "Difficulty.AI.MiniBoss.Resistances",
    "Difficulty.AI.Skeleton.Damage", "Difficulty.AI.Skeleton.Health", "Difficulty.AI.Skeleton.Resistances",
    "Difficulty.AI.Undead.Damage", "Difficulty.AI.Undead.Health", "Difficulty.AI.Undead.Resistances",
    "Difficulty.AI.Zamorak.Damage", "Difficulty.AI.Zamorak.Health", "Difficulty.AI.Zamorak.Resistances",
    "Difficulty.AI.DisableAggressiveAI",
    # Environment
    "Difficulty.Environment.FriendlyFire",
    # Player
    "Difficulty.Player.NoBuildingStability",
    # Progression
    "Difficulty.Progression.BuildingMaterialCostScale",
    "Difficulty.Progression.CraftingCostScale",
]

# Friendly metadata for each tag
DIFFICULTY_TAG_INFO = {
    "Difficulty.AI.DisableAggressiveAI": ("Disable Aggressive AI", "bool", "1.0 = enemies don't attack you"),
    "Difficulty.Environment.FriendlyFire": ("Friendly Fire", "bool", "1.0 = can damage allies"),
    "Difficulty.Player.NoBuildingStability": ("No Building Stability", "bool", "1.0 = buildings don't need support"),
    "Difficulty.Progression.BuildingMaterialCostScale": ("Building Material Cost", "scale", "0.5 = half cost, 2.0 = double"),
    "Difficulty.Progression.CraftingCostScale": ("Crafting Cost", "scale", "0.5 = half cost, 2.0 = double"),
}
# Auto-generate metadata for AI category tags
for tag in KNOWN_DIFFICULTY_TAGS:
    if tag.startswith("Difficulty.AI.") and tag not in DIFFICULTY_TAG_INFO:
        # e.g. "Difficulty.AI.Beast.Health" -> ("Beast Health", "scale", ...)
        parts = tag.split(".")
        if len(parts) == 4:
            category, stat = parts[2], parts[3]
            DIFFICULTY_TAG_INFO[tag] = (
                f"{category} {stat}",
                "scale",
                "1.0 = normal, 0.5 = easier, 2.0 = harder",
            )


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

        # Dedupe quests by QuestId — the game accumulates duplicate entries
        # across play sessions; we keep the LAST entry per id (most recent state).
        quests_by_id: dict[str, dict] = {}
        state_names = {0: "Not Started", 1: "In Progress", 2: "Completed"}
        for q in d.get("QuestProgress", {}).get("Quests", []):
            qid = q.get("QuestId", "")
            if not qid:
                continue
            catalog = lookup_guid(qid)
            quests_by_id[qid] = {
                "id": qid,
                "state": q.get("QuestState", 0),
                "state_name": state_names.get(q.get("QuestState", 0), "Unknown"),
                "objective": q.get("QuestObjective", ""),
                "bools": q.get("QuestBools", []),
                "ints": q.get("QuestInts", []),
                # Enriched from data/guid_map.json (Phase 2 pak extraction)
                "display_name": catalog.get("name") if catalog else None,
                "description": catalog.get("description") if catalog else None,
                "internal_name": catalog.get("internal_name") if catalog else None,
            }
        # Sort: completed last, then in-progress, then not started (so active quests float to top)
        quests = sorted(
            quests_by_id.values(),
            key=lambda q: (q["state"] == 2, q["state"] != 1, q.get("display_name") or q["id"])
        )

        inventory_items = []
        inv = d.get("Inventory", {})
        for key in sorted(inv.keys(), key=lambda x: int(x) if x.isdigit() else 99999):
            if key.isdigit():
                item = inv[key]
                # Items are EITHER stackable (Count) OR durable (Durability)
                is_stackable = "Count" in item
                item_data = item.get("ItemData", "")
                catalog = lookup_guid(item_data)
                inventory_items.append({
                    "slot": int(key),
                    "guid": item.get("GUID", ""),
                    "item_data": item_data,
                    "durability": item.get("Durability"),  # None for stackables
                    "count": item.get("Count"),              # None for non-stackables
                    "vital_shield": item.get("VitalShield"),
                    "is_stackable": is_stackable,
                    # Enriched from data/guid_map.json (Phase 2 pak extraction)
                    "display_name": catalog.get("name") if catalog else None,
                    "description": catalog.get("description") if catalog else None,
                    "icon_key": catalog.get("icon") if catalog else None,
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

    def set_char_type(self, char_type: int):
        """
        Set the character type flag controlling which world types they can join.
        Discovered 04-06-2026:
          0 = Standard worlds only (Gielinor, default new worlds)
          3 = Custom worlds only (Middle Eearth, custom-difficulty worlds)
        Mutually exclusive — no "both" value found.
        """
        if "meta_data" not in self.data:
            self.data["meta_data"] = {}
        self.data["meta_data"]["char_type"] = int(char_type)

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
        self.difficulty_entries: list[dict] = []
        self.filename = os.path.basename(filepath)

    def load(self):
        with open(self.filepath, "rb") as f:
            self.raw_data = bytearray(f.read())
        self._find_json_sections()
        self._categorize_sections()
        self._find_difficulty_entries()

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

    # ===== World Mode (Standard / Custom) =====
    # Discovered 04-06-2026: Two bytes determine world mode classification.
    # Both must be set together for the game to recognize and PERSIST a custom-world.
    # Byte A: L_World+9 uint32 enum (display/UI cache)
    # Byte B: First byte of CustomDifficultySettings PROP field (persistent storage)

    def _find_mode_byte_offsets(self) -> tuple[int, int]:
        """Returns (l_world_enum_offset, prop_cds_byte_offset) or (-1, -1) if not found."""
        data = self.raw_data
        lw = data.find(b'L_World\x00')
        if lw == -1:
            return (-1, -1)

        prop_p = data.find(b'PROP')
        if prop_p == -1:
            return (-1, -1)

        try:
            count = struct.unpack('<I', bytes(data[prop_p+8:prop_p+12]))[0]
            if count == 0 or count > 100:
                return (-1, -1)
            offsets = struct.unpack(
                f'<{count}I', bytes(data[prop_p+12 : prop_p+12 + count*4])
            )
            data_start = prop_p + 12 + count * 4
            # CustomDifficultySettings is field index 8 in WorldSaveSettings
            if 8 >= len(offsets):
                return (-1, -1)
            cds_pos = data_start + offsets[8]
            return (lw + 9, cds_pos)
        except (struct.error, IndexError):
            return (-1, -1)

    def get_world_mode(self) -> str:
        """Returns 'standard', 'custom', or 'unknown'."""
        lw_offset, prop_offset = self._find_mode_byte_offsets()
        if lw_offset == -1 or prop_offset == -1:
            return "unknown"

        try:
            lw_enum = struct.unpack(
                '<I', bytes(self.raw_data[lw_offset:lw_offset+4])
            )[0]
            prop_byte = self.raw_data[prop_offset]
        except (struct.error, IndexError):
            return "unknown"

        # Both must be 3 for definitive Custom; both 0 for definitive Standard
        if lw_enum == 3 and prop_byte == 0x03:
            return "custom"
        if lw_enum == 0 and prop_byte == 0x00:
            return "standard"
        # Mixed state (e.g., one byte was flipped without the other)
        return f"mixed (lw={lw_enum}, prop=0x{prop_byte:02x})"

    def convert_to_custom(self) -> bool:
        """
        Convert this world from Standard to Custom by setting both mode bytes.
        Returns True on success. Caller should then call save().
        """
        lw_offset, prop_offset = self._find_mode_byte_offsets()
        if lw_offset == -1 or prop_offset == -1:
            return False
        # Byte A: L_World+9 enum → 3
        self.raw_data[lw_offset:lw_offset+4] = struct.pack('<I', 3)
        # Byte B: PROP CustomDifficultySettings first byte → 0x03
        self.raw_data[prop_offset] = 0x03
        return True

    def revert_to_standard(self) -> bool:
        """
        Revert this world from Custom back to Standard. Inverse of convert_to_custom().
        Returns True on success.
        """
        lw_offset, prop_offset = self._find_mode_byte_offsets()
        if lw_offset == -1 or prop_offset == -1:
            return False
        self.raw_data[lw_offset:lw_offset+4] = struct.pack('<I', 0)
        self.raw_data[prop_offset] = 0x00
        return True

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
            "world_mode": self.get_world_mode(),
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

    # ===== Custom Difficulty Settings =====

    DIFFICULTY_HEADER_NEEDLE = b'\x08\x00\x00\x00TagName\x00\x0d\x00\x00\x00NameProperty\x00'

    def _find_difficulty_entries(self):
        """
        Scan the binary for custom difficulty setting entries.
        Each entry is structured as:
            FString "TagName" (8 bytes prefixed)
            FString "NameProperty" (13 bytes prefixed)
            ~13 bytes of UE4 property metadata
            FString <difficulty tag>
            FString "None"
            float32 <value>
        """
        self.difficulty_entries = []
        data = self.raw_data
        pos = 0
        while True:
            idx = data.find(self.DIFFICULTY_HEADER_NEEDLE, pos)
            if idx == -1:
                break
            pos = idx + len(self.DIFFICULTY_HEADER_NEEDLE)

            # Search for "Difficulty." within next 50 bytes
            diff_idx = data.find(b'Difficulty.', pos, min(pos + 50, len(data)))
            if diff_idx == -1:
                continue
            # Length prefix is 4 bytes before
            try:
                tag_len = struct.unpack('<i', data[diff_idx - 4:diff_idx])[0]
                tag_bytes = data[diff_idx:diff_idx + tag_len - 1]  # exclude null
                tag = tag_bytes.decode('utf-8')
            except (struct.error, UnicodeDecodeError):
                continue

            # After tag (with null): expect 9-byte FString "None"
            after_tag = diff_idx + tag_len
            if data[after_tag:after_tag + 9] != b'\x05\x00\x00\x00None\x00':
                continue

            # Float follows
            float_offset = after_tag + 9
            if float_offset + 4 > len(data):
                continue
            try:
                value = struct.unpack('<f', data[float_offset:float_offset + 4])[0]
            except struct.error:
                continue

            self.difficulty_entries.append({
                'tag': tag,
                'value': value,
                'value_offset': float_offset,
                'tag_offset': diff_idx,
                'header_offset': idx,
            })

    def get_difficulty_settings(self) -> dict:
        """Return current difficulty settings + catalog of all known tags."""
        # Build current entries with friendly names
        current = []
        for e in self.difficulty_entries:
            name, dtype, hint = DIFFICULTY_TAG_INFO.get(e['tag'], (e['tag'], 'scale', ''))
            current.append({
                'tag': e['tag'],
                'name': name,
                'type': dtype,
                'hint': hint,
                'value': e['value'],
                'value_offset': e['value_offset'],
            })

        # Get list of "missing" tags (not currently in save) for Phase 2 reference
        present_tags = {e['tag'] for e in self.difficulty_entries}
        missing = []
        for tag in KNOWN_DIFFICULTY_TAGS:
            if tag not in present_tags:
                name, dtype, hint = DIFFICULTY_TAG_INFO.get(tag, (tag, 'scale', ''))
                missing.append({'tag': tag, 'name': name, 'type': dtype, 'hint': hint})

        return {
            'current': current,
            'missing': missing,
            'total_known': len(KNOWN_DIFFICULTY_TAGS),
        }

    def update_difficulty_value(self, tag: str, new_value: float) -> bool:
        """
        Length-preserving update of an existing difficulty entry.
        Returns True if updated, False if tag not found.
        """
        for e in self.difficulty_entries:
            if e['tag'] == tag:
                new_bytes = struct.pack('<f', float(new_value))
                self.raw_data[e['value_offset']:e['value_offset'] + 4] = new_bytes
                e['value'] = float(new_value)
                return True
        return False

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

    # ===== Placed Structures (player-built actors in SPWN chunks) =====
    #
    # Reverse-engineered 04-07-2026 via diff of three same-world snapshots
    # (see scripts/structure_research/). Player-built actors are stored as
    # SPWN+PROP record pairs inside the LVLS chunk. The world's procedural
    # content (trees, rocks, ore, enemies) is generated from the world seed
    # at load time and is NOT serialized per-instance — only state deltas.
    #
    # Each save file has ~15 baseline SPWN records (some kind of system
    # entities — starter tent, persistence anchors, etc.) that we ignore.
    # Player-built structures are detected by matching their record version
    # byte and class-reference signature.
    #
    # Record layout for Personal Chest (589 bytes):
    #   0x00-0x03  record version  (0x00000017)
    #   0x04-0x13  16-byte instance GUID (unique per placed actor)
    #   0x14-0x43  6 doubles (actor transform — pos vec3 + rot/scale vec3)
    #   0x44-0x67  class+component table refs (constant per class)
    #   0x68-0xff  secondary transform region + reserved
    #   0x100+     embedded PROPF property block

    # Known structure class signatures.
    #
    # Cross-world detection strategy (validated 04-07-2026 against Gielinor):
    # The first 4 bytes (`body_first4`) and the class-table indices in the
    # class-ref region are WORLD-LOCAL — they reference each world's own
    # CDEF/CNIX table indices and differ between worlds. Do NOT use them for
    # cross-world matching.
    #
    # What IS portable across worlds:
    #   1. Body length (a class-determined fixed size for an empty fresh actor)
    #   2. The constant 9-byte property header at offset 0x44:
    #          01 0a 02 00 00 f9 03 00 00
    #      This is the same for every SPWN actor record we've seen.
    #   3. The component count uint32 at offset 0x4d (immediately after the
    #      header). This IS the per-class discriminator — Personal Chest has
    #      3 components, Ash Chest has 5, the baseline tree/rock/system
    #      records have 2.
    #
    # So a portable signature is: body_length + component_count + constant header.
    # The class-table indices that follow the count (4 bytes each) are world-local
    # and intentionally ignored.
    PROPERTY_HEADER_PREFIX = b"\x01\x0a\x02\x00\x00\xf9\x03\x00\x00"
    PROPERTY_HEADER_OFFSET = 0x44
    COMPONENT_COUNT_OFFSET = 0x4d  # uint32, immediately after PROPERTY_HEADER_PREFIX

    KNOWN_STRUCTURES = {
        "BP_BaseBuilding_PersonalChest_C": {
            "body_length": 589,
            "component_count": 3,
            "display_name": "Personal Chest",
        },
        "BP_BaseBuilding_AshChest_C": {
            "body_length": 625,
            "component_count": 5,
            "display_name": "Ash Chest",
        },
    }

    # Offsets within an SPWN body for the actor transform doubles
    SPWN_TRANSFORM_OFFSET = 0x14
    SPWN_TRANSFORM_DOUBLE_COUNT = 6
    SPWN_INSTANCE_GUID_OFFSET = 0x04

    # ===== Placed Building Pieces (player-built walls/floors/roofs in Pces chunk) =====
    #
    # Reverse-engineered 04-07-2026 (continuation of structure research).
    # Building pieces (walls, floors, roofs, doors, foundations) are stored in
    # the `Pces` chunk inside the world save, NOT in `SPWN` records. The Pces
    # chunk is a length-prefixed chunk containing a flat array of piece records.
    #
    # Each piece record contains:
    #   uint32   persistent_id   (globally-unique ID; gaps appear when pieces
    #                             are deleted/replaced during construction)
    #   FString  guid            (length-prefixed, always 23 bytes = 22-char
    #                             base64 GUID + null terminator. The GUID
    #                             identifies the piece CLASS — walls share a
    #                             GUID, tiles share a different GUID, etc.)
    #   double   pos_x, pos_y, pos_z    (UE world coordinates in cm)
    #   float    extra_a, extra_b, extra_c
    #            extra_a is rotation degrees (0-360)
    #            extra_b is variable per piece type — possibly piece length
    #                    in cm (965 = 9.65m, 1565 = 15.65m for taller pieces)
    #            extra_c is usually 1.0 (uniform scale?)
    #   uint32   ref_count       (1-4 typically — number of connection anchors)
    #   FString  refs[ref_count] (anchor GUIDs — usually share class with the
    #                             main piece's parent foundation)
    #   ...trailing slot/connection data (variable length, format varies per class)
    #
    # The trailing format is messy and varies per class — we don't parse it
    # for the purposes of detection. We just identify records by scanning for
    # the (FString-23 + 3 doubles + 3 floats + small uint32 ref_count) pattern.

    def get_placed_pieces(self) -> list[dict]:
        """
        Walk the Pces chunk and return all detected placed building pieces
        (walls, floors, roofs, doors, etc.). Returns one entry per piece with
        persistent_id, guid (class identifier), position, extras (rotation
        and per-class fields), and ref_count.
        """
        data = self.raw_data

        # Find the Pces chunk
        pces_off = data.find(b"Pces")
        if pces_off == -1:
            return []
        try:
            pces_len = struct.unpack_from("<I", data, pces_off + 4)[0]
        except struct.error:
            return []
        if pces_len <= 0 or pces_off + 8 + pces_len > len(data):
            return []
        body = bytes(data[pces_off + 8 : pces_off + 8 + pces_len])

        pieces = []
        # Scan for FString-23 occurrences and check what follows
        i = 0
        while i < len(body) - 27 - 36 - 4:
            # FString length prefix == 23?
            if body[i:i+4] != b"\x17\x00\x00\x00":
                i += 1
                continue
            gchunk = body[i+4:i+27]
            # Must be printable ASCII ending in null
            if gchunk[-1] != 0:
                i += 1
                continue
            if not all(0x20 <= b <= 0x7e or b == 0 for b in gchunk):
                i += 1
                continue
            try:
                guid = gchunk[:-1].decode("ascii")
            except UnicodeDecodeError:
                i += 1
                continue

            # Try to interpret the bytes after the GUID as a piece record:
            #   3 doubles (24 B) + 3 floats (12 B) + uint32 ref_count (4 B)
            tail_off = i + 27
            try:
                px, py, pz = struct.unpack_from("<3d", body, tail_off)
                e1, e2, e3 = struct.unpack_from("<3f", body, tail_off + 24)
                ref_count = struct.unpack_from("<I", body, tail_off + 36)[0]
            except struct.error:
                i += 1
                continue

            # Plausibility checks: position must be in a sane range, ref_count small
            if not all(-1e7 < c < 1e7 for c in (px, py, pz)):
                i += 1
                continue
            if ref_count > 30:
                i += 1
                continue

            # Read the persistent ID from the 4 bytes BEFORE this FString
            persistent_id = 0
            if i >= 4:
                persistent_id = struct.unpack_from("<I", body, i - 4)[0]

            pieces.append({
                "pces_offset": i,
                "persistent_id": persistent_id,
                "guid": guid,
                "position": {"x": px, "y": py, "z": pz},
                "rotation_deg": e1,
                "extra_b": e2,
                "extra_c": e3,
                "ref_count": ref_count,
            })

            # Skip past this record's known prefix to avoid re-matching the GUID
            i = tail_off + 36 + 4
        return pieces

    # ===== Surgical Cross-World Transplant =====
    # See scripts/structure_research/surgical_transplant_v3.py for the
    # development history. Verified working in-game (cabin transplant
    # DiffTest → TransplantTest, 04-08-2026).
    #
    # IMPORTANT LIMITATIONS:
    # - Only Category 1 (passive building pieces — walls, floors, roofs) work
    # - Category 2 (chests, interactive actors) need additional SPWN copying
    #   that this method does NOT perform; their Pces records will be added
    #   but the actors won't instantiate
    # - Pre-existing target structures spatially overlapping the transplant
    #   may be silently destroyed by the game's collision system

    def _find_gbm_nobj_layout(self) -> Optional[dict]:
        """
        Locate the GlobalBuildingManager NOBJ in this world's L_World LEVL.
        Returns a dict with all the chunk header offsets needed for surgical
        modification, or None if not found.
        """
        data = self.raw_data

        # Walk SAVE → LVLS → L_World LEVL → LATS → GBM NOBJ → CUST → Pces
        if data[:4] != b"SAVE":
            return None

        save_len = struct.unpack_from("<I", data, 4)[0]
        save_end = 8 + save_len

        # Find LVLS in SAVE body
        lvls_off = data.find(b"LVLS", 8, save_end)
        if lvls_off == -1:
            return None
        lvls_len = struct.unpack_from("<I", data, lvls_off + 4)[0]
        lvls_body_start = lvls_off + 8
        lvls_body_end = lvls_body_start + lvls_len

        # Find L_World LEVL inside LVLS
        # LVLS body is just sequential LEVL chunks
        levl_off = lvls_body_start
        l_world_levl = None
        while levl_off < lvls_body_end - 8:
            if data[levl_off:levl_off+4] != b"LEVL":
                levl_off += 1
                continue
            levl_len = struct.unpack_from("<I", data, levl_off + 4)[0]
            levl_body_start = levl_off + 8
            # Check if this LEVL's name is "L_World"
            try:
                name_len = struct.unpack_from("<i", data, levl_body_start)[0]
                if 0 < name_len < 100:
                    name = bytes(data[levl_body_start + 4 : levl_body_start + 4 + name_len - 1]).decode("ascii", errors="replace")
                    if name == "L_World":
                        l_world_levl = (levl_off, levl_len, levl_body_start)
                        break
            except (struct.error, UnicodeDecodeError):
                pass
            levl_off = levl_body_start + levl_len

        if l_world_levl is None:
            return None
        levl_off, levl_len, levl_body_start = l_world_levl
        levl_body_end = levl_body_start + levl_len

        # Skip past name FString + 8-byte version header
        name_len = struct.unpack_from("<i", data, levl_body_start)[0]
        pos = levl_body_start + 4 + name_len + 8

        # Find LATS sub-chunk inside L_World LEVL
        lats_off = None
        while pos < levl_body_end - 8:
            tag = bytes(data[pos:pos+4])
            length = struct.unpack_from("<I", data, pos + 4)[0]
            if tag == b"LATS":
                lats_off = pos
                lats_body_start = pos + 8
                lats_body_end = lats_body_start + length
                break
            pos += 8 + length
        if lats_off is None:
            return None
        lats_len = length

        # Walk LATS body to find GlobalBuildingManager NOBJ
        gbm_nobj_off = None
        nobj_pos = lats_body_start
        while nobj_pos < lats_body_end - 8:
            if data[nobj_pos:nobj_pos+4] != b"NOBJ":
                nobj_pos += 1
                continue
            nobj_len = struct.unpack_from("<I", data, nobj_pos + 4)[0]
            nobj_body_start = nobj_pos + 8
            # NOBJ body: ClassID(4) + FString Name + ...
            try:
                name_field_len = struct.unpack_from("<i", data, nobj_body_start + 4)[0]
                if 0 < name_field_len < 200:
                    name_str = bytes(data[nobj_body_start + 8 : nobj_body_start + 8 + name_field_len - 1]).decode("ascii", errors="replace")
                    if "GlobalBuildingManager" in name_str:
                        gbm_nobj_off = nobj_pos
                        gbm_nobj_len = nobj_len
                        gbm_nobj_body_start = nobj_body_start
                        gbm_nobj_body_end = nobj_body_start + nobj_len
                        gbm_class_id = struct.unpack_from("<I", data, nobj_body_start)[0]
                        gbm_name = name_str
                        # Position right after the name FString + 12B metadata + 8B version header
                        pos_after = nobj_body_start + 4 + 4 + name_field_len + 12 + 8
                        break
            except (struct.error, UnicodeDecodeError):
                pass
            nobj_pos = nobj_body_start + nobj_len
        if gbm_nobj_off is None:
            return None

        # Walk NOBJ body to find PROP and CUST sub-chunks
        prop_off = None
        cust_off = None
        sub_pos = pos_after
        while sub_pos < gbm_nobj_body_end - 8:
            stag = bytes(data[sub_pos:sub_pos+4])
            slen = struct.unpack_from("<I", data, sub_pos + 4)[0]
            if stag == b"PROP":
                prop_off = sub_pos
                prop_len = slen
                prop_body_start = sub_pos + 8
            elif stag == b"CUST":
                cust_off = sub_pos
                cust_len = slen
                cust_body_start = sub_pos + 8
                cust_body_end = cust_body_start + slen
                break
            sub_pos += 8 + slen
        if cust_off is None:
            return None

        # CUST body: int32 TArray count + bytes
        tarray_count_off = cust_body_start
        tarray_count = struct.unpack_from("<i", data, tarray_count_off)[0]
        tarray_data_start = cust_body_start + 4

        # Find Pces chunk inside CUST data
        pces_off = data.find(b"Pces", tarray_data_start, cust_body_end)
        if pces_off == -1:
            return None
        pces_len = struct.unpack_from("<I", data, pces_off + 4)[0]
        pces_body_start = pces_off + 8
        pces_body_end = pces_body_start + pces_len

        # Locate PROP[2] counter offset (the per-world piece counter)
        # PROP body: int32 offsets_count + offsets + int32 data_count + data
        prop2_off = None
        if prop_off is not None:
            try:
                p = prop_body_start
                offsets_count = struct.unpack_from("<i", data, p)[0]
                p += 4
                offsets = list(struct.unpack_from(f"<{offsets_count}I", data, p))
                p += offsets_count * 4
                data_count_field = struct.unpack_from("<i", data, p)[0]
                p += 4
                data_blob_start = p
                if len(offsets) >= 3:
                    prop2_off = data_blob_start + offsets[2]
            except struct.error:
                pass

        return {
            "save_off": 0,
            "lvls_off": lvls_off,
            "levl_off": levl_off,
            "lats_off": lats_off,
            "nobj_off": gbm_nobj_off,
            "cust_off": cust_off,
            "tarray_count_off": tarray_count_off,
            "tarray_count": tarray_count,
            "pces_off": pces_off,
            "pces_body_start": pces_body_start,
            "pces_body_end": pces_body_end,
            "pces_len": pces_len,
            "prop2_off": prop2_off,
            "gbm_name": gbm_name,
        }

    def get_pces_body(self) -> Optional[bytes]:
        """Return the raw bytes of the GlobalBuildingManager Pces chunk body, or None."""
        layout = self._find_gbm_nobj_layout()
        if layout is None:
            return None
        return bytes(self.raw_data[layout["pces_body_start"] : layout["pces_body_end"]])

    def get_pces_counter(self) -> Optional[int]:
        """Return the GBM PROP[2] counter value (next persistent_id / piece count), or None."""
        layout = self._find_gbm_nobj_layout()
        if layout is None or layout["prop2_off"] is None:
            return None
        return struct.unpack_from("<I", self.raw_data, layout["prop2_off"])[0]

    def transplant_structures_from(self, source: "WorldSave", auto_save: bool = True) -> dict:
        """
        Copy all building piece records from `source` world's GlobalBuildingManager
        Pces chunk into this world's GBM Pces chunk, preserving this world's
        existing pieces and other state. Updates the GBM PROP[2] counter to at
        least the source's value so the game accepts the new pieces.

        ⚠️ LIMITATIONS:
          - Only Category 1 pieces (walls, floors, roofs) actually render in-game
          - Category 2 pieces (chests, stations) need additional SPWN copying
            that this method does NOT do; their Pces records will be added but
            the actors won't instantiate
          - Spatially overlapping pre-existing target structures may be lost

        Returns a dict with operation summary:
            {
                "added_bytes": int,
                "source_pces_size": int,
                "target_pces_before": int,
                "target_pces_after": int,
                "old_counter": int,
                "new_counter": int,
            }
        """
        src_layout = source._find_gbm_nobj_layout()
        if src_layout is None:
            raise ValueError(f"Source world has no GlobalBuildingManager NOBJ")
        tgt_layout = self._find_gbm_nobj_layout()
        if tgt_layout is None:
            raise ValueError(f"Target world has no GlobalBuildingManager NOBJ")

        src_pces_body = bytes(source.raw_data[src_layout["pces_body_start"] : src_layout["pces_body_end"]])
        delta = len(src_pces_body)

        # Insert at end of target's Pces body
        insert_point = tgt_layout["pces_body_end"]
        new_data = bytearray(self.raw_data[:insert_point])
        new_data.extend(src_pces_body)
        new_data.extend(self.raw_data[insert_point:])

        # Update chunk lengths up the tree (Pces, CUST, NOBJ, LATS, LEVL, LVLS, SAVE)
        # All these chunk headers come BEFORE the insert point so their offsets
        # in `new_data` are unchanged.
        for chunk_off in ["pces_off", "cust_off", "nobj_off", "lats_off", "levl_off", "lvls_off", "save_off"]:
            hdr = tgt_layout[chunk_off]
            old_len = struct.unpack_from("<I", new_data, hdr + 4)[0]
            struct.pack_into("<I", new_data, hdr + 4, old_len + delta)

        # Update CUST TArray count (signed int32, also before insert point)
        ct_off = tgt_layout["tarray_count_off"]
        old_ct = struct.unpack_from("<i", new_data, ct_off)[0]
        struct.pack_into("<i", new_data, ct_off, old_ct + delta)

        # Update GBM PROP[2] counter to max(target, source)
        old_counter = 0
        new_counter = 0
        if tgt_layout["prop2_off"] is not None:
            old_counter = struct.unpack_from("<I", new_data, tgt_layout["prop2_off"])[0]
            src_counter = source.get_pces_counter() or 0
            new_counter = max(old_counter, src_counter)
            if new_counter > old_counter:
                struct.pack_into("<I", new_data, tgt_layout["prop2_off"], new_counter)

        # Replace raw data
        self.raw_data = new_data
        # JSON section offsets are now stale — re-scan
        self._find_json_sections()
        self._categorize_sections()

        result = {
            "added_bytes": delta,
            "source_pces_size": delta,
            "target_pces_before": tgt_layout["pces_len"],
            "target_pces_after": tgt_layout["pces_len"] + delta,
            "old_counter": old_counter,
            "new_counter": new_counter,
        }

        if auto_save:
            self._raw_save()

        return result

    def _raw_save(self):
        """Write raw_data directly to filepath. Used by binary-modifying operations
        that don't want the JSON-section-rewriting save() path."""
        # Auto-backup
        if os.path.exists(self.filepath):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(self.filepath), "editor_backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{self.filename}.{timestamp}.bak")
            shutil.copy2(self.filepath, backup_path)
        with open(self.filepath, "wb") as f:
            f.write(bytes(self.raw_data))

    def get_placed_structures(self) -> list[dict]:
        """
        Walk all SPWN chunks in the binary and return player-built structures.
        Returns one entry per detected structure with offset, class, position,
        instance GUID, and the raw record bytes (for transplant operations).
        """
        structures = []
        data = self.raw_data
        pos = 0
        while True:
            spwn_off = data.find(b"SPWN", pos)
            if spwn_off == -1:
                break
            pos = spwn_off + 1

            # Length is the next 4 bytes (little-endian uint32)
            if spwn_off + 8 > len(data):
                continue
            try:
                body_len = struct.unpack_from("<I", data, spwn_off + 4)[0]
            except struct.error:
                continue
            # Sanity check on length
            if body_len < 100 or body_len > 10000:
                continue
            body_start = spwn_off + 8
            body_end = body_start + body_len
            if body_end > len(data):
                continue

            body = bytes(data[body_start:body_end])

            # Portable cross-world detection: match by body_length + component_count
            # plus the constant property header at offset 0x44. Ignore the world-local
            # class-table indices that follow.
            if body_len < self.COMPONENT_COUNT_OFFSET + 4:
                continue
            if body[self.PROPERTY_HEADER_OFFSET : self.PROPERTY_HEADER_OFFSET + len(self.PROPERTY_HEADER_PREFIX)] != self.PROPERTY_HEADER_PREFIX:
                continue
            try:
                comp_count = struct.unpack_from("<I", body, self.COMPONENT_COUNT_OFFSET)[0]
            except struct.error:
                continue

            matched = None
            for class_name, sig in self.KNOWN_STRUCTURES.items():
                if body_len == sig["body_length"] and comp_count == sig["component_count"]:
                    matched = (class_name, sig)
                    break
            if matched is None:
                continue
            class_name, sig = matched

            # Extract the 16-byte instance GUID
            instance_guid = body[
                self.SPWN_INSTANCE_GUID_OFFSET
                : self.SPWN_INSTANCE_GUID_OFFSET + 16
            ]

            # Extract the 6 transform doubles starting at 0x14
            try:
                doubles = struct.unpack_from(
                    f"<{self.SPWN_TRANSFORM_DOUBLE_COUNT}d",
                    body,
                    self.SPWN_TRANSFORM_OFFSET,
                )
            except struct.error:
                continue

            structures.append({
                "spwn_offset": spwn_off,
                "body_length": body_len,
                "class_name": class_name,
                "display_name": sig["display_name"],
                "instance_guid_hex": instance_guid.hex(),
                # First 3 doubles are position (X, Y, Z) in UE coordinates
                "position": {
                    "x": doubles[0],
                    "y": doubles[1],
                    "z": doubles[2],
                },
                # Last 3 doubles are unverified — likely rotation or scale
                "transform_extra": list(doubles[3:6]),
                "raw_record_hex": body.hex(),
            })
        return structures

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
    """Find all save files in the default or given location.

    Auto-detects the game's save directory across platforms:
    - Windows: %LOCALAPPDATA%\\RSDragonwilds\\Saved
    - WSL: /mnt/c/Users/<your-windows-user>/AppData/Local/RSDragonwilds/Saved
    - Override via the RSDW_SAVE_DIR environment variable.
    """
    if base_path is None:
        # Highest priority: explicit env var override
        env_override = os.environ.get("RSDW_SAVE_DIR")
        if env_override and os.path.isdir(env_override):
            base_path = env_override
        else:
            # Try common platform locations
            candidates = [
                # Windows native
                os.path.expandvars(r"%LOCALAPPDATA%\RSDragonwilds\Saved"),
                # User home (rare layout)
                os.path.expanduser("~/AppData/Local/RSDragonwilds/Saved"),
            ]
            # WSL: scan /mnt/c/Users/* for any user with RSDragonwilds installed
            if os.path.isdir("/mnt/c/Users"):
                try:
                    for user in os.listdir("/mnt/c/Users"):
                        wsl_candidate = f"/mnt/c/Users/{user}/AppData/Local/RSDragonwilds/Saved"
                        if os.path.isdir(wsl_candidate):
                            candidates.append(wsl_candidate)
                except OSError:
                    pass
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
