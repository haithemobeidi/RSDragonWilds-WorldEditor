---
description: Run the end-session protocol — handoff doc, index update, commit
---

Execute the **End Session Protocol** as defined in `SESSION_PROTOCOLS.md`.

Perform these steps **in order**:

### Step 1: Get the actual current time
Run this command — never guess the timestamp:
```bash
date '+%Y-%m-%d %H:%M:%S %Z'
```
Use the result for the handoff filename and document title.

### Step 2: Check git state
```bash
git status
git diff --stat
```
Note what's changed for the handoff doc.

### Step 3: Update top-level docs IF significant changes were made
- `CLAUDE.md` — only if scope/stack/phase status changed
- `CODEBASE_INDEX.md` — only if files added/removed/restructured
- `README.md` — only if user-facing functionality changed
- Skip this step entirely if changes were small/iterative

### Step 4: Create the session handoff document
Path: `docs/handoffs/MM-DD-YYYY_HH-MM-SS_<TZ>.md`

Use the template from `SESSION_PROTOCOLS.md` (the "Handoff Document Template" section). Fill in honestly:
- Session summary (2-3 sentences)
- Accomplishments (specific, file-level)
- Build status, test status, user confirmation status
- Files added/modified/deleted with brief descriptions
- Active issues / blockers
- Next session priorities (P1 / P2 / P3)
- Specific notes for the next Claude session
- Direct user quotes if there were any notable ones

### Step 5: Update the master handoff index
File: `docs/MASTER_HANDOFF_INDEX.md`

If it doesn't exist, create it with a header. Add the new entry **at the top** (newest first) in this format:
```markdown
**Handoff MM-DD-YYYY_HH-MM-SS_<TZ>** — [1-sentence summary], status: [working/broken/partial], user confirmed: [yes/no/pending]
```

### Step 6: Commit (do not push)
```bash
git add docs/handoffs/<new file>
git add docs/MASTER_HANDOFF_INDEX.md
git add CLAUDE.md  # if updated
git add CODEBASE_INDEX.md  # if updated
git add <other modified files from this session>

git commit -m "$(cat <<'EOF'
Session end MM/DD/YYYY: <Brief summary>

- <Key accomplishment 1>
- <Key accomplishment 2>
- <Files modified count>

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Do NOT push to remote unless the user explicitly says so.**

### Critical rules
- ❌ Never guess the time — always run `date`
- ❌ Never skip the handoff even for "quick" sessions
- ❌ Never lie about what worked vs didn't — be honest in the handoff
- ✅ One session = one handoff doc
- ✅ Always update the master index
- ✅ Always commit (but don't push)

After the commit, briefly tell the user the session is wrapped up and summarize the key items for the next session.
