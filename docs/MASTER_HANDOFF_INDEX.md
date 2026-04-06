# Master Handoff Index

A catalog of all session handoffs. Newest entries at the top. Each entry is a one-line summary — read the full handoff document for details.

---

**Handoff [04-06-2026_16-48-31_EDT](handoffs/04-06-2026_16-48-31_EDT.md)** — TWO MAJOR DISCOVERIES. (1) Difficulty "secondary copy" found at `L_World+10` — game reads from a tagless float array there, NOT from named entries. Direct hex edit confirmed working both at UI and gameplay level on Middle Eearth (crafting cost reduced to 0.1× as set). (2) `meta_data.char_type` field gates custom-world access — changing main character from `0` → `3` allowed Serious_Beans to join Middle Eearth (custom world) with all data intact. Also created README.md + run.bat one-click launcher. Status: working, **but `char_type=3` impact on standard worlds (Gielinor) is UNTESTED — critical first task next session**. parser.py difficulty methods still target wrong location and need rewrite. Next session goal: transfer Gielinor's storage chest contents to a custom world.

**Handoff [04-06-2026_03-41-14_EDT](handoffs/04-06-2026_03-41-14_EDT.md)** — Initial session: built Flask save editor from scratch, reverse-engineered character JSON + binary world `.sav` formats, implemented full character editing (skills/inventory/quests/spells/mounts/position/status effects) and partial world editing (chests/weather/events), reverse-engineered all 35 custom difficulty tags and built Phase 1 difficulty editor. Status: **working at file level**, but Phase 1 difficulty edits **do not apply in-game** (diagnostic test plan in TODO_TOMORROW.md). User confirmed: character editing untested but parser pulls correct data; difficulty edit failed in-game test.
