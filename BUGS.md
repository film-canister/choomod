# ChooMod Bug Tracker

### Active Issues

- **[Critical] Proton Version Switch Invalidation**: Switching Proton versions in Steam/Heroic causes the game to reject the `r6/cache/modded` folder.
    - *Status*: Mitigation added in v1.2.0 via aggressive cache clearing on refresh/toggle.
    - *Workaround*: Press 'Refresh' (R) or 'Clear Cache' in ChooMod before launching if Proton was changed.

- **[High] Script Trace Errors**: The game detects "traces of old mods" if empty folders are left in `r6/scripts`.
    - *Status*: Improved recursive folder cleanup added.

### Resolved

- [x] Toggling managed mods didn't persist in manifest (v1.1.2)
- [x] scc.exe missing .choobak backups (Non-issue: scc.exe is not a vanilla file)