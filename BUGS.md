# ChooMod Bug Tracker

This file tracks known issues and their current resolution status.

## Active Issues

### [BUG-001] Mod installation corrupts vanilla game files
**Description:** Framework mods (Redscript, Red4Ext, etc.) often overwrite vanilla files. If ChooMod uninstalls or disables these mods without restoring the original files, the game installation becomes "corrupted" (missing core components).
**Status:** `IN_TESTING` (Fix implemented in v1.2.0-dev)
**Solution:** Implemented a `.choobak` backup system. ChooMod now identifies vanilla files, backs them up before overwriting, and restores them on uninstall or toggle.

**Verification Checklist:**
- [ ] Install Redscript -> Verify `engine/tools/scc.exe.choobak` exists.
- [ ] Disable Redscript -> Verify `scc.exe` is restored (vanilla version) while `scc.exe.disabled` exists.
- [ ] Uninstall Redscript -> Verify `scc.exe` is permanently restored and `.choobak` is removed.