#!/usr/bin/env python3
"""
Fetch item icons from the RS Dragonwilds wiki using the MediaWiki API.

For each item in data/items.json, resolves the wiki page title (direct match
first, then search as fallback), gets the original image URL via pageimages API,
and downloads the PNG to static/images/items/{item_id}.png.

Records the full mapping in data/icon_map.json so subsequent runs can skip
already-fetched items and we have a record of what the wiki calls each item.

Usage:
    python scripts/fetch_icons.py [--limit N]  # fetch only N items (for testing)
    python scripts/fetch_icons.py --force       # re-fetch even if icon_map has entry

Rate limiting: 0.5 seconds between requests (polite to wiki).
"""
import argparse
import json
import os
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

WIKI_API = "https://dragonwilds.runescape.wiki/api.php"
USER_AGENT = "RSDragonWilds-WorldEditor/1.0 (https://github.com/haithemobeidi/RSDragonWilds-WorldEditor; community save editor)"
RATE_LIMIT_SEC = 0.5

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
ICONS_DIR = os.path.join(PROJECT_ROOT, "static", "images", "items")


def api_request(params: dict) -> dict:
    """GET the MediaWiki API with polite user agent."""
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    url = f"{WIKI_API}?{query}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return json.load(resp)


def download_image(url: str, dest_path: str) -> bool:
    """Download an image from URL to dest_path. Returns True on success."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    download failed: {e}")
        return False


def get_image_url_for_title(title: str) -> tuple[str | None, str | None]:
    """Query pageimages API for a title. Returns (resolved_title, image_url)."""
    try:
        data = api_request({
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "original",
            "titles": title,
        })
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                return None, None
            original = page.get("original", {})
            image_url = original.get("source")
            if image_url:
                return page.get("title", title), image_url
        return None, None
    except Exception as e:
        print(f"    pageimages error: {e}")
        return None, None


def search_for_title(query: str) -> str | None:
    """Use the wiki search to find the best matching page title."""
    try:
        data = api_request({
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
        })
        results = data.get("query", {}).get("search", [])
        if not results:
            return None
        # Skip VESTIGE: prefixed results (not the item itself)
        for r in results:
            title = r.get("title", "")
            if title.lower().startswith("vestige:"):
                continue
            return title
        return results[0].get("title")
    except Exception as e:
        print(f"    search error: {e}")
        return None


def fetch_icon_for_item(item: dict, force: bool, icon_map: dict, overrides: dict) -> dict:
    """
    Try to resolve and download the icon for one item.
    Returns the entry to add to icon_map.
    """
    item_id = item.get("id", "")
    display_name = item.get("display_name") or item.get("item_name") or ""

    if not item_id or not display_name:
        return {"status": "skipped_no_data"}

    # Check if we already have this icon
    existing = icon_map.get(item_id)
    dest_path = os.path.join(ICONS_DIR, f"{item_id}.png")
    if not force and existing and existing.get("status") == "ok" and os.path.exists(dest_path):
        return existing  # already fetched

    # Manual override takes precedence (for known XLSX typos / name mismatches)
    override_title = overrides.get(item_id)
    if override_title:
        resolved_title, image_url = get_image_url_for_title(override_title)
    else:
        # Attempt 1: direct pageimages lookup with the display name
        resolved_title, image_url = get_image_url_for_title(display_name)

        # Attempt 2: if direct lookup failed, search
        if not image_url:
            time.sleep(RATE_LIMIT_SEC)
            search_title = search_for_title(display_name)
            if search_title:
                time.sleep(RATE_LIMIT_SEC)
                resolved_title, image_url = get_image_url_for_title(search_title)

    if not image_url:
        return {
            "status": "not_found",
            "queried_name": display_name,
        }

    # Download
    ok = download_image(image_url, dest_path)
    return {
        "status": "ok" if ok else "download_failed",
        "queried_name": display_name,
        "wiki_title": resolved_title,
        "image_url": image_url,
        "local_path": f"/static/images/items/{item_id}.png" if ok else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Fetch only N items")
    parser.add_argument("--force", action="store_true", help="Re-fetch already-cached icons")
    args = parser.parse_args()

    os.makedirs(ICONS_DIR, exist_ok=True)

    # Load existing icon map (so we can skip already-fetched)
    icon_map_path = os.path.join(DATA_DIR, "icon_map.json")
    icon_map = {}
    if os.path.exists(icon_map_path):
        with open(icon_map_path) as f:
            icon_map = json.load(f)

    # Load manual overrides (for XLSX typos / name mismatches)
    overrides_path = os.path.join(DATA_DIR, "icon_manual_overrides.json")
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path) as f:
            raw = json.load(f)
            overrides = {k: v for k, v in raw.items() if not k.startswith("_")}

    # Load items
    items_path = os.path.join(DATA_DIR, "items.json")
    with open(items_path) as f:
        items = json.load(f)

    if args.limit > 0:
        items = items[: args.limit]

    print(f"Fetching icons for {len(items)} items...")
    print(f"  Rate limit: {RATE_LIMIT_SEC}s between requests")
    print(f"  Cache: {len([v for v in icon_map.values() if v.get('status') == 'ok'])} already ok")
    print()

    stats = {"ok": 0, "skipped": 0, "not_found": 0, "failed": 0}

    for i, item in enumerate(items):
        item_id = item.get("id", "?")
        name = item.get("display_name", "?")
        existing = icon_map.get(item_id, {})
        # Re-attempt not_found items AND skipped items (cheap to retry since
        # overrides may have been added since last run)
        has_override = item_id in overrides
        if not args.force and existing.get("status") == "ok" and not has_override:
            stats["skipped"] += 1
            continue

        print(f"[{i+1}/{len(items)}] {item_id}: {name}{' (override)' if has_override else ''}")
        result = fetch_icon_for_item(item, args.force, icon_map, overrides)
        icon_map[item_id] = result

        status = result.get("status", "unknown")
        if status == "ok":
            stats["ok"] += 1
            print(f"    ✓ {result.get('wiki_title')}")
        elif status == "not_found":
            stats["not_found"] += 1
            print(f"    ✗ not found")
        else:
            stats["failed"] += 1
            print(f"    ✗ {status}")

        # Save progress after every item (resumable)
        with open(icon_map_path, "w") as f:
            json.dump(icon_map, f, indent=2)

        time.sleep(RATE_LIMIT_SEC)

    print()
    print(f"Done. Stats:")
    print(f"  OK:        {stats['ok']}")
    print(f"  Skipped:   {stats['skipped']} (already cached)")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Failed:    {stats['failed']}")


if __name__ == "__main__":
    main()
