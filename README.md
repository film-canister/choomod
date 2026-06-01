# ChooMod
### A Cyberpunk 2077 mod manager for Linux — built for the terminal

![Version](https://img.shields.io/badge/version-0.3.0-red) ![Platform](https://img.shields.io/badge/platform-Linux-blue) ![Python](https://img.shields.io/badge/python-3.10+-yellow)

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

## What it can do (v0.3.1)

- **Auto-detects your game install** — scans known Heroic and Steam paths, no manual setup required in most cases
- **Zip installer with pre-install preview** — inspect what a mod zip contains and where every file will go before anything is written to disk
- **Separate tabs for dependencies** - Good to know what's missing if you're installing mods for the first time!
- **Full subfolder preservation** — complex mods with Redscript, TweakXL, CET plugins, and ArchiveXL files all route correctly
- **Manifest-tracked installs** — every file placed by ChooMod is recorded, making clean uninstalls possible
- **Path-based manifest matching** — mods with multiple archive files are correctly identified and uninstalled cleanly
- **Enable/disable toggling** — non-destructive, just renames files
- **Search and filter** — find mods by name or category
- **Activity log** — timestamped record of everything ChooMod has done

### Supported file types
| Type | Destination |
|------|-------------|
| `.archive` | `archive/pc/mod/` |
| `.archive.xl` | `archive/pc/mod/` |
| `.reds` | `r6/scripts/` |
| `.toml` (config) | `r6/config/` |
| `.xml` (input) | `r6/input/` |
| TweakXL `.yaml` | `r6/tweaks/` |
| CET Lua plugins | `bin/x64/plugins/cyber_engine_tweaks/` |
| Red4Ext `.dll` | `bin/x64/` |

---

## What it can't do yet

- Dependency resolution (it won't stop you installing a mod that needs Archive XL if you don't have it)
- Conflict detection between mods
- Load order management
- Optional/variant file selection during install
- Grouping multi-archive mods as a single entry in the mod list
- Nexus Mods API integration

These are all planned. This is a passion project in active development, not a finished product.

---

## Installation

**Requirements:** Python 3.10+, pip

```bash
pip install textual --break-system-packages
```

Download `choomod.py` and run it:

```bash
python3 choomod.py
```

That's it. No build step, no dependencies beyond Textual.

---

## Usage

### TUI (recommended)
```bash
python3 choomod.py
```

Launch the interactive terminal UI. Use keyboard shortcuts or mouse.

| Key | Action |
|-----|--------|
| `I` / Install zip button | Install a mod from a .zip file |
| `T` | Toggle selected mod on/off |
| `E` | Edit mod metadata (category, notes) |
| `U` | Uninstall a managed mod |
| `R` | Refresh mod list |
| `/` | Focus search |
| `Q` | Quit |

### CLI install (alternative)
```bash
python3 choomod.py install /path/to/mod.zip
```

Inspects the zip, shows you the plan, asks for confirmation, installs.

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

ChooMod will install these if you point it at their zips, but it won't warn you if a mod needs one and you don't have it — yet.

---

## Project background

This started as a personal frustration. I'm **film** — not a programmer, just a Linux user who wanted to mod Cyberpunk 2077 without dual booting or fighting with Wine.

The code was written with the help of **Claude (Anthropic)**, which handled the implementation. The idea, the design decisions, the feature priorities, and the testing are mine. I'm learning Python through building this, which means development is honest about what it is: a passion project by someone figuring it out as they go.

ChooMod is strictly focused on Cyberpunk 2077 for now. Other games have their own mod managers. If this project takes off and there's demand, other games could follow — but that's not the current goal.

If you're a developer and you want to contribute, that's genuinely welcome — especially around dependency resolution and conflict detection, which are the next big gaps.

---

## Roadmap

**Priority 1 — Core reliability**
- [ ] Conflict detection (two mods writing the same file) — in development
- [ ] Partial install rollback (clean up files if install fails mid-way) — in development
- [ ] Fix `.reds` and `.dll` routing when mod zips do not use the expected folder layout
- [ ] Show managed script/tweak/Lua/CET-only mods in the mod list
- [ ] Group multi-archive mods as a single mod list entry
- [ ] Adopt unmanaged mods into ChooMod's manifest

**Priority 2 — Install experience**
- [ ] Optional/variant file selection during install
- [ ] Dependency tagging and warnings
- [ ] First-run setup checker — verify launch options are correctly set for Steam/Heroic
- [ ] Pacman-style install progress output
- [ ] Support `.7z` mod archives, either through optional `py7zr` support or system `7z`
- [x] Separate tab for framework/dependency mods (CET, Redscript, Red4Ext etc)

**Priority 3 — Power features**
- [ ] Load order management
- [ ] Profiles (multiple mod loadouts)
- [ ] Investigate disabled mods still appearing in in-game Mod Settings menus
- [ ] Nexus Mods API integration for version checking and dependency data

**Future — If there's demand**
- [ ] Support for additional games
- [ ] Windows support

---

## Changelog

**v0.3.1**
- added tab menu showing install status for required mod dependencies (ex: CET, Red4Ext, etc.)
- github and nexusmods links for each framework in order to maintain compatibility

**v0.3.0**
- Path-based manifest matching — multi-archive mods now correctly identified and uninstalled
- Manifest consolidation — single config location at `~/.config/choomod/`
- Bug fix: manifest key now uses zip filename consistently

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

*Choom is Night City slang for friend. Felt right.*
