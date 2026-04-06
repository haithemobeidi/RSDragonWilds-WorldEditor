---
description: Run the start-session protocol — load context, assess state, plan
---

Execute the **Session Start Protocol** as defined in `SESSION_PROTOCOLS.md`.

Steps to perform now:

1. **Read context files** (in this order):
   - `CLAUDE.md` (project overview, current phase status)
   - `SESSION_PROTOCOLS.md` (full protocol reference if you need it)
   - The most recent handoff in `docs/handoffs/` (sort by filename, take the newest)
   - `TODO_TOMORROW.md` if it exists (carryover work from prior session)
   - Any other doc files at the project root (`SAVE_FORMAT.md`, `DIFFICULTY_SETTINGS.md`, etc.)

2. **Check git state:**
   - `git status` — uncommitted changes
   - `git log --oneline -10` — recent commits

3. **Check task list:**
   - Run TaskList to see any in-progress / pending tasks from prior session

4. **Verify environment:**
   - Confirm Python venv exists: `ls venv/`
   - Confirm Flask is installed in venv if relevant

5. **Briefly summarize for the user:**
   - Where the project stands (current phase, last session focus)
   - What's outstanding (pending tasks, TODO_TOMORROW items)
   - Suggest a starting point based on what's most pressing

6. **Wait for user direction** — don't start coding until they confirm what they want to work on this session.

Be concise. Lead with the summary, not a long preamble.
