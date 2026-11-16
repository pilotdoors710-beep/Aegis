# Live events stream over SSE from the backend, not Supabase Realtime

The browser connects straight to FastAPI for a run's Events (SSE, 15 s heartbeat, resumable with `Last-Event-ID`). Postgres stores Events and Storage holds screenshots for Replay. The web app never holds Supabase keys and reads replays through the backend REST API. Realtime would have exposed database credentials to the client and added a second live path that could drift from the persisted one.
