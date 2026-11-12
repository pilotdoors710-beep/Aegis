> **Host used (12 Nov 2026):** Oracle A1 had no capacity and Hugging Face Docker Spaces need PRO.
> The backend currently runs on Dev A's PC behind Tailscale Funnel at
> `https://tequila-sunset.tailaa5d70.ts.net` (proxies to `localhost:8000`, streams SSE).
> A Cloudflare quick tunnel was rejected because it buffers SSE. A cloud VM is still wanted for
> submission; `deploy/smoke.sh` must pass against whichever host is used.

# Oracle Always Free: server setup

1. Create an Ampere A1 VM (Ubuntu 24.04, up to 2 OCPU / 12 GB). In the VCN security list, open ingress TCP 80 and 443.
2. On the VM: `sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git && sudo usermod -aG docker $USER` (re-login).
   Also open the OS firewall: `sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT` (Oracle images block by default).
3. `git clone <repo> && cd <repo>`; create `.env` at the repo root with your keys (see the variable names in `server/aegis/config.py`); set `CORS_ORIGINS` to the Vercel URL.
4. `cd deploy && SERVER_HOST=<dashed-ip>.sslip.io docker compose up -d --build`
5. Check from a phone on mobile data: `https://<dashed-ip>.sslip.io/healthz/browser`
