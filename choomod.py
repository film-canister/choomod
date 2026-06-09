#!/usr/bin/env python3
"""
ChooMod - Cyberpunk 2077 Mod Manager for Linux
Supports: GOG via Heroic, Steam via Proton
"""

import json
import asyncio
import os
import shutil
import zipfile
import py7zr
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label,
    Static, Switch, TabbedContent, TabPane
)

# ─── Constants ────────────────────────────────────────────────────────────────

APP_VERSION = "1.2.0-dev"
MANIFEST_FILE = Path.home() / ".config" / "choomod" / "manifest.json"

# Known CP2077 install locations to scan
SEARCH_PATHS = {
    "heroic_default":   Path.home() / "Games" / "Heroic" / "Cyberpunk 2077",
    "heroic_alt":       Path.home() / "GOG Games" / "Cyberpunk 2077",
    "heroic_legacy":    Path.home() / ".local" / "share" / "heroic" / "GOG Games" / "Cyberpunk 2077",
    "steam_native":     Path.home() / ".steam" / "steam" / "steamapps" / "common" / "Cyberpunk 2077",
    "steam_flatpak":    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "common" / "Cyberpunk 2077",
    "heroic_flatpak":   Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "GOG Games" / "Cyberpunk 2077",
}

def scan_heroic_config() -> Path | None:
    """Try to find the game path by reading Heroic's installed games manifest."""
    paths = [
        Path.home() / ".config" / "heroic" / "gog_store" / "installed.json",
        Path.home() / ".config" / "heroic" / "sideloaded_games" / "installed.json"
    ]
    for p in paths:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for game in data.get("installed", []):
                    if "Cyberpunk 2077" in game.get("title", ""):
                        install_path = Path(game.get("installPath", ""))
                        if install_path.exists():
                            return install_path
            except Exception:
                continue
    return None

# ─────────────────────────────────────────────────────────────────────────────
# FILE ROUTING TABLE
# ─────────────────────────────────────────────────────────────────────────────
# This is the core of the zip installer.
# Each entry is: (rule_type, pattern, destination_relative_to_game_root)
#
# rule_type "path"   = the file's path inside the zip contains this string
# rule_type "suffix" = the file has this extension
#
# Order matters — more specific rules go first.
# When a file matches a rule, we stop checking and use that destination.
#
# Think of this as the "knowledge base" of CP2077 mod structure.
# Adding support for a new mod type = adding a row here.
# ─────────────────────────────────────────────────────────────────────────────

FILE_ROUTES = [
    # (rule_type, pattern,                       destination,                required_framework)

    # Specific Framework files (handles archives missing full directory structures)
    ("name",   "RED4ext.dll",                    "bin/x64",                  "Red4Ext"),
    ("name",   "scc.exe",                        "engine/tools",             "Redscript"),
    ("name",   "scc_lib.dll",                    "engine/tools",             "Redscript"),

    # Redscript compiler directory
    ("path",   "engine/tools",                   "engine/tools",             "Redscript"),

    # ArchiveXL extension files — must come before generic .archive rule
    ("suffix", ".archive.xl",                    "archive/pc/mod",           "ArchiveXL"),

    # ArchiveXL resource files
    ("suffix", ".xl",                            "archive/pc/mod",           "ArchiveXL"),

    # Codeware (Redscript dependency)
    ("path",   "codeware/",                      "r6/scripts",               "Redscript"),

    # Standard mod archives
    ("suffix", ".archive",                       "archive/pc/mod",           None),

    # Red4Ext plugin folders — must come before r6/scripts rule
    # to catch .reds files that live inside red4ext/plugins/
    ("path", "red4ext/plugins",                 "red4ext/plugins",          "Red4Ext"),

    # Redscript source files
    ("path",   "r6/scripts",                     "r6/scripts",               "Redscript"),

    # TweakXL yaml patches
    ("path",   "r6/tweaks",                      "r6/tweaks",                "TweakXL"),

    # User config / hints (toml, ini etc)
    ("path",   "r6/config",                      "r6/config",                None),

    # Input bindings
    ("path",   "r6/input",                       "r6/input",                 None),

    # Engine config files
    ("path", "engine/config", "engine/config",          None),

    # Redscript cache
    ("path", "r6/cache", "r6/cache",                None),

    # Cyber Engine Tweaks mods (lua scripts)
    ("path",   "bin/x64/plugins/cyber_engine_tweaks", "bin/x64/plugins/cyber_engine_tweaks", "Cyber Engine Tweaks"),

    # Red4Ext DLLs and plugins
    ("path",   "bin/x64",                        "bin/x64",                  "Red4Ext"),
]

FRAMEWORK_MODS = [
    {
        "name": "Cyber Engine Tweaks",
        "check_path": "bin/x64/plugins/cyber_engine_tweaks",
        "url": "https://github.com/maximegmd/CyberEngineTweaks",
        "nexus_url": "https://www.nexusmods.com/cyberpunk2077/mods/107"
    },
    {
        "name": "Red4Ext",
        "check_path": "red4ext",
        "url": "https://github.com/WopsS/RED4ext",
        "nexus_url": "https://www.nexusmods.com/cyberpunk2077/mods/2380"
    },
    {
        "name": "Redscript",
        "check_path": "engine/tools/scc.exe",
        "url": "https://github.com/jac3km4/redscript",
        "nexus_url": "https://www.nexusmods.com/cyberpunk2077/mods/1511"
    },
    {
        "name": "ArchiveXL",
        "check_path": "red4ext/plugins/ArchiveXL",
        "url": "https://github.com/psiberx/cp2077-archive-xl",
        "nexus_url": "https://www.nexusmods.com/cyberpunk2077/mods/4198"
    },
    {
        "name": "TweakXL",
        "check_path": "red4ext/plugins/TweakXL",
        "url": "https://github.com/psiberx/cp2077-tweak-xl",
        "nexus_url": "https://www.nexusmods.com/cyberpunk2077/mods/4197"
    },
    {
        "name": "Codeware",
        "check_path": "r6/scripts/Codeware",
        "url": "https://github.com/psiberx/cp2077-codeware",
        "nexus_url": "https://www.nexusmods.com/cyberpunk2077/mods/7381"
    },
]

def check_frameworks(game_path: Path) -> list[dict]:
    results = []
    
    for framework in FRAMEWORK_MODS:
        rel_path = Path(framework["check_path"])
        full_path = game_path / rel_path
        
        # 1. Direct check (handles exact match and .disabled variants)
        installed = full_path.exists() or Path(str(full_path) + ".disabled").exists()
        
        # 2. Case-insensitive fallback (crucial for Linux compatibility)
        if not installed:
            parent = game_path / rel_path.parent
            if parent.exists():
                target_lower = rel_path.name.lower()
                for item in parent.iterdir():
                    item_name_lower = item.name.lower()
                    if item_name_lower == target_lower or item_name_lower == target_lower + ".disabled":
                        installed = True
                        break

        results.append({
            "name": framework["name"],
            "installed": installed,
            "url": framework["url"],
            "nexus_url": framework["nexus_url"],
        })
    
    return results

# Extensions we recognise but deliberately skip (readmes, screenshots etc)
SKIP_EXTENSIONS = {".txt", ".md", ".png", ".jpg", ".jpeg", ".pdf", ".url", ".gif"}

# ─── Detection ────────────────────────────────────────────────────────────────

def detect_game() -> tuple[str | None, Path | None, str]:
    # 1. Try Heroic config first (most accurate)
    heroic_path = scan_heroic_config()
    if heroic_path:
        return "GOG (Heroic)", heroic_path, f"Detected via Heroic config at {heroic_path}"

    # 2. Fall back to brute-force scanning
    for key, path in SEARCH_PATHS.items():
        if path.exists() and (path / "bin").exists():
            launcher = "GOG (Heroic)" if "heroic" in key or "gog" in key.lower() else "Steam"
            return launcher, path, f"Found via {launcher} at {path}"
    return None, None, "Game not found. Set path manually in Settings."


def _route_file(entry_path: str) -> tuple[str | None, str | None]:
    """Determine the destination directory and framework requirement for a file."""
    entry_lower = entry_path.lower()
    entry_name_lower = Path(entry_path).name.lower()
    for rule_type, pattern, dest, req in FILE_ROUTES:
        if rule_type == "suffix" and entry_lower.endswith(pattern.lower()):
            return dest, req
        elif rule_type == "name" and entry_name_lower == pattern.lower():
            return dest, req
        elif rule_type == "path" and pattern.lower() in entry_lower:
            return dest, req
    return None, None


def _get_relative_subpath(entry_path: str, destination: str) -> Path:
    """
    Calculates the subpath relative to the route root to preserve folder structures.
    Example: r6/scripts/mod/script.reds + destination r6/scripts -> mod/script.reds
    """
    p = Path(entry_path)
    p_parts = p.parts
    dest_root_parts = Path(destination).parts
    last_dest_part = dest_root_parts[-1]

    try:
        # Use case-insensitive matching for the anchor folder (e.g., match 'Scripts' to 'scripts')
        p_parts_lower = [part.lower() for part in p_parts]
        idx = p_parts_lower.index(last_dest_part.lower())
        return Path(*p_parts[idx + 1:]) if idx + 1 < len(p_parts) else Path(p.name)
    except ValueError:
        return Path(p.name)


class ArchiveHandler:
    """Unified interface for zip, 7z, and rar archives."""
    def __init__(self, path: Path):
        self.path = path
        suffix = path.suffix.lower()
        self.is_7z = suffix == ".7z"
        self.is_rar = suffix == ".rar"

    def __enter__(self):
        if self.is_7z:
            try:
                self.archive = py7zr.SevenZipFile(self.path, mode='r')
            except NameError:
                raise ImportError("The 'py7zr' library is required for .7z files. Install it with: pip install py7zr")
        elif self.is_rar:
            try:
                import rarfile
                self.archive = rarfile.RarFile(self.path, mode='r')
            except ImportError:
                raise ImportError("The 'rarfile' library is required for .rar files. Install it with: pip install rarfile\nNote: You may also need the 'unrar' package installed on your system.")
        else:
            self.archive = zipfile.ZipFile(self.path, 'r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.archive.close()

    def get_entries(self) -> list[str]:
        return self.archive.getnames() if (self.is_7z or self.is_rar) else self.archive.namelist()

    def open_entry(self, name: str):
        if self.is_7z:
            # Returns a BytesIO object for consistency with zipfile.open()
            return list(self.archive.read(targets=[name]).values())[0]
        return self.archive.open(name)


def get_mod_dir(game_path: Path) -> Path:
    return game_path / "archive" / "pc" / "mod"


# ─── Manifest ─────────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text())
        except Exception:
            pass
    return {"mods": {}, "game_path": None, "launcher": None}


def save_manifest(data: dict):
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(data, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# ZIP INSPECTOR
# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 of the install process: look before touching anything.
#
# We open the zip and sort every file into one of four buckets:
#   auto      — we know exactly where this goes, install confidently
#   ambiguous — it's inside an Optional/Variant folder, ask the user
#   unknown   — we have no idea, warn the user
#   skip      — readme/image/etc, ignore silently
#
# This function never writes anything. It only reads and plans.
# The actual file writing happens in install_from_plan() below.
# Keeping inspect and install separate is called the "dry run" pattern —
# it means you can always show the user what WILL happen before it does.
# ─────────────────────────────────────────────────────────────────────────────

def inspect_zip(zip_path: Path) -> dict:
    """
    Inspect a zip and return an install plan without touching any files.
    Returns:
        {
            "auto":      [(zip_entry, destination_dir), ...],
            "ambiguous": [(zip_entry, destination_dir), ...],
            "unknown":   [zip_entry, ...],
            "skip":      [zip_entry, ...],
            "requirements": set(),
        }
    """
    plan = {"auto": [], "ambiguous": [], "unknown": [], "skip": [], "requirements": set()}

    # Keywords that suggest a file is optional or a variant.
    # If a file lives inside a folder with one of these names,
    # we flag it as ambiguous instead of auto-installing.
    ambiguous_keywords = {"optional", "variant", "alternative", "alt", "choose", "option"}

    with ArchiveHandler(zip_path) as zf:
        for entry in zf.get_entries():
            # skip folder entries ending in /
            if entry.endswith("/"):
                continue

            p = Path(entry)
            if p.suffix.lower() in SKIP_EXTENSIONS:
                plan["skip"].append(entry)
                continue

            destination, requirement = _route_file(entry)

            parts_lower = {part.lower() for part in p.parts}
            is_ambiguous = bool(parts_lower & ambiguous_keywords)

            if destination and not is_ambiguous:
                plan["auto"].append((entry, destination))
                if requirement:
                    plan["requirements"].add(requirement)
            elif destination and is_ambiguous:
                plan["ambiguous"].append((entry, destination))
            else:
                plan["unknown"].append(entry)

    return plan

def format_plan_summary(plan: dict) -> str:
    lines = []
    if plan["auto"]:
        lines.append(f"[green]✓ Auto-install ({len(plan['auto'])} files):[/green]")
        for entry, dest in plan["auto"]:
            lines.append(f"  {Path(entry).name}  →  {dest}")

    if plan["ambiguous"]:
        lines.append(f"\n[yellow]⚠ Optional/Variant files ({len(plan['ambiguous'])} files) — skipped for now:[/yellow]")
        for entry, dest in plan["ambiguous"]:
            lines.append(f"  {Path(entry).name}  ({Path(entry).parent})")

    if plan["unknown"]:
        lines.append(f"\n[red]✗ Unknown files ({len(plan['unknown'])}) — will not be installed:[/red]")
        for entry in plan["unknown"]:
            lines.append(f"  {entry}")

    if plan["skip"]:
        lines.append(f"\n[dim]— Skipped ({len(plan['skip'])} readme/image files)[/dim]")

    if not plan["auto"] and not plan["ambiguous"]:
        lines.append("[red]No installable files found in this zip.[/red]")

    return "\n".join(lines)

def check_conflicts(plan: dict, manifest: dict, game_path: Path) -> list[dict]:
    conflicts = []
    for zip_entry, destination in plan["auto"]:
        relative_subpath = _get_relative_subpath(zip_entry, destination)
        full_dest = str(game_path / destination / relative_subpath)
        existing_owner = find_manifest_entry(full_dest, manifest)
        if existing_owner:
            conflicts.append({
                "file": Path(zip_entry).name,
                "owned_by": existing_owner,
            })

    return conflicts

def check_dependencies(plan: dict, game_path: Path, manifest: dict) -> list[str]:
    """Compare plan requirements against installed frameworks."""
    reqs = plan.get("requirements", set())
    if not reqs:
        return []

    frameworks = check_frameworks(game_path)
    managed_mods = manifest.get("mods", {})
    # Check both if the file exists AND if it is managed/enabled by ChooMod
    status_map = {}
    for fw in frameworks:
        is_installed = fw["installed"]
        # If the framework is managed, ensure it's actually enabled
        if fw["name"] in managed_mods:
            if not managed_mods[fw["name"]].get("enabled", True):
                is_installed = False
        status_map[fw["name"]] = is_installed
    
    return [req for req in reqs if not status_map.get(req, False)]

# ─────────────────────────────────────────────────────────────────────────────
# ZIP INSTALLER
# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Execute the plan produced by inspect_zip().
#
# For each (zip_entry, destination) in plan["auto"]:
#   - Preserve the subfolder structure relative to the route root.
#     e.g. r6/scripts/virtual-atelier-full/core/Classes.reds
#     route root = "r6/scripts"
#     subfolder  = "virtual-atelier-full/core"
#     final path = game_path/r6/scripts/virtual-atelier-full/core/Classes.reds
#     This matters — dumping all .reds into a flat folder would break things.
#
# Every file we write gets recorded in installed_files.
# That list is stored in the manifest and is how uninstall works later.
# ─────────────────────────────────────────────────────────────────────────────

def install_from_plan(
    zip_path: Path,
    plan: dict,
    game_path: Path,
    manifest: dict,
    mod_name: str
) -> tuple[bool, str, list[str]]:
    """
    Install auto-routed files from a zip into the game directory.
    Returns (success, message, list_of_installed_file_paths).
    """
    installed_files = []
    total = len(plan["auto"])

    try:
        with ArchiveHandler(zip_path) as zf:
            for zip_entry, destination in plan["auto"]:
                relative_subpath = _get_relative_subpath(zip_entry, destination)
                dest_path = game_path / destination / relative_subpath
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Extract and write the file
                with zf.open_entry(zip_entry) as src, open(dest_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                
                installed_files.append(str(dest_path))
    except Exception as e:
        # ROLLBACK: If any file fails, delete everything we installed so far
        for file_to_undo in installed_files:
            p_to_undo = Path(file_to_undo)
            if p_to_undo.exists():
                p_to_undo.unlink()
        
        return False, f"Install failed: {e}. Rollback complete.", []

    if not installed_files:
        return False, "No files were installed.", []

    # ── Record in manifest ─────────────────────────────────────────────────
    # This is what makes uninstall possible later.
    # We store every file path we wrote, plus metadata

    
    manifest.setdefault("mods", {})[mod_name] = {
        "installed_files": installed_files,
        "category": "Uncategorised",
        "notes": "",
        "added": datetime.now().strftime("%Y-%m-%d"),
        "source_zip": str(zip_path),
        "enabled": True,
    }
    save_manifest(manifest)

    # Force a script recompile to prevent "Missing Dependency" errors
    clear_redscript_cache(game_path)

    return True, f"Successfully installed {len(installed_files)} files.", installed_files


# ─────────────────────────────────────────────────────────────────────────────
# UNINSTALLER
# ─────────────────────────────────────────────────────────────────────────────
# Because install_from_plan() recorded every file it wrote,
# uninstalling is just: read the list, delete each file.
# No guessing, no leftover files.
# ─────────────────────────────────────────────────────────────────────────────

def uninstall_mod(mod_name: str, manifest: dict) -> tuple[bool, str]:
    mod_data = manifest.get("mods", {}).get(mod_name)
    if not mod_data:
        return False, f"No install record for '{mod_name}'"

    files = mod_data.get("installed_files", [])
    removed = 0
    errors = []

    for file_str in files:
        p = Path(file_str)
        # We check both the original path and the '.disabled' variant 
        # to ensure toggled mods are still cleaned up.
        targets = [p, Path(str(p) + ".disabled")]
        
        for target in targets:
            try:
                if target.exists():
                    target.unlink()
                    removed += 1
                    # Clean up empty parent directories
                    try:
                        target.parent.rmdir()
                    except OSError:
                        pass
            except Exception as e:
                errors.append(f"Failed to delete {target.name}: {e}")

    del manifest["mods"][mod_name]
    save_manifest(manifest)

    if errors:
        return False, f"Removed {removed} files with {len(errors)} errors"
    return True, f"Uninstalled '{mod_name}' — {removed} files removed"


# ─── Mod scanning (for mods installed outside ChooMod) ───────────────────────

def find_manifest_entry(file_path: str, manifest: dict):
    # Normalize: if the file on disk is currently '.disabled', 
    # we look for its original 'active' path in the manifest.
    search_path = file_path.replace(".disabled", "")

    for mod_name, mod_data in manifest.get("mods", {}).items():
        for installed_file in mod_data.get("installed_files", []):
            # Match exact file path OR check if the installed file is inside this directory
            if installed_file == search_path or installed_file.startswith(search_path + "/"):
                return mod_name
    return None

def scan_mods(game_path: Path, manifest: dict) -> list[dict]:
    """
    Scans the game directory for mods.
    1. Finds archives in archive/pc/mod (managed and unmanaged)
    2. Finds unmanaged script/plugin folders in r6/scripts and red4ext/plugins
    3. Adds managed mods from manifest that don't have archives
    """
    mod_dir = get_mod_dir(game_path)
    mods = []

    handled_manifest_keys = set()
    managed = manifest.get("mods", {})

    # 1. Scan for all archive files (enabled and disabled)
    archive_files = []
    if mod_dir.exists():
        archive_files = sorted(list(mod_dir.glob("*.archive")) + list(mod_dir.glob("*.archive.disabled")))

    for f in archive_files:
        managed_key = find_manifest_entry(str(f).replace(".disabled", ""), manifest)
        
        if managed_key:
            # This file belongs to a mod we track in the manifest.
            # We only add the entry once, even if it has multiple archives.
            if managed_key not in handled_manifest_keys:
                meta = managed[managed_key]
                mods.append({
                    "name": managed_key,
                    "file": str(f),
                    "enabled": not str(f).endswith(".disabled"),
                    "size_kb": round(f.stat().st_size / 1024),
                    "category": meta.get("category", "Uncategorised"),
                    "notes": meta.get("notes", ""),
                    "added": meta.get("added", "Unknown"),
                    "managed": True,
                    "manifest_key": managed_key,
                    "file_count": len(meta.get("installed_files", [])),
                })
                handled_manifest_keys.add(managed_key)
        else:
            # This is an unmanaged mod file on disk.
            name = f.name.replace(".archive.disabled", "").replace(".archive", "")
            mods.append({
                "name": name,
                "file": str(f),
                "enabled": not str(f).endswith(".disabled"),
                "size_kb": round(f.stat().st_size / 1024),
                "category": "Unmanaged",
                "notes": "Drag-and-drop install",
                "added": "Unknown",
                "managed": False,
                "file_count": 1,
            })
            
    # 1.5 Scan for unmanaged scripts and plugins (folders)
    search_dirs = [
        (game_path / "r6" / "scripts", "Unmanaged Script"),
        (game_path / "red4ext" / "plugins", "Unmanaged Plugin")
    ]
    for root_dir, cat in search_dirs:
        if root_dir.exists():
            for item in root_dir.iterdir():
                if item.is_dir() and not find_manifest_entry(str(item), manifest):
                    # Check if it's already in our list (could be if it has an archive too)
                    if any(m["name"] == item.name.replace(".disabled", "") for m in mods):
                        continue
                    
                    mods.append({
                        "name": item.name.replace(".disabled", ""),
                        "file": str(item),
                        "enabled": not item.name.endswith(".disabled"),
                        "size_kb": 0,
                        "category": cat,
                        "notes": "Folder-based mod",
                        "added": "Unknown",
                        "managed": False,
                        "file_count": 1,
                    })

    # 2. Add managed mods that have NO .archive files at all (CET, Redscript, etc.)
    for mod_name, mod_data in managed.items():
        if mod_name not in handled_manifest_keys:
            mods.append({
                "name": mod_name,
                "file": mod_data.get("source_zip", ""),
                "enabled": True,
                "size_kb": 0,
                "category": mod_data.get("category", "Script/Plugin"),
                "notes": mod_data.get("notes", ""),
                "added": mod_data.get("added", "Unknown"),
                "managed": True,
                "manifest_key": mod_name,
                "file_count": len(mod_data.get("installed_files", [])),
            })

    return mods


def clear_redscript_cache(game_path: Path) -> list[str]:
    """Deletes the Redscript cache to force a recompile."""
    deleted = []
    cache_files = [
        game_path / "r6" / "cache" / "final.redscripts",
        game_path / "r6" / "cache" / "final.redscripts.bk",
        game_path / "r6" / "logs" / "redscript.log",
        game_path / "red4ext" / "cache" / "final.redscripts"
    ]
    
    # Wipe the entire modded cache directory if it exists
    modded_dir = game_path / "r6" / "cache" / "modded"
    if modded_dir.exists():
        try:
            shutil.rmtree(modded_dir)
            deleted.append("r6/cache/modded/")
        except Exception:
            # If we can't remove the dir, we'll try to individual files via the loop below
            pass

    for cf in cache_files:
        try:
            if cf.exists():
                cf.unlink()
                deleted.append(cf.name)
        except Exception:
            pass
    return deleted

def toggle_mod(mod: dict, game_path: Path, manifest: dict) -> tuple[bool, str]:
    """
    Toggle a mod on or off.

    For managed mods: renames every tracked file in the manifest,
    not just the .archive. This ensures scripts, plugins, and config
    files are all disabled — not just the archive.

    For unmanaged mods: falls back to renaming just the .archive file.
    """
    enabling = not mod["enabled"]
    action = "Enabled" if enabling else "Disabled"

    # ── Managed mod — rename all tracked files ────────────────────────────
    managed_key = mod.get("manifest_key")
    if managed_key and managed_key in manifest.get("mods", {}):
        tracked_files = manifest["mods"][managed_key].get("installed_files", [])
        renamed = []
        errors = []

        for file_str in tracked_files:
            f = Path(file_str)
            if enabling:
                disabled_path = Path(str(f) + ".disabled")
                if disabled_path.exists():
                    try:
                        disabled_path.rename(f)
                        renamed.append(str(f))
                    except Exception as e:
                        errors.append(f"{f.name}: {e}")
            else:
                if f.exists():
                    disabled_path = Path(str(f) + ".disabled")
                    try:
                        f.rename(disabled_path)
                        renamed.append(str(f))
                    except Exception as e:
                        errors.append(f"{f.name}: {e}")

        if errors:
            clear_redscript_cache(game_path)
            return False, f"{action} {mod['name']} with errors: {'; '.join(errors)}"
        
        clear_redscript_cache(game_path)
        return True, f"{action} {mod['name']} ({len(renamed)} files)"

    # ── Unmanaged mod — archive only ──────────────────────────────────────
    f = Path(mod["file"])
    try:
        if mod["enabled"]:
            dest = Path(str(f) + ".disabled")
            f.rename(dest)
            clear_redscript_cache(game_path)
            return True, f"Disabled {mod['name']} (unmanaged)"
        else:
            # Remove .disabled from the end of the name
            new_name = f.name.removesuffix(".disabled")
            dest = f.parent / new_name
            f.rename(dest)
            clear_redscript_cache(game_path)
            return True, f"Enabled {mod['name']} (unmanaged)"
    except Exception as e:
        return False, f"Error: {e}"

# ─── Screens ──────────────────────────────────────────────────────────────────

class MessageModal(ModalScreen):
    BINDINGS = [Binding("escape,enter,q", "dismiss", "Close")]

    def __init__(self, message: str, title: str = "Info"):
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label(self._title, id="modal-title")
            yield Static(self._message, id="modal-body")
            yield Button("OK", id="modal-ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()

class ConfirmModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, message: str, title: str = "Confirm"):
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label(self._title, id="modal-title")
            yield Static(self._message, id="modal-body")
            with Horizontal(id="modal-btns"):
                yield Button("Confirm", id="confirm-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "confirm-btn")

class InstallPreviewModal(ModalScreen):
    """Show the install plan and ask for confirmation before writing any files."""
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, zip_name: str, plan: dict, conflicts: list, missing_deps: list):
        super().__init__()
        self._zip_name = zip_name
        self._plan = plan
        self._conflicts = conflicts
        self._missing_deps = missing_deps

    def compose(self) -> ComposeResult:
        with Container(id="modal-box-wide"):
            yield Label(f"Install: {self._zip_name}", id="modal-title")
            with ScrollableContainer(id="modal-scroll"):
                yield Static(format_plan_summary(self._plan), id="modal-plan")
                if self._missing_deps:
                    dep_lines = ["[yellow]⚠ Missing Dependencies:[/yellow]"]
                    for dep in self._missing_deps:
                        dep_lines.append(f"  [yellow]• {dep}[/yellow] is required for some files")
                    yield Static("\n".join(dep_lines), id="modal-deps")
                if self._conflicts:
                    conflict_lines = ["[red]⚠ Conflicts detected:[/red]"]
                    for c in self._conflicts:
                        conflict_lines.append(f"  [red]{c['file']}[/red] already owned by [yellow]{c['owned_by']}[/yellow]")
                    yield Static("\n".join(conflict_lines), id="modal-conflicts")
            with Horizontal(id="modal-btns"):
                can_install = bool(self._plan["auto"])
                yield Button(
                    f"Install {len(self._plan['auto'])} files",
                    id="confirm-btn",
                    variant="primary",
                    disabled=not can_install
                )
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "confirm-btn")


class SetPathModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label("Set Game Path", id="modal-title")
            yield Label("Enter the full path to your Cyberpunk 2077 folder:", id="modal-body")
            yield Input(placeholder="/home/user/Games/Cyberpunk 2077", id="path-input")
            with Horizontal(id="modal-btns"):
                yield Button("Set Path", id="set-path-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "set-path-btn":
            val = self.query_one("#path-input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)


class InstallZipModal(ModalScreen):
    """Ask for the path to a zip file to install."""
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label("Install Mod from Zip", id="modal-title")
            yield Label("Enter the full path to the mod file (.zip, .7z, .rar):", id="modal-body")
            yield Input(placeholder="/path/to/mod.zip, .7z, or .rar", id="zip-input")
            with Horizontal(id="modal-btns"):
                yield Button("Inspect", id="inspect-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "inspect-btn":
            val = self.query_one("#zip-input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)


class EditModModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, mod: dict):
        super().__init__()
        self._mod = mod

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label(f"Edit: {self._mod['name']}", id="modal-title")
            yield Label("Category:", classes="field-label")
            yield Input(value=self._mod.get("category", ""), id="cat-input",
                        placeholder="e.g. Visual, Gameplay, QoL")
            yield Label("Notes:", classes="field-label")
            yield Input(value=self._mod.get("notes", ""), id="notes-input",
                        placeholder="Optional notes")
            with Horizontal(id="modal-btns"):
                yield Button("Save", id="save-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save-btn":
            cat = self.query_one("#cat-input", Input).value.strip()
            notes = self.query_one("#notes-input", Input).value.strip()
            self.dismiss({"category": cat or "Uncategorised", "notes": notes})
        else:
            self.dismiss(None)


class BootScreen(Screen):
    """
    Cyberpunk-themed startup sequence.
    Plays before the main app loads.
    Press any key to skip.
    """

    BINDINGS = [Binding("space,enter,escape", "skip", "Skip")]

    def __init__(self, launcher: str | None, game_path: str | None):
        super().__init__()
        self._launcher = launcher
        self._game_path = game_path
        self._skipped = False

    def compose(self) -> ComposeResult:
        with Container(id="boot-container"):
            yield Static(self._logo(), id="boot-logo")
            yield Vertical(id="boot-lines")
            yield Static("  [dim]PRESS ANY KEY TO SKIP[/dim]", id="boot-skip-hint")

    def _logo(self) -> str:
        return (
            f"  [yellow]╔══════╗[/yellow]\n"
            f"  [yellow]║  CM  ║[/yellow]\n"
            f"  [yellow]╠══════╣[/yellow]  [bold yellow]CHOOMOD[/bold yellow]\n"
            f"  [yellow]║ v{APP_VERSION} ║[/yellow]  [dim]CP2077 Mod Manager // Linux[/dim]\n"
            f"  [yellow]╚══════╝[/yellow]"
        )

    async def on_mount(self) -> None:
        self.run_worker(self._boot_sequence(), exclusive=True)

    async def _boot_sequence(self) -> None:
        lines_container = self.query_one("#boot-lines", Vertical)

        game_found = self._game_path is not None
        launcher_str = self._launcher or "UNKNOWN"

        boot_lines = [
            ("  [cyan]> [/cyan] INITIALIZING CHOOMOD...", None, 0.15),
            (
                "  [cyan]> [/cyan] SCANNING FOR GAME INSTALLATION...",
                f"[green][ {launcher_str.upper()} ][/green]" if game_found else "[red][ NOT FOUND ][/red]",
                0.20,
            ),
            ("  [cyan]> [/cyan] LOADING MANIFEST...", "[green][ OK ][/green]", 0.15),
            ("  [cyan]> [/cyan] CHECKING FRAMEWORK INTEGRITY...", "[green][ OK ][/green]", 0.20),
            ("  [cyan]> [/cyan] ALL SYSTEMS NOMINAL.", None, 0.30),
            ("", None, 0.10),
            ("  [bold yellow]WELCOME BACK, CHOOM.[/bold yellow]", None, 0.60),
        ]

        for line_text, status, delay in boot_lines:
            if self._skipped:
                break
            label = Static(line_text, classes="boot-line")
            await lines_container.mount(label)
            if status:
                await asyncio.sleep(0.10)
                if not self._skipped:
                    label.update(f"{line_text}  {status}")
            await asyncio.sleep(delay)

        if not self._skipped:
            await asyncio.sleep(0.4)
        self._launch_main()

    def _launch_main(self) -> None:
        self.app.switch_screen("main")

    def action_skip(self) -> None:
        self._skipped = True
        self._launch_main()

    def on_key(self) -> None:
        self.action_skip()


# ─── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
#boot-container {
    align: center middle;
    height: 1fr;
    background: #0a0a0f;
    padding: 4 6;
}

#boot-logo {
    color: #FCE300;
    height: auto;
    margin-bottom: 2;
}

#boot-lines {
    height: auto;
    min-height: 10;
}

.boot-line {
    color: #c8c8d8;
    height: auto;
}

#boot-skip-hint {
    margin-top: 2;
    color: #3a3a5a;
}

Screen { background: #0a0a0f; }
Header { background: #0f0f1a; color: #FCE300; border-bottom: tall #FF003C; }
Footer { background: #0f0f1a; border-top: tall #1e1e35; color: #5a5a7a; }

#status-bar {
    height: 3; background: #0f0f1a; border-bottom: tall #1e1e35;
    padding: 0 2; align: left middle;
}
#launcher-label { color: #00F5FF; width: auto; padding-right: 3; }
#path-label { color: #5a5a7a; width: 1fr; }
#stats-label { color: #FCE300; width: auto; text-align: right; }

#toolbar {
    height: 3; background: #0a0a0f; padding: 0 1; align: left middle;
}
#search-input {
    width: 30; background: #0f0f1a; border: tall #1e1e35; color: #c8c8d8;
}
#search-input:focus { border: tall #00F5FF; }
#filter-label { color: #5a5a7a; padding: 0 1; width: auto; }

.filter-btn {
    min-width: 12; background: #0f0f1a; border: tall #1e1e35; color: #5a5a7a;
}
.filter-btn:hover { background: #1a1a2e; color: #00F5FF; }
.filter-btn.-active {
    background: rgba(252,227,0,0.1); border: tall #FCE300; color: #FCE300;
}

DataTable { background: #0a0a0f; border: none; height: 1fr; }
DataTable > .datatable--header { background: #0f0f1a; color: #5a5a7a; text-style: bold; }
DataTable > .datatable--cursor { background: #1a1a2e; color: #c8c8d8; }
DataTable > .datatable--hover { background: #0f0f18; }

#action-bar {
    height: 4; background: #0f0f1a; border-top: tall #1e1e35;
    padding: 0 1; layout: horizontal; overflow-y: hidden; align: left middle;
}
.action-btn {
    min-width: 16; margin-right: 1;
    background: #0a0a0f; border: tall #1e1e35; color: #5a5a7a;
}
.action-btn:hover { border: tall #FF003C; color: #FF003C; }
.action-btn.-primary { border: tall #FCE300; color: #FCE300; }
.action-btn.-danger { border: tall #FF003C; color: #FF003C; }

#settings-container { padding: 2; }
.setting-row { height: 3; align: left middle; margin-bottom: 1; }
.setting-label { width: 25; color: #c8c8d8; }
.setting-value { color: #00F5FF; width: 1fr; }

ModalScreen { align: center middle; background: rgba(0,0,0,0.8); }
#modal-box {
    background: #0f0f1a; border: tall #FF003C;
    padding: 2 3; width: 60; min-height: 10;
}
#modal-box-wide {
    background: #0f0f1a; border: tall #FF003C;
    padding: 2 3; width: 90; min-height: 14; max-height: 50;
}
#modal-conflicts {
    color: #FF003C;
    margin-top: 1;
    height: auto;
}
#modal-deps {
    color: #FCE300;
    margin-top: 1;
    height: auto;
}
#modal-title { color: #FCE300; text-style: bold; margin-bottom: 1; }
#modal-body, #modal-plan { color: #c8c8d8; margin-bottom: 2; }
#modal-btns { align: right middle; height: 3; }
.field-label { color: #5a5a7a; margin-top: 1; }

Button { margin-left: 1; }
Button.-primary { background: #FF003C; border: tall #FF003C; color: white; }

#log-container { padding: 1 2; background: #0a0a0f; }
.log-line { color: #5a5a7a; height: auto; }
.log-line.-ok { color: #00FF88; }
.log-line.-warn { color: #FCE300; }
.log-line.-err { color: #FF003C; }
"""


# ─── Main App ─────────────────────────────────────────────────────────────────

class MainScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("i", "do_install_zip", "Install"),
        Binding("t", "toggle_selected", "Toggle"),
        Binding("e", "edit_selected", "Edit"),
        Binding("a", "adopt_selected", "Adopt"),
        Binding("u", "uninstall_selected", "Uninstall"),
        Binding("v", "verify_integrity", "Verify"),
        Binding("/", "focus_search", "Search"),
    ]

    current_filter = reactive("All")
    search_query = reactive("")

    def __init__(self):
        super().__init__()
        self.manifest = load_manifest()
        self.launcher, self.game_path, self.detect_msg = detect_game()
        self.mods: list[dict] = []
        self.log_lines: list[tuple[str, str]] = []

        if self.manifest.get("game_path"):
            saved = Path(self.manifest["game_path"])
            if saved.exists():
                self.game_path = saved
                self.launcher = self.manifest.get("launcher", "Manual")

        if self.game_path:
            self.mods = scan_mods(self.game_path, self.manifest)

        self._add_log(self.detect_msg, "ok" if self.game_path else "warn")
        self._add_log(f"SESSION SIGNED // v{APP_VERSION} // {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "ok")

    def _add_log(self, msg: str, level: str = "ok"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append((f"[{ts}] {msg}", level))

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="status-bar"):
            launcher_text = f"● {self.launcher}" if self.launcher else "● Not detected"
            yield Label(launcher_text, id="launcher-label")
            path_text = str(self.game_path) if self.game_path else "No game path — use Settings"
            yield Label(path_text, id="path-label")
            yield Label(self._stats_text(), id="stats-label")

        with TabbedContent(id="tabs"):

            with TabPane("Mods", id="tab-mods"):
                with Vertical(id="main-container"):
                    with Horizontal(id="toolbar"):
                        yield Input(placeholder="Search mods...", id="search-input")
                        yield Label("Filter:", id="filter-label")
                        yield Button("All",      id="f-All",      classes="filter-btn -active")
                        yield Button("Enabled",  id="f-Enabled",  classes="filter-btn")
                        yield Button("Disabled", id="f-Disabled", classes="filter-btn")
                        yield Button("Managed",  id="f-Managed",  classes="filter-btn")

                    yield DataTable(id="mod-table", cursor_type="row")

                    with ScrollableContainer(id="action-bar"):
                        yield Button("Install [I]",     id="btn-install",   classes="action-btn -primary")
                        yield Button("Toggle [T]",      id="btn-toggle",    classes="action-btn")
                        yield Button("Edit [E]",        id="btn-edit",      classes="action-btn")
                        yield Button("Adopt [A]",       id="btn-adopt",     classes="action-btn")
                        yield Button("Uninstall [U]",   id="btn-uninstall", classes="action-btn -danger")
                        yield Button("Clear Cache",     id="btn-clearcache",classes="action-btn")
                        yield Button("Verify [V]",      id="btn-verify",    classes="action-btn")
                        yield Button("Refresh [R]",     id="btn-refresh",   classes="action-btn")
                        yield Button("Set Game Path",   id="btn-setpath",   classes="action-btn")

            with TabPane("Log", id="tab-log"):
                with ScrollableContainer(id="log-container"):
                    yield Static("// Activity log //", classes="log-line")

            with TabPane("Dependencies", id="tab-deps"):
                with Vertical(id="deps-container"):
                    yield Static("// Framework mod status //", classes="log-line")
                    yield DataTable(id="deps-table", cursor_type="none")

            with TabPane("Settings", id="tab-settings"):
                with Vertical(id="settings-container"):
                    with Horizontal(classes="setting-row"):
                        yield Label("Launcher:", classes="setting-label")
                        yield Label(self.launcher or "Not detected", classes="setting-value", id="s-launcher")
                    with Horizontal(classes="setting-row"):
                        yield Label("Game path:", classes="setting-label")
                        yield Label(str(self.game_path) if self.game_path else "Not set",
                                    classes="setting-value", id="s-path")
                    with Horizontal(classes="setting-row"):
                        yield Label("Mod directory:", classes="setting-label")
                        mod_dir = str(get_mod_dir(self.game_path)) if self.game_path else "N/A"
                        yield Label(mod_dir, classes="setting-value", id="s-moddir")
                    yield Button("Reset Manifest", id="btn-reset-manifest", variant="error", classes="action-btn -danger")
                    with Horizontal(classes="setting-row"):
                        yield Label("Manifest file:", classes="setting-label")
                        yield Label(str(MANIFEST_FILE), classes="setting-value")

        yield Footer()

    def on_mount(self):
        self._build_table()
        self._refresh_log_tab()
        self._build_deps_table()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self):
        table = self.query_one("#mod-table", DataTable)
        table.clear(columns=True)
        table.add_columns("", "Name", "Category", "Files", "Size", "Notes")

        for mod in self._filtered_mods():
            status = "✓" if mod["enabled"] else "✗"
            color  = "green" if mod["enabled"] else "red"
            managed_tag = "[cyan]●[/cyan]" if mod["managed"] else " "
            file_count = str(mod["file_count"]) if mod["managed"] else "—"
            table.add_row(
                f"[{color}]{status}[/] {managed_tag}",
                mod["name"],
                mod["category"],
                file_count,
                f"{mod['size_kb']} KB",
                mod["notes"] or "—",
                key=mod["name"],
            )
    
    def _stats_text(self) -> str:
        total   = len(self.mods)
        enabled = sum(1 for m in self.mods if m["enabled"])
        managed = sum(1 for m in self.mods if m["managed"])
        return f"[bold]{enabled}[/] on / [bold]{total}[/] total / [cyan]{managed}[/] managed"

    def _build_deps_table(self):
        if not self.game_path:
            return
        table = self.query_one("#deps-table", DataTable)
        table.clear(columns=True)
        table.add_columns("", "Framework", "GitHub", "Nexus")

        frameworks = check_frameworks(self.game_path)
        for fw in frameworks:
            status = "[green]✓[/green]" if fw["installed"] else "[red]✗[/red]"
            table.add_row(
                status,
                fw["name"],
                fw["url"],
                fw["nexus_url"],
                key=fw["name"],
            )

    def _filtered_mods(self) -> list[dict]:
        mods = self.mods
        q = self.search_query.lower()
        if q:
            mods = [m for m in mods if q in m["name"].lower() or q in m["category"].lower()]
        if self.current_filter == "Enabled":
            mods = [m for m in mods if m["enabled"]]
        elif self.current_filter == "Disabled":
            mods = [m for m in mods if not m["enabled"]]
        elif self.current_filter == "Managed":
            mods = [m for m in mods if m["managed"]]
        return mods

    def _get_selected_mod(self) -> dict | None:
        table = self.query_one("#mod-table", DataTable)
        visible = self._filtered_mods()
        idx = table.cursor_row
        if idx is not None and 0 <= idx < len(visible):
            return visible[idx]
        return None

    # ── Events ────────────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "search-input":
            self.search_query = event.value
            self._build_table()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid and bid.startswith("f-"):
            f = bid[2:]
            self.current_filter = f
            for btn in self.query(".filter-btn"):
                btn.remove_class("-active")
            event.button.add_class("-active")
            self._build_table()
            return

        actions = {
            "btn-toggle":    self.action_toggle_selected,
            "btn-edit":      self.action_edit_selected,
            "btn-adopt":     self.action_adopt_selected,
            "btn-verify":    self.action_verify_integrity,
            "btn-refresh":   self.action_refresh,
            "btn-clearcache": self.action_clear_cache,
            "btn-setpath":   self._do_set_path,
            "btn-reset-manifest": self.action_reset_manifest,
            "btn-install":   self.action_do_install_zip,
            "btn-uninstall": self.action_uninstall_selected,
        }
        if bid in actions:
            actions[bid]()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_refresh(self):
        if self.game_path:
            self.mods = scan_mods(self.game_path, self.manifest)
            self._build_table()
            self.query_one("#stats-label", Label).update(self._stats_text())
            self._add_log("Mod list refreshed.", "ok")
            self._refresh_log_tab()

    def action_clear_cache(self):
        if self.game_path:
            deleted = clear_redscript_cache(self.game_path)
            msg = f"Redscript cache cleared ({', '.join(deleted) if deleted else 'none found'})"
            self._add_log(msg, "ok")
            self._refresh_log_tab()
            self.app.push_screen(MessageModal("Redscript cache has been wiped. It will recompile on next launch.", "Cache Cleared"))
        else:
            self.app.push_screen(MessageModal("No game path set.", "Error"))

    def action_reset_manifest(self):
        async def handle(confirmed):
            if confirmed:
                self.manifest = {"mods": {}, "game_path": str(self.game_path), "launcher": self.launcher}
                save_manifest(self.manifest)
                self._add_log("Manifest reset to match fresh installation.", "warn")
                self.action_refresh()
                self.app.push_screen(MessageModal("All mod tracking data has been cleared.", "Manifest Reset"))
        
        self.app.push_screen(
            ConfirmModal("This will clear all tracked mods from ChooMod. Use this after a fresh game reinstall.", "Reset Manifest"),
            handle
        )

    def action_toggle_selected(self):
        if not self.game_path:
            self.app.push_screen(MessageModal("No game path set.", "Error"))
            return
        mod = self._get_selected_mod()
        if not mod:
            return
        ok, msg = toggle_mod(mod, self.game_path, self.manifest)
        self._add_log(msg, "ok" if ok else "err")
        self.action_refresh()

    def action_edit_selected(self):
        mod = self._get_selected_mod()
        if not mod:
            return

        async def handle(result):
            if result:
                name = mod["name"]
                self.manifest.setdefault("mods", {}).setdefault(name, {}).update(result)
                save_manifest(self.manifest)
                self._add_log(f"Updated metadata for {name}", "ok")
                self.action_refresh()
                self._refresh_log_tab()

        self.app.push_screen(EditModModal(mod), handle)

    def action_adopt_selected(self):
        """Bring an unmanaged .archive mod into the manifest."""
        mod = self._get_selected_mod()
        if not mod:
            return
        if mod["managed"]:
            self.app.push_screen(MessageModal("This mod is already managed.", "Info"))
            return

        mod_name = mod["name"]
        file_path = mod["file"]
        
        self.manifest.setdefault("mods", {})[mod_name] = {
            "installed_files": [file_path],
            "category": "Unmanaged",
            "notes": "Adopted unmanaged mod",
            "added": datetime.now().strftime("%Y-%m-%d"),
            "source_zip": "Adopted",
            "enabled": mod["enabled"],
        }
        save_manifest(self.manifest)
        self._add_log(f"Adopted '{mod_name}' into manifest.", "ok")
        self.action_refresh()

    def action_verify_integrity(self):
        """Check if all managed files exist on disk."""
        if not self.game_path:
            return
            
        # Clear the Redscript cache as part of the verification process
        clear_redscript_cache(self.game_path)
        
        missing = []
        total = 0
        for mod_name, data in self.manifest.get("mods", {}).items():
            for f_path in data.get("installed_files", []):
                total += 1
                p = Path(f_path)
                # Check both active and .disabled versions
                if not p.exists() and not Path(str(p) + ".disabled").exists():
                    missing.append(f"{mod_name}: {p.name}")
        
        if not missing:
            self.app.push_screen(MessageModal(f"Verified {total} files. All systems nominal.", "Integrity Check"))
            self._add_log("Integrity check passed.", "ok")
        else:
            msg = f"Found {len(missing)} missing files!\n\n" + "\n".join(missing[:10])
            if len(missing) > 10:
                msg += f"\n...and {len(missing)-10} more."
            self.app.push_screen(MessageModal(msg, "Integrity Warning"))
            self._add_log(f"Integrity check failed: {len(missing)} files missing.", "err")

    def action_uninstall_selected(self):
        mod = self._get_selected_mod()
        if not mod:
            return
        if not mod["managed"]:
            self.app.push_screen(MessageModal(
                f"'{mod['name']}' was not installed by ChooMod,\n"
                "so there's no file record to uninstall from.\n\n"
                "Delete the .archive file manually from:\n"
                f"{get_mod_dir(self.game_path)}",
                "Not managed by ChooMod"
            ))
            return

        ok, msg = uninstall_mod(mod["name"], self.manifest)
        self._add_log(msg, "ok" if ok else "err")
        self.action_refresh()
        self._refresh_log_tab()

    def action_focus_search(self):
        self.query_one("#search-input", Input).focus()

    # ─────────────────────────────────────────────────────────────────────────
    # ZIP INSTALL FLOW
    # Three steps, each in its own modal:
    #   1. InstallZipModal  — ask for the zip path
    #   2. InstallPreviewModal — show the plan, ask for confirmation
    #   3. Execute install, show result
    # The user sees exactly what will happen before anything is written.
    # ─────────────────────────────────────────────────────────────────────────

    def action_do_install_zip(self):
        if not self.game_path:
            self.app.push_screen(MessageModal("No game path set. Use 'Set Game Path' first.", "Error"))
            return

        async def got_zip_path(zip_str):
            if not zip_str:
                return
            zip_path = Path(zip_str).expanduser()
            if not zip_path.exists():
                self.app.push_screen(MessageModal(f"File not found:\n{zip_path}", "Error"))
                return
            
            # Accept zip files, 7z, or rar
            if not (zipfile.is_zipfile(zip_path) or zip_path.suffix.lower() in [".7z", ".rar"]):
                self.app.push_screen(MessageModal("Unsupported archive type. Use .zip, .7z, or .rar.", "Error"))
                return

            # Step 2: inspect and show preview
            try:
                plan = inspect_zip(zip_path)
                conflicts = check_conflicts(plan, self.manifest, self.game_path)
                missing_deps = check_dependencies(plan, self.game_path, self.manifest)
            except Exception as e:
                self.app.push_screen(MessageModal(f"Error reading zip:\n{e}", "Error"))
                return

            async def got_confirmation(confirmed):
                if not confirmed:
                    self._add_log(f"Install cancelled: {zip_path.name}", "warn")
                    return

                # Step 3: install
                mod_name = zip_path.stem
                ok, msg, files = install_from_plan(
                    zip_path, plan, self.game_path, self.manifest, mod_name
                )
                level = "ok" if ok else "err"
                self._add_log(f"{'Installed' if ok else 'Failed'} {zip_path.name}: {msg}", level)
                self.action_refresh()
                self._refresh_log_tab()
                self.app.push_screen(MessageModal(
                    msg + (f"\n\n{len(files)} files placed." if ok else ""),
                    "Install Complete" if ok else "Install Failed"
                ))

            self.app.push_screen(
                InstallPreviewModal(zip_path.name, plan, conflicts, missing_deps),
                got_confirmation
            )

        self.app.push_screen(InstallZipModal(), got_zip_path)

    def _do_set_path(self):
        async def handle(result):
            if result:
                p = Path(result).expanduser()
                if p.exists():
                    self.game_path = p
                    self.launcher = "Manual"
                    self.manifest["game_path"] = str(p)
                    self.manifest["launcher"] = "Manual"
                    save_manifest(self.manifest)
                    self.mods = scan_mods(p, self.manifest)
                    self._build_table()
                    self.query_one("#path-label",   Label).update(str(p))
                    self.query_one("#stats-label",  Label).update(self._stats_text())
                    self.query_one("#s-path",       Label).update(str(p))
                    self.query_one("#s-launcher",   Label).update("Manual")
                    self.query_one("#s-moddir",     Label).update(str(get_mod_dir(p)))
                    self._add_log(f"Game path set to {p}", "ok")
                else:
                    self.app.push_screen(MessageModal(f"Path does not exist:\n{p}", "Error"))
                self._refresh_log_tab()

        self.app.push_screen(SetPathModal(), handle)

    def _refresh_log_tab(self):
        try:
            container = self.query_one("#log-container", ScrollableContainer)
            container.remove_children()
            for text, level in self.log_lines[-50:]:
                container.mount(Static(text, classes=f"log-line -{level}"))
            container.scroll_end(animate=False)
        except Exception:
            pass

class ChooMod(App):
    TITLE = f"ChooMod v{APP_VERSION} // CP2077 Mod Manager"
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        # Initialize core data for the boot screen
        launcher, game_path, _ = detect_game()
        
        # Load manifest to check for path overrides
        manifest = load_manifest()
        if manifest.get("game_path"):
            saved_path = Path(manifest["game_path"])
            if saved_path.exists():
                game_path = saved_path
                launcher = manifest.get("launcher", "Manual")

        # Install and start the flow
        self.install_screen(MainScreen(), name="main")
        self.app.push_screen(BootScreen(launcher, str(game_path) if game_path else None))

    def action_quit(self) -> None:
        self.exit()

# ─── CLI ──────────────────────────────────────────────────────────────────────

def cli_install(src: str):
    """python3 ChooMod.py install /path/to/mod.zip"""
    manifest = load_manifest()
    _, game_path, msg = detect_game()
    if not game_path and manifest.get("game_path"):
        game_path = Path(manifest["game_path"])
    if not game_path:
        print(f"Error: {msg}")
        return

    zip_path = Path(src)
    if not zip_path.exists():
        print(f"Error: File not found: {zip_path}")
        return
    if not (zipfile.is_zipfile(zip_path) or zip_path.suffix.lower() in [".7z", ".rar"]):
        print(f"Error: Unsupported archive type: {zip_path}. Use .zip, .7z, or .rar")
        return

    print(f"Inspecting {zip_path.name}...")
    plan = inspect_zip(zip_path)
    print(format_plan_summary(plan))

    if not plan["auto"]:
        print("Nothing to install.")
        return

    confirm = input(f"\nInstall {len(plan['auto'])} files? [y/N] ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    mod_name = zip_path.stem
    ok, result, files = install_from_plan(zip_path, plan, game_path, manifest, mod_name)
    print(("✓ " if ok else "✗ ") + result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "install":
        cli_install(sys.argv[2])
    else:
        app = ChooMod()
        app.run()
