#!/usr/bin/env python3
"""
ChooMod - Cyberpunk 2077 Mod Manager for Linux
Supports: GOG via Heroic, Steam via Proton
"""

import json
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label,
    Static, Switch, TabbedContent, TabPane
)

# ─── Constants ────────────────────────────────────────────────────────────────

APP_VERSION = "0.2.0"
MANIFEST_FILE = Path.home() / ".config" / "ChooMod" / "manifest.json"

# Known CP2077 install locations to scan
SEARCH_PATHS = {
    "heroic_default":   Path.home() / "Games" / "Heroic" / "Cyberpunk 2077",
    "heroic_alt":       Path.home() / "GOG Games" / "Cyberpunk 2077",
    "heroic_legacy":    Path.home() / ".local" / "share" / "heroic" / "GOG Games" / "Cyberpunk 2077",
    "steam_native":     Path.home() / ".steam" / "steam" / "steamapps" / "common" / "Cyberpunk 2077",
    "steam_flatpak":    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "common" / "Cyberpunk 2077",
    "heroic_flatpak":   Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "GOG Games" / "Cyberpunk 2077",
}

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
    # (rule_type, pattern,                       destination)

    # ArchiveXL extension files — must come before generic .archive rule
    ("suffix", ".archive.xl",                    "archive/pc/mod"),

    # Standard mod archives
    ("suffix", ".archive",                       "archive/pc/mod"),

    # Redscript source files
    ("path",   "r6/scripts",                     "r6/scripts"),

    # TweakXL yaml patches
    ("path",   "r6/tweaks",                      "r6/tweaks"),

    # User config / hints (toml, ini etc)
    ("path",   "r6/config",                      "r6/config"),

    # Input bindings
    ("path",   "r6/input",                       "r6/input"),

    # Cyber Engine Tweaks mods (lua scripts)
    ("path",   "bin/x64/plugins/cyber_engine_tweaks", "bin/x64/plugins/cyber_engine_tweaks"),

    # Red4Ext DLLs and plugins
    ("path",   "bin/x64",                        "bin/x64"),
]

# Extensions we recognise but deliberately skip (readmes, screenshots etc)
SKIP_EXTENSIONS = {".txt", ".md", ".png", ".jpg", ".jpeg", ".pdf", ".url", ".gif"}

# ─── Detection ────────────────────────────────────────────────────────────────

def detect_game() -> tuple[str | None, Path | None, str]:
    for key, path in SEARCH_PATHS.items():
        if path.exists() and (path / "bin").exists():
            launcher = "GOG (Heroic)" if "heroic" in key or "gog" in key.lower() else "Steam"
            return launcher, path, f"Found via {launcher} at {path}"
    return None, None, "Game not found. Set path manually in Settings."


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
        }
    """
    plan = {"auto": [], "ambiguous": [], "unknown": [], "skip": []}

    # Keywords that suggest a file is optional or a variant.
    # If a file lives inside a folder with one of these names,
    # we flag it as ambiguous instead of auto-installing.
    ambiguous_keywords = {"optional", "variant", "alternative", "alt", "choose", "option"}

    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in zf.namelist():

            # zipfile includes folder entries ending in /  — skip those,
            # we only care about actual files
            if entry.endswith("/"):
                continue

            p = Path(entry)

            # ── Skip readmes, images, etc ──────────────────────────────────
            # p.suffix gives the file extension e.g. ".txt"
            # We check the full name too for files like "mod.archive.xl"
            # which have a compound extension
            if p.suffix.lower() in SKIP_EXTENSIONS:
                plan["skip"].append(entry)
                continue

            # ── Route the file ─────────────────────────────────────────────
            # Walk through FILE_ROUTES in order.
            # For "suffix" rules: check if the filename ends with the pattern.
            #   We use str(p).endswith() not p.suffix because .archive.xl
            #   has a compound extension that p.suffix alone misses.
            # For "path" rules: check if the pattern appears anywhere in the
            #   full zip entry path. This handles cases where the mod author
            #   wrapped everything in a top-level folder.
            destination = None
            for rule_type, pattern, dest in FILE_ROUTES:
                if rule_type == "suffix" and str(p).endswith(pattern):
                    destination = dest
                    break
                elif rule_type == "path" and pattern in entry:
                    destination = dest
                    break

            # ── Check for ambiguity ────────────────────────────────────────
            # p.parts splits a path into its components.
            # e.g. Path("Optional/Main/mod.archive").parts
            #   -> ('Optional', 'Main', 'mod.archive')
            # We lowercase each part and check against our keyword set.
            parts_lower = {part.lower() for part in p.parts}
            is_ambiguous = bool(parts_lower & ambiguous_keywords)
            # The & operator on sets = intersection.
            # If any part matches any keyword, is_ambiguous = True.

            # ── Sort into buckets ──────────────────────────────────────────
            if destination and not is_ambiguous:
                plan["auto"].append((entry, destination))
            elif destination and is_ambiguous:
                plan["ambiguous"].append((entry, destination))
            else:
                plan["unknown"].append(entry)

    return plan


def format_plan_summary(plan: dict) -> str:
    """
    Turn an install plan into a human-readable summary string.
    Used to show the user what will happen before we do it.
    """
    lines = []

    if plan["auto"]:
        lines.append(f"[green]✓ Auto-install ({len(plan['auto'])} files):[/green]")
        for entry, dest in plan["auto"]:
            # Just show filename and destination, not the full zip path
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
    errors = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for zip_entry, destination in plan["auto"]:

            p = Path(zip_entry)

            # ── Preserve subfolder structure ───────────────────────────────
            # Find where the route root appears in the zip path,
            # then keep everything after it.
            #
            # Example:
            #   zip_entry   = "r6/scripts/virtual-atelier-full/core/Classes.reds"
            #   destination = "r6/scripts"
            #   dest_parts  = ["r6", "scripts"]
            #   We find "scripts" in p.parts, take everything after it.
            #   Result: game_path / "r6/scripts" / "virtual-atelier-full/core/Classes.reds"
            #
            # For flat files like archive/pc/mod/mod.archive,
            # there's no subfolder so we just use the filename.

            dest_root_parts = Path(destination).parts
            p_parts = p.parts

            # Find the index where the destination root ends in the zip path
            # We match on the last component of the destination root
            last_dest_part = dest_root_parts[-1]
            try:
                idx = list(p_parts).index(last_dest_part)
                # Everything after the match = the relative subpath
                relative_subpath = Path(*p_parts[idx + 1:]) if idx + 1 < len(p_parts) else p.name
            except ValueError:
                # Pattern not found in parts — just use filename
                relative_subpath = p.name

            dest_path = game_path / destination / relative_subpath

            # ── Create parent directories if needed ───────────────────────
            # parents=True  = create the whole chain (like mkdir -p)
            # exist_ok=True = don't error if folder already exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # ── Extract and write the file ─────────────────────────────────
            try:
                with zf.open(zip_entry) as src, open(dest_path, "wb") as dst:
                    # copyfileobj reads in chunks — memory-safe for large files
                    shutil.copyfileobj(src, dst)
                installed_files.append(str(dest_path))
            except Exception as e:
                errors.append(f"{p.name}: {e}")

    if not installed_files:
        return False, "No files were installed.", []

    # ── Record in manifest ─────────────────────────────────────────────────
    # This is what makes uninstall possible later.
    # We store every file path we wrote, plus metadata.
    manifest.setdefault("mods", {})[mod_name] = {
        "installed_files": installed_files,
        "category": "Uncategorised",
        "notes": "",
        "added": datetime.now().strftime("%Y-%m-%d"),
        "source_zip": str(zip_path),
        "enabled": True,
    }
    save_manifest(manifest)

    msg = f"Installed {len(installed_files)} files"
    if errors:
        msg += f" ({len(errors)} errors: {'; '.join(errors)})"
    return True, msg, installed_files


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
        try:
            if p.exists():
                p.unlink()      # unlink() deletes a file
                removed += 1
            # Clean up empty parent directories
            # We try to remove parents up the tree, stopping when non-empty
            try:
                p.parent.rmdir()    # only removes if empty
            except OSError:
                pass                # not empty — that's fine, leave it
        except Exception as e:
            errors.append(str(e))

    del manifest["mods"][mod_name]
    save_manifest(manifest)

    if errors:
        return False, f"Removed {removed} files with {len(errors)} errors"
    return True, f"Uninstalled '{mod_name}' — {removed} files removed"


# ─── Mod scanning (for mods installed outside ChooMod) ───────────────────────

def scan_mods(game_path: Path, manifest: dict) -> list[dict]:
    mod_dir = get_mod_dir(game_path)
    if not mod_dir.exists():
        return []

    mods = []
    seen = set()
    managed = manifest.get("mods", {})

    for f in sorted(mod_dir.glob("*.archive")):
        name = f.stem
        seen.add(name)
        meta = managed.get(name, {})
        mods.append({
            "name": name,
            "file": str(f),
            "enabled": True,
            "size_kb": round(f.stat().st_size / 1024),
            "category": meta.get("category", "Uncategorised"),
            "notes": meta.get("notes", ""),
            "added": meta.get("added", "Unknown"),
            "managed": name in managed,
            "file_count": len(meta.get("installed_files", [])),
        })

    for f in sorted(mod_dir.glob("*.archive.disabled")):
        name = f.name.replace(".archive.disabled", "")
        if name in seen:
            continue
        meta = managed.get(name, {})
        mods.append({
            "name": name,
            "file": str(f),
            "enabled": False,
            "size_kb": round(f.stat().st_size / 1024),
            "category": meta.get("category", "Uncategorised"),
            "notes": meta.get("notes", ""),
            "added": meta.get("added", "Unknown"),
            "managed": name in managed,
            "file_count": len(meta.get("installed_files", [])),
        })

    return mods


def toggle_mod(mod: dict, game_path: Path) -> tuple[bool, str]:
    f = Path(mod["file"])
    try:
        if mod["enabled"]:
            new_path = Path(str(f) + ".disabled")
            f.rename(new_path)
            return True, f"Disabled {mod['name']}"
        else:
            new_path = Path(str(f).replace(".archive.disabled", ".archive"))
            f.rename(new_path)
            return True, f"Enabled {mod['name']}"
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


class InstallPreviewModal(ModalScreen):
    """Show the install plan and ask for confirmation before writing any files."""
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, zip_name: str, plan: dict):
        super().__init__()
        self._zip_name = zip_name
        self._plan = plan

    def compose(self) -> ComposeResult:
        with Container(id="modal-box-wide"):
            yield Label(f"Install: {self._zip_name}", id="modal-title")
            yield Static(format_plan_summary(self._plan), id="modal-body")
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
            yield Label("Enter the full path to the mod .zip file:", id="modal-body")
            yield Input(placeholder="/home/user/Downloads/mod.zip", id="zip-input")
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


# ─── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
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
    height: 3; background: #0f0f1a; border-top: tall #1e1e35;
    padding: 0 1; align: left middle;
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
    padding: 2 3; width: 90; min-height: 14; max-height: 40;
}
#modal-title { color: #FCE300; text-style: bold; margin-bottom: 1; }
#modal-body { color: #c8c8d8; margin-bottom: 2; }
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

class ChooMod(App):
    TITLE = f"ChooMod v{APP_VERSION} // CP2077 Mod Manager"
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "toggle_selected", "Toggle"),
        Binding("e", "edit_selected", "Edit"),
        Binding("u", "uninstall_selected", "Uninstall"),
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

                    with Horizontal(id="action-bar"):
                        yield Button("Install zip [I]", id="btn-install",   classes="action-btn -primary")
                        yield Button("Toggle [T]",      id="btn-toggle",    classes="action-btn")
                        yield Button("Edit [E]",        id="btn-edit",      classes="action-btn")
                        yield Button("Uninstall [U]",   id="btn-uninstall", classes="action-btn -danger")
                        yield Button("Refresh [R]",     id="btn-refresh",   classes="action-btn")
                        yield Button("Set Game Path",   id="btn-setpath",   classes="action-btn")

            with TabPane("Log", id="tab-log"):
                with ScrollableContainer(id="log-container"):
                    yield Static("// Activity log //", classes="log-line")

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
                    with Horizontal(classes="setting-row"):
                        yield Label("Manifest file:", classes="setting-label")
                        yield Label(str(MANIFEST_FILE), classes="setting-value")

        yield Footer()

    def on_mount(self):
        self._build_table()
        self._refresh_log_tab()

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

    def _stats_text(self) -> str:
        total   = len(self.mods)
        enabled = sum(1 for m in self.mods if m["enabled"])
        managed = sum(1 for m in self.mods if m["managed"])
        return f"[bold]{enabled}[/] on / [bold]{total}[/] total / [cyan]{managed}[/] managed"

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
            "btn-refresh":   self.action_refresh,
            "btn-setpath":   self._do_set_path,
            "btn-install":   self._do_install_zip,
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

    def action_toggle_selected(self):
        if not self.game_path:
            self.push_screen(MessageModal("No game path set.", "Error"))
            return
        mod = self._get_selected_mod()
        if not mod:
            return
        ok, msg = toggle_mod(mod, self.game_path)
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

        self.push_screen(EditModModal(mod), handle)

    def action_uninstall_selected(self):
        mod = self._get_selected_mod()
        if not mod:
            return
        if not mod["managed"]:
            self.push_screen(MessageModal(
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

    def _do_install_zip(self):
        if not self.game_path:
            self.push_screen(MessageModal("No game path set. Use 'Set Game Path' first.", "Error"))
            return

        async def got_zip_path(zip_str):
            if not zip_str:
                return
            zip_path = Path(zip_str)
            if not zip_path.exists():
                self.push_screen(MessageModal(f"File not found:\n{zip_path}", "Error"))
                return
            if not zipfile.is_zipfile(zip_path):
                self.push_screen(MessageModal("That doesn't look like a valid zip file.", "Error"))
                return

            # Step 2: inspect and show preview
            try:
                plan = inspect_zip(zip_path)
            except Exception as e:
                self.push_screen(MessageModal(f"Error reading zip:\n{e}", "Error"))
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
                self.push_screen(MessageModal(
                    msg + (f"\n\n{len(files)} files placed." if ok else ""),
                    "Install Complete" if ok else "Install Failed"
                ))

            self.push_screen(InstallPreviewModal(zip_path.name, plan), got_confirmation)

        self.push_screen(InstallZipModal(), got_zip_path)

    def _do_set_path(self):
        async def handle(result):
            if result:
                p = Path(result)
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
                    self.push_screen(MessageModal(f"Path does not exist:\n{p}", "Error"))
                self._refresh_log_tab()

        self.push_screen(SetPathModal(), handle)

    def _refresh_log_tab(self):
        try:
            container = self.query_one("#log-container", ScrollableContainer)
            container.remove_children()
            for text, level in self.log_lines[-50:]:
                container.mount(Static(text, classes=f"log-line -{level}"))
            container.scroll_end(animate=False)
        except Exception:
            pass


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
    if not zipfile.is_zipfile(zip_path):
        print(f"Error: Not a valid zip file: {zip_path}")
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
