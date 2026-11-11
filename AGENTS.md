# AGENTS.md

Read [`project_brief.md`](project_brief.md) in full before writing any code. It is the single source of truth for scope, architecture, data contracts, engineering rules and schedule. If a request conflicts with it, ask the human first.

Quick rules (details in the brief, §9):
- Your area: `web/` (Shield Console + static Trap Arena in `web/public/arena/`) unless told otherwise.
- Never hand-edit `web/lib/api-types.ts`; regenerate it from the server's OpenAPI (`pnpm gen:types`).
- Secrets only via env vars; never commit `.env`.
- Work on a branch, open a PR, keep CI green.
