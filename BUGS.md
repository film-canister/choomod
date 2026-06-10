# ChooMod Bug Tracker & Dev Notes

## Active Issues

### [BUG-001] Mod installation corrupts vanilla game files
**Description:** Framework mods (Redscript, Red4Ext, etc.) overwrite vanilla files (e.g., `scc.exe`). If ChooMod uninstalls or disables these without restoring the originals, the game fails to launch or compile scripts.
**Status:** `IN_TESTING` (v1.2.0-dev)
**Implemented Fix:** 
- Added `.choobak` system to `install_from_plan`.
- Added restoration logic to `uninstall_mod` and `toggle_mod`.
- Added "Vanilla Overwrite" warnings to the Install Preview.

**Verification Checklist:**
- [ ] Install Redscript -> Verify `engine/tools/scc.exe.choobak` exists.
- [ ] Disable Redscript -> Verify `scc.exe` (vanilla) is restored; `scc.exe.disabled` (mod) exists.
- [ ] Re-enable Redscript -> Verify vanilla `scc.exe` is removed and mod version returns.
- [ ] Uninstall Redscript -> Verify `scc.exe` (vanilla) is permanently restored.

---

## Session Notes

### 2024-XX-XX: Vanilla Protection Logic
- **The Problem:** Installing one dependency could "corrupt" the game because the manager didn't know what was there before the mod.
- **The Solution:** ChooMod now performs a "Check-before-Overwrite". If a file exists on disk but isn't in the manifest, it's flagged as "Vanilla".
- **Transactional Safety:** If an install fails, the rollback now restores any vanilla files that were moved during that specific session.
- **Toggle Behavior:** Toggling a mod off now "swaps" the vanilla file back in, keeping the game in a working state even when framework mods are disabled for testing.

### Testing Recommendations
- **Environment:** Use a standalone terminal (Kitty, Alacritty, etc.) for TUI testing. Built-in IDE terminals can mangle mouse input and color rendering.
- **Procedure:** Always check the `archive/pc/mod` and `engine/tools` directories manually during testing to ensure `.choobak` files are appearing and disappearing as expected.

## Resolved / Archive
*(Empty)*