# Development Session Protocols

This document defines the mandatory session protocols for all Claude Code development sessions on this project. These protocols ensure continuity, quality, and proper documentation across sessions.

---

## 📋 Session Start Protocol (MANDATORY)

Each Claude session must begin by following this checklist:

### 1. Context Loading
- [ ] Read `CLAUDE.md` in full for project overview
- [ ] Read any phase/plan files if they exist (`docs/`, `plan/`)
- [ ] Check `git log --oneline -10` for recent commits
- [ ] Read the most recent handoff document from `docs/handoffs/` (if any)
- [ ] Read `TODO_TOMORROW.md` (if any) for outstanding work from prior session

### 2. Environment Verification
- [ ] Confirm working directory is the project root
- [ ] Verify required tools/runtimes are installed (Python, Node, etc.)
- [ ] Check for `.env` files or local config that need attention

### 3. Current State Assessment
- [ ] Run `git status` to see uncommitted changes
- [ ] Identify any blocking issues or in-progress work from previous session
- [ ] Review TaskList for active tasks

### 4. Planning Before Action
- [ ] Use TaskCreate to capture session goals as discrete tasks
- [ ] Confirm user's goals for this session
- [ ] Break complex tasks into manageable steps
- [ ] Identify which specialized agents (if any) may be needed

---

## 🔄 During Session Best Practices

### Code Quality Standards
- [ ] **Comments for handoffs** — Explain non-obvious logic so future sessions can pick up where you left off
- [ ] **Consistent formatting** — Match the project's existing style
- [ ] **Test before declaring done** — Verify features actually work end-to-end, don't assume
- [ ] **Library-first approach** — Use existing packages, don't reinvent functionality
- [ ] **Honest feedback** — When something doesn't work, say so clearly. Don't paper over issues.

### 📦 Modularity Guidelines

#### Before Writing New Code:
1. **Search the existing codebase first** — Don't duplicate functionality
2. **Reuse existing helpers/utilities** when they fit
3. **Use existing styling/component patterns** — Don't introduce new conventions arbitrarily

#### While Developing:
- **Keep functions focused** — If a function does multiple things, split it
- **Target small, focused modules** — A file approaching ~500 lines should probably be split
- **Avoid premature abstraction** — Don't build helpers for hypothetical future needs

#### After Feature Complete:
- [ ] **Audit new files** — Check if any file exceeds reasonable size
- [ ] **Extract if bloated** — Split large files into logical modules
- [ ] **Update CODEBASE_INDEX.md** if it exists — Document new modules
- [ ] **No duplicate code** — If you copy/pasted, extract to a shared location

### Documentation Standards
- [ ] Update relevant markdown files when adding/changing features
- [ ] Document architectural decisions and the reasoning behind them
- [ ] Add comments explaining "why" not just "what"
- [ ] Keep `CLAUDE.md` current if scope or stack changes

### Communication Standards
- [ ] Update task statuses promptly — mark completed immediately when done
- [ ] Ask the user when requirements are unclear instead of guessing
- [ ] Provide clear, concise status updates as work progresses
- [ ] Be honest about limitations or uncertainties

---

## 🏁 End Session Protocol (MANDATORY)

When user confirms work is complete and says **"end session"**, **"session end"**, or **"end protocol"**, Claude must follow this exact order:

### Step 1: Get the actual current time
```bash
date '+%Y-%m-%d %H:%M:%S %Z'
```
**NEVER guess the time.** Always run this command and use the real result.

### Step 2: Check git state
```bash
git status
git diff --stat
```
Understand what changed before writing the handoff.

### Step 3: Update Documentation (If Needed)
**Only update if significant changes were made:**
- [ ] **CODEBASE_INDEX.md** — Update if files added/removed or major structural changes
- [ ] **CLAUDE.md** — Update if project scope/tech stack/phase status changed
- [ ] **README.md** — Update if user-facing features changed

**Skip this step if:** Only bug fixes, minor tweaks, or no new files added.

### Step 4: Create Session Handoff Document (ALWAYS)
**File path:** `docs/handoffs/MM-DD-YYYY_HH-MM-SS_<TZ>.md`

Use the actual time from Step 1. Use the template at the bottom of this document.

### Step 5: Update Master Handoff Index (ALWAYS)
**File:** `docs/MASTER_HANDOFF_INDEX.md`

Add new entry at the TOP in this format:
```markdown
**Handoff MM-DD-YYYY_HH-MM-SS_<TZ>** — [Brief 1-sentence summary], status: [working/broken], user confirmed: [yes/no]
```

If the file doesn't exist yet, create it with a header.

### Step 6: Git Commit (ALWAYS)
**Commit everything from this session:**
```bash
git add docs/handoffs/<new file>
git add docs/MASTER_HANDOFF_INDEX.md
git add CLAUDE.md  # if updated
git add CODEBASE_INDEX.md  # if updated
git add <other modified files>

git commit -m "Session end MM/DD/YYYY: <Brief summary>

- <Key accomplishment 1>
- <Key accomplishment 2>
- <Files modified count>

🤖 Generated with Claude Code"
```

**DO NOT push unless user explicitly requests it.**

---

## 📄 Handoff Document Template

```markdown
# Session Handoff — MM/DD/YYYY HH:MM:SS <TZ>

## Session Summary
[2-3 sentence overview of session goals and what was accomplished]

## Accomplishments This Session
- [Feature/fix 1 — specific files/functionality]
- [Feature/fix 2 — what it does]
- [Documentation updated — which files]

## Current Project Status
**Build Status:** [✅ Working / ⚠️ Issues / ❌ Broken]
**Tests Passing:** [Yes/No/N/A]
**User Confirmation:** [User confirmed feature works: Yes/No/Pending]

**Active Issues:**
- [Any known bugs or incomplete features]
- [Blockers for next session]

## Files Modified This Session
### Added:
- `path/to/file` — [Brief description]

### Modified:
- `path/to/file` — [What changed and why]

### Deleted:
- `path/to/file` — [Why removed]

## Technical Notes
**Dependencies Added:**
- `package@version` — [Why]

**Configuration Changes:**
- [Any config file changes]

## Next Session Recommendations

### Priority 1 (Must Do Next):
1. [Most important task]
2. [Second most important]

### Priority 2 (Should Do Soon):
1. [Important but not urgent]

### Priority 3 (Future Enhancement):
1. [Nice to have]

### Specific Notes for Next Claude:
- [Anything the next session should know]
- [Gotchas, edge cases discovered]
- [Design decisions made and rationale]

## User Feedback
**User Said:**
- "[Direct quotes if user gave specific feedback]"

**User Requested:**
- [Any feature requests or changes user mentioned]

---

*Session concluded. All changes documented and committed.*
```

---

## 🚨 Critical Rules

### Never Skip These:
1. ✅ **Always create handoff document** — Even for "quick fixes"
2. ✅ **Always update master index** — Maintains session history
3. ✅ **Always commit handoff files** — Ensures continuity
4. ✅ **Always test before ending** — User confirms it works
5. ✅ **Always use TaskCreate/TaskUpdate** — Track progress visibility
6. ✅ **Always get the real current time** — Never guess timestamps

### Never Do These:
1. ❌ **Never commit without user confirmation** — User must verify it works
2. ❌ **Never push to remote without explicit request** — User decides when to push
3. ❌ **Never skip documentation** — Future Claude sessions depend on it
4. ❌ **Never batch multiple sessions into one handoff** — One session = one handoff
5. ❌ **Never lie or paper over failures** — Be honest about what didn't work

---

## 📊 Quality Checklist (Before Session End)

### Code Quality
- [ ] No build errors
- [ ] No new warnings introduced (or all justified)
- [ ] No console errors when running
- [ ] All TODOs either completed or documented in handoff

### Testing
- [ ] Manual testing completed (user tried the feature)
- [ ] Edge cases considered
- [ ] No regressions (old features still work)

### Documentation
- [ ] Comments added for complex logic
- [ ] CLAUDE.md updated if needed
- [ ] Handoff document is thorough

### Git
- [ ] All changes staged (nothing left uncommitted that should be committed)
- [ ] Commit message is clear and descriptive
- [ ] Handoff files included in commit
- [ ] User approved committing

---

## 🎯 Success Criteria

A session is considered successful when:
1. ✅ User confirms features work as expected (or honest about what doesn't)
2. ✅ Build/run completes without errors
3. ✅ All session goals from TaskList completed (or rescheduled to next session)
4. ✅ Handoff document comprehensively documents the session
5. ✅ All files committed with clear message
6. ✅ Master index updated with session summary

---

*These protocols ensure high-quality development and seamless handoffs between Claude sessions. Follow them strictly for project continuity.*
