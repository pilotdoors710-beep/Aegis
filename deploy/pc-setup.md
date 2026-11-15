# Backend host: Dev A's PC

The backend runs only on Dev A's PC. There is no cloud VM or hosted Space.
Tailscale Funnel exposes it at `https://tequila-sunset.tailaa5d70.ts.net` (proxies to
`localhost:8000` and streams SSE). The web app stays on Vercel.

1. Put the keys in `.env` at the repo root (names in `server/aegis/config.py`); set `CORS_ORIGINS` to the Vercel URL.
2. Put the Sybil artifact (4 files) in `server/data/sybil/` if Sybil is enabled, and set
   `SYBIL_DATA_DIR=<absolute path to server/data/sybil>` in `.env` (the default `/app/data/sybil` only exists in Docker).
3. Start the server: `cd server && uv run uvicorn api.main:app --host 127.0.0.1 --port 8000`
   (or `cd deploy && docker compose up -d --build`).
4. Expose it: `tailscale funnel --bg 8000`.
5. Check: `SERVER=https://tequila-sunset.tailaa5d70.ts.net WEB=<vercel url> deploy/smoke.sh`

The PC must stay on, with the server and Funnel running, for the live URL to work.
A Cloudflare quick tunnel is not usable: it buffers SSE.
