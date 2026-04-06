# Known Bugs & Issues

Tracker for known bugs in the editor and outstanding things to investigate. Newest at the top. Update status as items are resolved.

Format: each bug has an ID, severity, status, summary, what we know, what we suspect, and notes for the eventual fix.

---

## #001 — World Mode Conversion breaks ownership-bound features

**Severity:** Medium (data is not lost, but features stop working)
**Status:** OPEN
**Reported:** 2026-04-06 by Accurious in the RSDW Discord community
**Affects:** `convert_to_custom()` in `parser.py`, GUI button in `tab_world.html`

### Summary
After using the World Mode Conversion (Standard → Custom), the world ↔ character ownership binding appears to break. Features that depend on the original character being recognized as the world's "owner" stop working.

### Symptoms reported
- 🔒 **Locked chests** — original character can no longer open them after conversion
- 🛡️ **Protection totems** — bound to "local host of the world", become unusable
- 🔐 **Privacy settings** — affected (specifics TBD)
- World renders / character can join successfully — only the ownership features fail

### Workaround (current)
1. **BEFORE converting**, in-game:
   - Unlock and empty all locked chests you care about
   - Pick up / remove all protection totems
   - Note your privacy settings
2. Then convert
3. After joining, re-place totems and re-lock chests if needed

The GUI now shows a warning to this effect on the conversion confirmation dialog.

### What we know
- Conversion only flips 2 bytes (`L_World+9` uint32 enum AND first byte of `CustomDifficultySettings` PROP field)
- Conversion does NOT touch the schema fields `WorldSaveSettings/PlayerOwnerGuid`, `OwnerName`, or `GuidData`
- World can still be joined by both the original char_type=0 and a converted char_type=3 character
- Difficulty settings work correctly post-conversion

### Suspected root cause
The PROP block has an offset table at fields 0..12 (13 entries). We saw earlier:
```
TestWorld   PROP offsets: 0x0, 0x4, 0x14, 0x22, 0x30, 0x3c, 0x3d, 0x3f, 0x41, 0x49,  0xe5,  0xf7, 0x109
Middle E    PROP offsets: 0x0, 0x4, 0x14, 0x26, 0x38, 0x44, 0x45, 0x47, 0x49, 0x176, 0x212, 0x224, 0x236
Gielinor    PROP offsets: 0x0, 0x4, 0x14, 0x21, 0x2e, 0x3a, 0x3b, 0x3d, 0x3f, 0x16a, 0x75e, 0x770, 0x782
```

Field index 8 = `CustomDifficultySettings`, fields 9-12 = `LastSavedByEntries`, `PlayerOwnerGuid`, `GuidData`, `OwnerName`.

Notice the jump from offset[8] to offset[9] is HUGE in custom worlds (Middle E: 0x49 → 0x176, Gielinor: 0x3f → 0x16a) compared to standard (TestWorld: 0x49 → 0xe5). This is because CustomDifficultySettings grows when there are entries.

**Theory:** When we flip the mode byte to 0x03 inside CustomDifficultySettings without growing the field, the game's loader sees "this looks like a Custom array" and tries to read N entries, but the actual byte content doesn't match the expected layout. As a result, the loader either:
- Walks past the end of CustomDifficultySettings into PlayerOwnerGuid territory, parsing PlayerOwnerGuid bytes as difficulty data → real GuidData becomes garbage to the loader → game thinks the owner is someone else
- Or correctly reads CustomDifficultySettings but then can't find PlayerOwnerGuid because the offset table isn't updated → reads garbage

### Fix plan (when ready to tackle)
1. **Verify the theory** — read PlayerOwnerGuid bytes before and after conversion, see if they're being misinterpreted
2. **Decode the GuidData / PlayerOwnerGuid binary format** — likely a 16-byte GUID
3. **Compare** the GUID values in a converted world vs a fresh custom world to see if they're being corrupted vs being read from wrong location
4. **If offset table needs updating:** rewrite `convert_to_custom()` to also update the PROP offset table — this is non-trivial because PROP block size changes
5. **Alternative:** if mode flip doesn't actually require growing the CustomDifficultySettings array, the offsets shouldn't need to change. Confirm there's no implicit size assumption.

### Notes
- This bug doesn't apply when the world was ALREADY custom (e.g., Middle Eearth) — the offsets are correct from creation
- Only affects converting old standard worlds (e.g., Gielinor) to custom
- Reverting (custom → standard) probably has the inverse problem if it ever ships

---

## How to add a bug

Copy this template:

```markdown
## #NNN — Short title

**Severity:** Critical / High / Medium / Low
**Status:** OPEN / IN PROGRESS / FIXED / WONTFIX
**Reported:** YYYY-MM-DD by Name
**Affects:** path/to/file or feature

### Summary
1-2 sentences.

### Symptoms
Bullet list of observed behavior.

### Workaround (current)
What users should do until fixed.

### What we know
Facts gathered.

### Suspected root cause
Hypothesis with reasoning.

### Fix plan
Steps to fix (when ready).

### Notes
Anything else.
```
