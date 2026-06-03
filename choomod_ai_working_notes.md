# ChooMod AI Working Notes

## Current working file
Use `choomod_dev.py` for experiments.
Do not edit `choomod.py` until changes are tested and verified in-game.
Active branch: `dev` (merge to `main` on version release only)

Run dev version with:
```bash
python3 choomod_dev.py
```

---

## In development
- Conflict detection — `check_conflicts()` written, not yet wired into install flow
- Partial install rollback

---

## To-do (Priority order)

### High priority
- Wire `check_conflicts()` into `_do_install_zip()` — runs after inspect, before preview modal
- Partial install rollback (clean up placed files if install fails mid-way)
- 7zip support — needs `py7zr` library, ~10 lines of code (AdaptiveSliders couldn't install)

### Medium priority
- Parent/child mod grouping (visual indent for add-ons/patches under their parent mod)
- First-run setup checker (verify launch options set correctly for Steam/Heroic)

### Not urgent
- Toggle behaviour for script-only mods (disabled mods still appear in in-game Mod Settings menu)
- CP2077 HUD colour scheme (health bar colours, flatline text, background — purely cosmetic)

---

## Known issues / investigation notes
- Disabled mods may still appear in the in-game Mod Settings menu after toggling off.
  Current toggle renames `.archive` files correctly but config/script files stay active.
  Investigate: settings files staying active, framework caching, or script files not being toggled.
  Not urgent — basic toggle works fine for archive-based mods.

---

## Completed

### v0.3.2 (in progress)
- `check_conflicts()` function added near `inspect_zip()` and `install_from_plan()`
- Red4Ext plugin routing fixed (`red4ext/plugins` rule added to FILE_ROUTES)
- Added `engine/config` and `r6/cache` to FILE_ROUTES
- Script/plugin-only mods now visible in mod list (manifest-only entries surfaced)
- Duplicate entry bug fixed via manifest key matching in `already_listed`

### v0.3.1
- Dependencies tab added — shows install status for CET, Red4Ext, Redscript, ArchiveXL, TweakXL, Codeware
- GitHub and Nexus links for each framework
- Version badge and changelog updated in README

### v0.3.0
- Path-based manifest matching — multi-archive mods correctly identified and uninstalled
- Manifest consolidation — single config at `~/.config/choomod/`
- Manifest key uses zip filename consistently

### v0.2.0
- Zip installer with pre-install preview
- Full subfolder preservation for complex mods
- Manifest-tracked installs with clean uninstall
- Verified: Virtual Atelier (47 files), Limited HUD, Native Settings UI

### v0.1.0
- Basic mod list display
- Enable/disable toggling
- GOG/Heroic and Steam auto-detection

---

## Session log
*Sign and date each session. Helps track what was done and who drove it.*

| Date | Work done | Driven by |
|------|-----------|-----------|
| 2026-05-29 | Initial build — TUI, detection, toggle, v0.1.0 | film + Claude |
| 2026-05-29 | Zip installer, manifest tracking, v0.2.0 | film + Claude |
| 2026-05-30 | Manifest consolidation, path matching, v0.3.0 | film + Claude |
| 2026-05-31 | Dependencies tab, FILE_ROUTES additions, v0.3.1 | film + Claude |
| 2026-06-01 | Script mod visibility, conflict detection groundwork | film + Claude |

---

## Key functions reference

| Function | Purpose |
|----------|---------|
| `detect_game()` | Scans known paths to find CP2077 |
| `inspect_zip()` | Reads zip, returns install plan — no writing |
| `check_conflicts()` | Checks plan against manifest for file conflicts |
| `install_from_plan()` | Executes install, writes manifest |
| `uninstall_mod()` | Reads manifest, deletes tracked files |
| `scan_mods()` | Scans game folder + manifest, builds mod list |
| `find_manifest_entry()` | Looks up a file path in manifest — returns mod name |
| `check_frameworks()` | Checks if framework mods are installed |

---

## Notes for Codex handoff
```
Working on ChooMod — CP2077 mod manager for Linux, Python/Textual.
Active file: choomod_dev.py, branch: dev

Recently added: check_conflicts() near inspect_zip() and install_from_plan().
Takes (plan, manifest, game_path), returns list of conflict dicts.
Reuses find_manifest_entry() for path lookup.

Next: wire check_conflicts() into _do_install_zip().
Run AFTER inspect_zip(), BEFORE InstallPreviewModal.
If conflicts found, surface them in the preview modal.
User can proceed anyway or cancel — do not block install.
```
