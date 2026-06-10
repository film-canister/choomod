# ChooMod Bug Tracker
*Last updated: 2026-06-10*

---

## Critical (breaks functionality)

### BUG-001: Codeware installation corrupts game state
**Severity:** Critical  
**Status:** Open  
**Reported:** 2026-06-10  

**Symptoms:**
- Game stops working after Codeware is installed through ChooMod
- Redscript compilation errors appear on launch
- Issue is reproducible across fresh installs

**Suspected cause:**
Codeware recently changed its structure — it now has both a script component (`r6/scripts/Codeware`) and a binary component (`red4ext/plugins/Codeware`). ChooMod's FILE_ROUTES may be routing Codeware files incorrectly, placing them in the wrong location or missing files entirely.

The `.xl` file type added recently may also be involved — Codeware ships `.xl` resource files that need to land in `archive/pc/mod/` but may be getting misrouted.

**Investigation needed:**
1. Inspect the Codeware zip manually and log exactly what files are inside
2. Run inspect_zip on it and check what the plan shows
3. Compare planned destinations against what the Codeware wiki says is correct
4. Check if the issue is routing or if files are simply missing after install

**Workaround:** Install Codeware manually by copying files directly into game folders. Do not use ChooMod for Codeware until fixed.

---

### BUG-002: Dependencies not togglable (except ArchiveXL)
**Severity:** Critical  
**Status:** Open  
**Reported:** 2026-06-10  

**Symptoms:**
- Framework mods (Red4Ext, CET, Redscript, TweakXL, Codeware) cannot be toggled
- ArchiveXL toggles correctly because it was uninstalled and reinstalled through ChooMod, giving it a proper manifest entry
- Other frameworks were installed manually or through an earlier ChooMod version without full manifest tracking

**Root cause:**
The full-file toggle fix requires `manifest_key` to be present in the mod dict. Mods without a manifest entry fall back to archive-only toggling. Framework mods that live purely in `bin/x64/`, `red4ext/`, or `r6/scripts/` with no `.archive` file have no toggle path at all in the fallback.

**Fix needed:**
The toggle fallback for unmanaged mods needs to handle non-archive files. OR — better long term — prompt the user to adopt the mod into the manifest first, then toggle will work.

---

## High (significant UX problem)

### BUG-003: Red4Ext false positive detection when ArchiveXL is installed
**Severity:** High  
**Status:** Open  
**Reported:** 2026-06-10  

**Symptoms:**
- Dependencies tab shows Red4Ext as installed when only ArchiveXL is present
- ArchiveXL installs into `red4ext/plugins/ArchiveXL/` which creates the `red4ext/` folder
- Red4Ext detection logic sees the folder and reports a false positive

**Root cause:**
The `exists_ci` check for Red4Ext is matching on the `red4ext/` folder rather than the actual `RED4ext.dll` binary. Any mod that installs into `red4ext/plugins/` will trigger this false positive.

**Fix:**
Red4Ext detection must check specifically for `bin/x64/RED4ext.dll` — the sentinel binary — not just the presence of the `red4ext/` folder.

---

### BUG-004: Dependency detection requires ChooMod restart
**Severity:** High  
**Status:** Open  
**Reported:** 2026-06-10  

**Symptoms:**
- Installing a framework mod through ChooMod does not update the Dependencies tab
- Must close and reopen ChooMod to see updated detection status

**Root cause:**
`_build_deps_table()` is only called on `on_mount`. The `action_refresh()` method rebuilds the mod list table but does not call `_build_deps_table()`.

**Fix:**
Add `self._build_deps_table()` to `action_refresh()`. One line fix.

---

### BUG-005: Uninstalled mods leave orphaned empty folders
**Severity:** High  
**Status:** Open  
**Reported:** 2026-06-10  

**Symptoms:**
- After uninstalling Virtual Atelier, `r6/scripts/virtual-atelier-full/` folder remained empty
- ChooMod's scan_mods picked up the empty folder as an unmanaged "Script/Plugin" mod with 0kb
- Creates ghost entries in the mod list after clean uninstalls

**Root cause:**
`uninstall_mod()` deletes tracked files but doesn't clean up empty parent directories. The folder cleanup logic exists in the code but only attempts to remove the immediate parent, not the full chain.

**Fix needed:**
After deleting all files for a mod, walk up the directory tree and remove any directories that are now empty, stopping at known game root folders (`r6/scripts`, `red4ext/plugins`, etc.) so we don't accidentally delete those.

---

### BUG-006: Framework mods show no file size in mod list
**Severity:** Medium  
**Status:** Open  
**Reported:** 2026-06-10  

**Symptoms:**
- Framework mods installed manually show 0kb in the mod list
- ArchiveXL shows correct size because it was reinstalled through ChooMod

**Root cause:**
Script/plugin-only mods that have no `.archive` file get `size_kb: 0` hardcoded in `scan_mods`. The manifest tracks `installed_files` but the display logic doesn't sum their sizes.

**Fix:**
For manifest-tracked mods with no archive file, sum the actual file sizes from `installed_files` paths instead of defaulting to 0.

---

## Low (cosmetic / minor)

### BUG-007: Stray 'g' character at end of README
**Severity:** Low  
**Status:** Open  

The README ends with `*Choom is Night City slang for friend. Felt right.*g` — stray `g` needs removing.

---

## Investigation notes

### Codeware structure (needs verification)
Codeware v3.x+ has a dual structure:
- `red4ext/plugins/Codeware/` — binary component (`.dll` files)
- `r6/scripts/Codeware/` — script component (`.reds` files)
- Possibly `.xl` resource files in `archive/pc/mod/`

ChooMod's current FILE_ROUTES may not handle all three destinations from a single zip correctly. Need to inspect the actual Codeware zip to confirm.

### Toggle architecture gap
The full-file toggle works for mods ChooMod installed. It doesn't work for:
1. Mods installed manually (no manifest entry)
2. Mods installed by older ChooMod versions without `manifest_key`
3. Framework mods with no `.archive` file and no manifest entry

The adopt feature is the correct long-term solution — adopt first, then toggle. The UX needs to guide users toward this rather than silently failing.
