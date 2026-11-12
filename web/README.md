Aegis Shield Console and static Aurora Home arena. Scope and contracts are defined in the root `project_brief.md`.

Set `NEXT_PUBLIC_API_URL` using `.env.example`, then run `pnpm dev`. The browser connects directly to FastAPI; its CORS configuration must allow the web origin.

- `/`: server-provided demo presets and a one-click labelled sample event stream.
- `/runs`: sample viewer; persisted run history is pending backend integration.
- `/stats`: server-provided evaluation counts, explicitly labelled when illustrative.
- `/health`: remote Chromium infrastructure check.
- `/arena/index.html?traps=none`: clean simulated shop.

Live launch remains unavailable until the run API is implemented. The sample button always plays the fixed `sample` run; it does not execute the listed presets. Sample approvals are displayed as recorded events and never sent as human consent.

Checks: `pnpm typecheck`, `pnpm lint`, `pnpm build`, and `node --test lib/events.test.mjs`. The stream tests check completion, duplicate frames, transport errors, and cleanup. Generated `lib/api-types.ts` must come from the server OpenAPI; never edit it manually.
