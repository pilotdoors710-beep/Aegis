# One backend process, one shared Chromium, one paired Run at a time

The backend is a single replica on Dev A's PC behind Tailscale Funnel, with zero hosting budget. It launches one Chromium and gives each Side a fresh BrowserContext. A semaphore (`MAX_CONCURRENT_RUNS`, default 1) queues further Runs. Asks are in-memory futures resolved by `POST /runs/{id}/ask/{ask_id}`. That works only because there is exactly one process, so scaling out would first need a shared Ask store.
