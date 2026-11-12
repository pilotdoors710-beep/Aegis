Aegis Shield Console and static Aurora Home arena. Scope and contracts are defined in the root `project_brief.md`.

Set `NEXT_PUBLIC_API_URL` using `.env.example`, then run `pnpm dev`. The browser connects directly to FastAPI; its CORS configuration must allow the web origin.

- `/`: server-provided demo presets and a one-click labelled sample event stream.
- `/runs`: sample viewer; persisted run history is pending backend integration.
- `/stats`: server-provided evaluation counts, explicitly labelled when illustrative.
- `/health`: remote Chromium infrastructure check.
- `/arena/index.html?traps=none`: clean simulated shop.

Live launch remains unavailable until the run API is implemented. The sample button always plays the fixed `sample` run; it does not execute the listed presets. Sample approvals are displayed as recorded events and never sent as human consent.

Checks: `pnpm typecheck`, `pnpm lint`, `pnpm build`, and `node --test lib/events.test.mjs`. The stream tests check completion, duplicate frames, transport errors, and cleanup. Generated `lib/api-types.ts` must come from the server OpenAPI; never edit it manually.

Day 1 deployment verification:

1. In Vercel, use `web/` as the project root and set `NEXT_PUBLIC_API_URL` to the public FastAPI origin before building. Redeploy after changing this build-time variable.
2. Give Dev A the production web origin for `CORS_ORIGINS` and its `/arena` URL for `ARENA_BASE_URL`.
3. From `web/`, run `pnpm verify:day1 --web https://YOUR-WEB-HOST --server https://YOUR-SERVER-HOST`. This checks public routes, exact-origin CORS, remote Chromium, its arena access, one LLM smoke call, presets, and the complete labelled sample stream. It does not create a real agent run.
4. In a browser at 1280×720, open `/health` and confirm the screenshot renders. On `/`, play the sample and confirm both sides update under SAMPLE DATA; in the network panel, verify one event-stream connection ends after both sides finish. Repeat public access from a phone hotspot. The command-line check cannot replace these browser/network checks.
