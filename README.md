# ChooMod
### A Cyberpunk 2077 mod manager for Linux — built for the terminal

![Version](https://img.shields.io/badge/version-0.4.0--dev-red) ![Platform](https://img.shields.io/badge/platform-Linux-blue) ![Python](https://img.shields.io/badge/python-3.10+-yellow)

---

## What is this?

ChooMod is a terminal-based mod manager for Cyberpunk 2077 on Linux. It runs natively in any terminal emulator (Kitty, Alacritty, whatever you use) and handles mod installation, enable/disable toggling, and file tracking without needing Wine, Proton compatibility layers, or a separate desktop app.

It supports both **GOG via Heroic Launcher** and **Steam**.

---

## Why does this exist?

The honest answer: because modding CP2077 on Linux is more painful than it should be.

Vortex doesn't run natively on Linux. The old Nexus Mod Manager is unsupported. The Nexus Mods App — which did support Linux — was quietly archived in February 2026. Running any of these through Wine works until it doesn't.

ChooMod isn't trying to replace any of those. It's solving one specific problem: give CP2077 players on Linux a native, no-fuss mod manager that actually works. No Wine, no Proton workarounds, no dual booting.

---

## What it can do (v0.3.2)

- **Auto-detects your game install** — scans known Heroic and Steam paths, no manual setup required in most cases
- **Mod installer with pre-install preview** — inspect what a mod archive contains and where every file will go before anything is written to disk. Supports `.zip` and `.7z` formats
- **Transactional Installation** — includes a rollback mechanism. If an install fails, ChooMod automatically cleans up the mess so no "ghost files" are left behind. Supports `.zip`, `.7z`, and `.rar` (via `rarfile`).
- **Conflict detection** — warns you if a mod you're installing overlaps with files already owned by another mod
- **Separate dependencies tab** — shows install status for all required frameworks (CET, Red4Ext, Redscript, etc.) with GitHub and Nexus links
- **Full subfolder preservation** — complex mods with Redscript, TweakXL, CET plugins, and ArchiveXL files all route correctly
- **Manifest-tracked installs** — every file placed by ChooMod is recorded, making clean uninstalls possible
- **Multi-archive grouping** — mods with multiple `.archive` files (like clothing sets) are grouped into a single entry in the mod list.
- **Script/plugin-only mods visible** — mods with no `.archive` file (CET mods, Redscript-only mods) appear in the mod list
- **Enable/disable toggling** — non-destructive, just renames files
- **Mod Adoption** — bring unmanaged mods you installed manually into the ChooMod manifest for easy management.
- **Integrity Verification** — quickly check if any managed mod files are missing from your game directory.
- **Search and filter** — find mods by name or category
- **Activity log** — timestamped record of every action, including signed sessions on boot.

### Supported file types
| Type | Destination |
|------|-------------|
| `.archive` | `archive/pc/mod/` |
| `.xl` | `archive/pc/mod/` |
| `.archive.xl` | `archive/pc/mod/` |
| `.reds` | `r6/scripts/` |
| `.toml` (config) | `r6/config/` |
| `.xml` (input) | `r6/input/` |
| `.ini` (engine config) | `engine/config/` |
| TweakXL `.yaml` | `r6/tweaks/` |
| CET Lua plugins | `bin/x64/plugins/cyber_engine_tweaks/` |
| Red4Ext `.dll` | `bin/x64/` |

---

## What it can't do yet

- Dependency resolution (it won't stop you installing a mod that needs Archive XL if you don't have it)
- Load order management
- Optional/variant file selection during install
- Nexus Mods API integration

These are all planned. This is a passion project in active development, not a finished product.

---

## Installation

**Requirements:** Python 3.10+, pip

```bash
pip install textual --break-system-packages
```

For `.7z` mod support (optional but recommended):
```bash
pip install py7zr --break-system-packages
```

Download `choomod.py` and run it:

```bash
python3 choomod.py
```

That's it. No build step, no other dependencies required.

---

## Usage

### TUI (recommended)
```bash
python3 choomod.py
```

Launch the interactive terminal UI. Use keyboard shortcuts or mouse.

| Key | Action |
|-----|--------|
| `I` / Install Mod button | Install a mod from a .zip or .7z file |
| `T` | Toggle selected mod on/off |
| `E` | Edit mod metadata (category, notes) |
| `A` | Adopt unmanaged mod into manifest |
| `U` | Uninstall a managed mod |
| `V` | Verify integrity of all managed files |
| `R` | Refresh mod list |
| `/` | Focus search |
| `Q` | Quit |

### CLI install (alternative)
```bash
python3 choomod.py install /path/to/mod.zip
```

Inspects the archive, shows you the plan, asks for confirmation, installs.

---

## Game path detection

ChooMod scans these locations automatically:

**Heroic / GOG:**
- `~/Games/Heroic/Cyberpunk 2077`
- `~/GOG Games/Cyberpunk 2077`
- `~/.local/share/heroic/GOG Games/Cyberpunk 2077`
- Heroic Flatpak path

**Steam:**
- `~/.steam/steam/steamapps/common/Cyberpunk 2077`
- Steam Flatpak path

If your install is somewhere else, use the **Set Game Path** button in the app.

---

## A note on dependencies

CP2077 mods often require framework mods to function:

- **[Redscript](https://github.com/jac3km4/redscript)** — required for `.reds` files
- **[Archive XL](https://github.com/psiberx/cp2077-archive-xl)** — required for `.archive.xl` files
- **[TweakXL](https://github.com/psiberx/cp2077-tweak-xl)** — required for `.yaml` tweaks
- **[Cyber Engine Tweaks](https://github.com/maximegmd/CyberEngineTweaks)** — required for CET Lua mods
- **[Red4Ext](https://github.com/wopss/RED4ext)** — required for `.dll` extension mods
- **[Codeware](https://github.com/psiberx/cp2077-codeware)** — required by some advanced mods

ChooMod will install these if you point it at their archives, but it won't warn you if a mod needs one and you don't have it — yet.

---

## Project background

This started as a personal frustration. I'm **film** — not a programmer, just a Linux user who wanted to mod Cyberpunk 2077 without dual booting or fighting with Wine.

The code was written with the help of **Claude (Anthropic)**, which handled the implementation. The idea, the design decisions, the feature priorities, and the testing are mine. I'm learning Python through building this, which means development is honest about what it is: a passion project by someone figuring it out as they go.

ChooMod is strictly focused on Cyberpunk 2077 for now. Other games have their own mod managers. If this project takes off and there's demand, other games could follow — but that's not the current goal.

If you're a developer and you want to contribute, that's genuinely welcome — especially around dependency resolution and load order management, which are the next big gaps.

---

## Roadmap

**Priority 1 — Core reliability**
- [x] Partial install rollback — clean up placed files if install fails mid-way
- [x] Adopt unmanaged mods into ChooMod's manifest
- [x] Group multi-archive mods as a single mod list entry
- [x] Support for `.rar` and `.xl` file types

**Priority 2 — Install experience**
- [ ] Optional/variant file selection during install
- [ ] Dependency tagging and warnings
- [ ] First-run setup checker — verify launch options are correctly set for Steam/Heroic
- [ ] Batch install + pacman-style progress output

**Priority 3 — Power features**
- [ ] Load order management
- [ ] Profiles (multiple mod loadouts)
- [ ] Nexus Mods API integration for version checking and dependency data
- [ ] Investigate disabled mods still appearing in in-game Mod Settings menus

**Future Exploration (Backlog)**
- [ ] **Launch Option Helper**: Generate/Apply the required `WINEDLLOVERRIDES` strings for Steam/Heroic.
- [ ] **Integrated Log Viewer**: View `redscript.log` and `CET` logs directly in the TUI for easier troubleshooting.
- [ ] **Symlink Mode**: Option to install mods via symbolic links to keep the game directory pristine.
- [ ] **Framework Update Checker**: Check GitHub API for the latest versions of CET, Red4Ext, etc.
- [ ] **Export/Import Modlist**: Share your manifest or backup your setup as a simple JSON/text file.


**Future — if there's demand**
- [ ] Support for additional games
- [ ] Windows support

---

## Completed features

| Feature | Version |
|---------|---------|
| Basic mod list display | v0.1.0 |
| Support for `.rar` and `.xl` file types | v0.4.0 |
| Enable/disable toggling | v0.1.0 |
| GOG/Heroic and Steam auto-detection | v0.1.0 |
| Zip installer with pre-install preview | v0.2.0 |
| Full subfolder preservation for complex mods | v0.2.0 |
| Manifest-tracked installs with clean uninstall | v0.2.0 |
| Path-based manifest matching for multi-archive mods | v0.3.0 |
| Manifest consolidation at `~/.config/choomod/` | v0.3.0 |
| Dependencies tab with framework status indicators | v0.3.1 |
| GitHub and Nexus links for each framework | v0.3.1 |
| Conflict detection — warns before overwriting files | v0.3.2 |
| `.7z` archive support via `py7zr` | v0.3.2 |
| Script/plugin-only mods visible in mod list | v0.3.2 |
| `red4ext/plugins` routing fix | v0.3.2 |
| `engine/config` and `r6/cache` routing support | v0.3.2 |

---

## Changelog

**v0.4.0 (Development)**
- Added support for `.rar` archives via `rarfile` library.
- Expanded `FILE_ROUTES` to support `.xl` resource files (ArchiveXL).
- Updated `ArchiveHandler` to gracefully handle library requirements for specific formats.

**v0.3.2**
- Refactored UI into BootScreen and MainScreen for better flow and state management.
- Implemented transactional installation with automatic rollback if extraction fails.
- Added unified ArchiveHandler to support .zip and .7z formats interchangeably.
- Added "Adopt" feature to take control of unmanaged mods on disk.
- Added "Verify Integrity" to check for missing managed files.
- Conflict detection wired into install preview — warns if files are already owned by another mod
- `.7z` archive support added via `py7zr`
- Routing logic refactored into shared `_route_entry()` helper
- `red4ext/plugins` rule added — script mods route correctly instead of landing in `r6/scripts`
- `engine/config` and `r6/cache` added to FILE_ROUTES
- Script/plugin-only mods now appear in mod list via manifest lookup
- Duplicate entry bug fixed via path-based manifest key matching
- UI: "Install Mod" replaces "Install zip" throughout

**v0.3.1**
- Dependencies tab showing install status for CET, Red4Ext, Redscript, ArchiveXL, TweakXL, Codeware
- GitHub and Nexus links for each framework

**v0.3.0**
- Path-based manifest matching — multi-archive mods correctly identified and uninstalled
- Manifest consolidation — single config at `~/.config/choomod/`
- Manifest key uses zip filename consistently

**v0.2.0**
- Zip installer with pre-install preview
- Full subfolder preservation for complex mods
- Manifest-tracked installs with clean uninstall
- Verified working: Virtual Atelier (47 files), Limited HUD, Native Settings UI

**v0.1.0**
- Basic mod list display
- Enable/disable toggling
- GOG/Heroic and Steam auto-detection

---

*Choom is Night City slang for friend. Felt right.*g