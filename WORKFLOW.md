# DZSL — WORKFLOW (shared: claude + codex)

Canonical process both agents follow. Lives in the shared working folder
`/mnt/Storage1tb/coding/DZSL` (gitignored, so it travels across branch checkouts
and is not shipped to the repo).

## Branches
- `claude/work` — Claude's dev/testing branch.
- `codex/work` — Codex's dev/testing branch.
- `claude/codex-base` — shared integration branch. Finished, tested fixes meant
  for release land here. This is the ONLY branch promoted to `main`.
- `main` — clean install ONLY: just the files needed to run on a fresh PC.
  No `tests/`, no `.github/`, no AI logs/tooling, no dev files. Stripped from
  `claude/codex-base` before promotion. Never pushed without the human (Andreas)
  confirming it works.

## Rules
1. Each agent works on its OWN `*/work` branch. Never commit dev work directly
   to `claude/codex-base` or `main`.
2. Both agents share ONE working folder — only one branch is checked out at a
   time. Do NOT run claude and codex simultaneously here, or the checkout and
   uncommitted files collide. Take turns (or use a git worktree).
3. Sync between agents goes through GitHub: commit + push, the other fetches.
   There is no live change detection.
4. A fix ready for both / for release → merge into `claude/codex-base`.
   `claude/codex-base` → `main` only after Andreas verifies it runs.
5. `main` stays clean-install-only. Strip dev files before promoting.

## Conventions
- No `#` comments and no docstrings in code (hard user rule).
- Log every working fix/change in `updatelogs` (shared, gitignored, repo root).
- Cross-agent task handoffs: `workorder-*.md` files (gitignored).
- Keep `CLAUDE.md` (gitignored) current after structural changes.

## Handoffs in flight
- `workorder-codex-steam-pause.md` — codex to fix the Steam-pauses-during-download
  bug (native Steam API masquerades as DayZ AppID 221100 → Steam pauses downloads).
