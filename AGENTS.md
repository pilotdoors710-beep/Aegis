# AGENTS.md

Read [`project_brief.md`](project_brief.md) in full before writing any code. It is the single source of truth for scope, architecture, data contracts and engineering rules. If a request conflicts with it, ask the human first.

Quick rules (details in the brief, §11):
- Your area: `web/` (Shield Console + static Trap Arena in `web/public/arena/`) unless told otherwise.
- Never hand-edit `web/lib/api-types.ts`; regenerate it from the server's OpenAPI (`pnpm gen:types`).
- Secrets only via env vars; never commit `.env`.
- Commit directly to `main` (no feature branches or PRs): run the web checks locally, `git pull --rebase origin main`, then `git push origin main`. Keep `main` green.
- Once per clone: `git config core.hooksPath .githooks`. The pre-commit hook runs ruff on any `server/` Python you commit (CI fails on style). Fix with `cd server && uv run ruff format . && uv run ruff check --fix .`.
- Read `session_notes.md` at the start of a session. Before ending a session, add a short entry at the top of its log in simple words (rule inside the file).
