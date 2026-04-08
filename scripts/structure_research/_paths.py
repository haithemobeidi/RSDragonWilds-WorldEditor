"""
Cross-platform path resolution for Dragonwilds save and cache directories.

Detection priority:
  1. Environment variable (RSDW_SAVES_DIR / RSDW_CACHE_DIR) — explicit user override
  2. Native Windows: Path.home() / "AppData/Local/RSDragonwilds/Saved/..."
  3. WSL detection: /mnt/c/Users/<WindowsUser>/AppData/Local/RSDragonwilds/Saved/...
     (tries the current $USER first, then common Windows usernames)
  4. macOS / Linux Steam Proton: standard Steam compatdata path
  5. Returns the most plausible path even if it doesn't exist (caller checks)

Override at any time by setting RSDW_SAVES_DIR or RSDW_CACHE_DIR.
"""
import os
import sys
from pathlib import Path


def is_wsl() -> bool:
    """Detect if we're running inside WSL."""
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower() or "wsl" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def find_saves_dir() -> Path:
    """Locate the Dragonwilds SaveGames directory."""
    # 1. Explicit env override
    env = os.environ.get("RSDW_SAVES_DIR")
    if env:
        return Path(env)

    # 2. Native Windows
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "RSDragonwilds" / "Saved" / "SaveGames"

    # 3. WSL — try /mnt/c/Users/<username>
    if is_wsl():
        # Try $USER first
        user = os.environ.get("USER")
        if user:
            candidate = Path(f"/mnt/c/Users/{user}/AppData/Local/RSDragonwilds/Saved/SaveGames")
            if candidate.parent.parent.parent.exists():  # check Local exists
                return candidate
        # Walk /mnt/c/Users for any user that has the game folder
        users_dir = Path("/mnt/c/Users")
        if users_dir.exists():
            for user_home in users_dir.iterdir():
                candidate = user_home / "AppData/Local/RSDragonwilds/Saved/SaveGames"
                if candidate.exists():
                    return candidate

    # 4. Linux native (Steam Proton compatdata)
    # The Dragonwilds Steam app ID is needed; common pattern:
    proton_base = Path.home() / ".steam/steam/steamapps/compatdata"
    if proton_base.exists():
        for app_dir in proton_base.iterdir():
            candidate = app_dir / "pfx/drive_c/users/steamuser/AppData/Local/RSDragonwilds/Saved/SaveGames"
            if candidate.exists():
                return candidate

    # 5. Fallback — return the Windows home pattern even if it doesn't exist,
    # so the caller gets a clear error if invoked.
    return Path.home() / "AppData" / "Local" / "RSDragonwilds" / "Saved" / "SaveGames"


def find_cache_dir() -> Path:
    """Locate the Dragonwilds SpudCache directory."""
    env = os.environ.get("RSDW_CACHE_DIR")
    if env:
        return Path(env)
    # SpudCache lives next to SaveGames
    return find_saves_dir().parent / "SpudCache"
