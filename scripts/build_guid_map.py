#!/usr/bin/env python3
"""
Build the GUID → name mapping from FModel's bulk JSON exports.

Reads every .json file under the FModel export directory (Gameplay/Items,
Quests, Mounts, NPCS, Character, Attributes) and extracts:

    - PersistenceID   (base64url GUID the save file uses)
    - InternalName    (human-friendly internal key)
    - display name    (from Properties.Name.SourceString)
    - category/type   (item, quest, mount, skill, npc, etc.)
    - icon reference  (if present)
    - description     (from FlavourText.SourceString if present)

Writes to data/guid_map.json:

    {
      "F73O1kqSP2Z-Y5SYg9F01A": {
        "type": "item",
        "name": "Infernal Fragment",
        "internal_name": "res_currency_dream_shard",
        "key": "DreamShard",
        "icon": "T_Icon_Infernal_Fragments",
        "description": "Used to craft magical equipment..."
      },
      ...
    }

Usage:
    python scripts/build_guid_map.py [path/to/exports/Gameplay]

The path should point to the FModel JSON exports of Dragonwilds's Gameplay folder.
You can override the default by passing the path as a CLI argument or by setting
the RSDW_FMODEL_EXPORTS environment variable.

Default path is the typical location on Windows after installing FModel and using
the default export directory: ~/OneDrive/Desktop/Output/Exports/RSDragonwilds/Content/Gameplay
"""
import json
import os
import sys
from pathlib import Path
from collections import Counter

# Default export directory. Override via CLI arg or RSDW_FMODEL_EXPORTS env var.
def _default_exports() -> str:
    env = os.environ.get("RSDW_FMODEL_EXPORTS")
    if env:
        return env
    # Try $HOME first, then WSL fallback
    home_path = Path.home() / "OneDrive/Desktop/Output/Exports/RSDragonwilds/Content/Gameplay"
    if home_path.exists():
        return str(home_path)
    # WSL fallback — walk /mnt/c/Users for any user that has the export
    if os.path.isdir("/mnt/c/Users"):
        for user_dir in Path("/mnt/c/Users").iterdir():
            candidate = user_dir / "OneDrive/Desktop/Output/Exports/RSDragonwilds/Content/Gameplay"
            if candidate.exists():
                return str(candidate)
    # Return the home pattern as fallback even if it doesn't exist
    return str(home_path)

DEFAULT_EXPORTS = _default_exports()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "guid_map.json"


def _get_localized(field) -> str | None:
    """If field is a localized-text dict, return the source/localized string."""
    if isinstance(field, dict):
        return field.get("SourceString") or field.get("LocalizedString")
    return None


# Display name lives in different fields for different entity types
NAME_FIELDS = ("Name", "QuestName", "DisplayName", "SpellName", "AbilityName", "MountName", "ItemName")

# Description lives in different fields too
DESC_FIELDS = ("FlavourText", "QuestDescription", "Description", "Tooltip", "DescriptionText")


def extract_name(props: dict) -> str | None:
    """Pull the display name from a Properties block. Tries multiple common field names."""
    for f in NAME_FIELDS:
        v = _get_localized(props.get(f))
        if v:
            return v
    return None


def extract_description(props: dict) -> str | None:
    for f in DESC_FIELDS:
        v = _get_localized(props.get(f))
        if v:
            return v
    return None


def extract_icon(props: dict) -> str | None:
    icon = props.get("Icon")
    if isinstance(icon, dict):
        return icon.get("ObjectName", "").replace("Texture2D'", "").rstrip("'")
    return None


def extract_category(props: dict) -> str | None:
    cat = props.get("Category")
    if isinstance(cat, dict):
        return cat.get("TagName")
    return None


def classify_entry(entry_type: str, package: str) -> str:
    """Infer a category from the entry's Type and Package path."""
    t = entry_type or ""
    p = (package or "").lower()

    # Explicit type mappings
    if t == "ItemData":
        return "item"
    if t == "MountDataAsset":
        return "mount"
    if t == "SkillData":
        return "skill"
    if t == "SkillPerkData":
        return "skill_perk"
    if t == "DominionAttributeData":
        return "attribute"
    if t in ("WearableEquipmentData", "HeldEquipmentData"):
        return "equipment"
    if t in ("QuestData", "QuestDataAsset"):
        return "quest"
    if t in ("SpellDataAsset", "AbilityDataAsset"):
        return "spell"
    if t in ("NpcDataAsset", "NpcData"):
        return "npc"
    if t == "RecipeData":
        return "recipe"
    if t == "DamageTypeDataAsset":
        return "damage_type"

    # Blueprint type patterns (they all end in _C)
    if t.startswith("BP_Consumables_"):
        if "Food" in t:
            return "food"
        if "Plan" in t:
            return "plan"
        if "Recipe" in t:
            return "recipe_unlocker"
        if "Potion" in t:
            return "potion"
        return "consumable"
    if t.startswith("BP_Item_") or "_Item_" in t:
        return "item"

    # Fallback by package path
    if "/items/" in p:
        return "item"
    if "/quests/" in p:
        return "quest"
    if "/mounts/" in p:
        return "mount"
    if "/skills/" in p or "/abilities/" in p:
        return "skill"
    if "/npc" in p:
        return "npc"
    if "/attributes/" in p:
        return "attribute"

    return "unknown"


def process_entry(entry: dict, file_path: Path) -> dict | None:
    """Extract a mapping entry from one JSON object, or return None if not mappable.

    Strategy: any entry with a PersistenceID is captured (that's the save-file GUID).
    Entries without a PersistenceID but with an InternalName + display name are
    captured as name-only fallbacks.
    """
    props = entry.get("Properties", {})
    if not isinstance(props, dict):
        return None

    persistence_id = props.get("PersistenceID")
    internal_name = props.get("InternalName")
    name = extract_name(props)

    # Must have some identifier AND some label
    has_id = bool(persistence_id or internal_name)
    has_label = bool(name or internal_name)
    if not has_id or not has_label:
        return None

    entry_type = entry.get("Type", "")
    package = entry.get("Package", "")

    return {
        "type": classify_entry(entry_type, package),
        "raw_type": entry_type,
        "asset_name": entry.get("Name", ""),
        "package": package,
        "persistence_id": persistence_id,
        "internal_name": internal_name,
        "name": name,
        "key": props.get("Name", {}).get("Key") if isinstance(props.get("Name"), dict) else None,
        "description": extract_description(props),
        "icon": extract_icon(props),
        "category": extract_category(props),
    }


def main():
    exports_dir = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXPORTS)
    if not exports_dir.is_dir():
        print(f"ERROR: exports directory not found: {exports_dir}")
        sys.exit(1)

    print(f"Scanning: {exports_dir}")

    # guid_map indexed by PersistenceID (the save-file form)
    # + a secondary index by internal_name for the cases where PersistenceID is missing
    guid_map: dict[str, dict] = {}
    name_map: dict[str, dict] = {}
    stats = Counter()
    file_count = 0
    entries_scanned = 0

    for json_file in exports_dir.rglob("*.json"):
        file_count += 1
        try:
            with open(json_file) as f:
                data = json.load(f)
        except Exception as e:
            stats["parse_error"] += 1
            continue

        # FModel exports are lists of entries (can be 1 or many per file)
        if not isinstance(data, list):
            data = [data]

        for entry in data:
            if not isinstance(entry, dict):
                continue
            entries_scanned += 1
            mapped = process_entry(entry, json_file)
            if mapped is None:
                continue

            stats[f"type:{mapped['type']}"] += 1

            pid = mapped.get("persistence_id")
            if pid:
                # Dedupe: if same PID appears again, keep the first (they should be identical)
                if pid not in guid_map:
                    guid_map[pid] = mapped
                    stats["with_persistence_id"] += 1
            else:
                iname = mapped.get("internal_name") or mapped.get("asset_name")
                if iname and iname not in name_map:
                    name_map[iname] = mapped
                    stats["by_name_only"] += 1

    # Write outputs
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({
            "by_persistence_id": guid_map,
            "by_internal_name": name_map,
        }, f, indent=2)

    print(f"\nProcessed {file_count:,} JSON files ({entries_scanned:,} entries)")
    print(f"Output written to: {OUTPUT_PATH}")
    print(f"\nStats:")
    for k in sorted(stats):
        print(f"  {k}: {stats[k]:,}")
    print(f"\nTotal GUID entries: {len(guid_map):,}")
    print(f"Total name-only entries: {len(name_map):,}")


if __name__ == "__main__":
    main()
