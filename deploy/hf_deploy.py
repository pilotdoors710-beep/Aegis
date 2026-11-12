"""Deploy server/ to the Hugging Face Docker Space (backup host while no VM exists).

Run from the repo root:  uvx --from huggingface_hub python deploy/hf_deploy.py [--code-only]

Reads HF_TOKEN and the server settings from the root .env (never uploaded). API keys become Space
*secrets* (encrypted, never shown publicly); non-secret settings become Space variables. Only
server code is uploaded: Dockerfile, pyproject.toml, uv.lock, aegis/, api/ and a README header.
"""

import os
import subprocess
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parents[1]
REPO = "eyerin/aegis-server"
WEB = "https://aegis-mu-sepia-91.vercel.app"
SECRETS = [
    "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "CEREBRAS_API_KEY",
    "SUPABASE_DB_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
]  # fmt: skip
README = """---
title: Aegis server
emoji: 🛡️
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
---
Backend for Aegis, runtime security middleware for browser agents (hackathon prototype).
Deployed from the project repo's `server/` directory by `deploy/hf_deploy.py`.
"""


def load_env() -> dict[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    env = load_env()
    api = HfApi(token=env["HF_TOKEN"])
    code_only = "--code-only" in sys.argv

    api.create_repo(REPO, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    if not code_only:
        for k in SECRETS:
            if env.get(k):
                api.add_space_secret(REPO, k, env[k])
                print("secret  ", k)
        variables = {
            "AGENT_MODELS": env["AGENT_MODELS"],
            "GROQ_RPM": env.get("GROQ_RPM", "5"),
            "GEMINI_RPM": env.get("GEMINI_RPM", "4"),
            "OPENROUTER_RPM": env.get("OPENROUTER_RPM", "15"),
            "CORS_ORIGINS": f"http://localhost:3000,{WEB}",
            "ARENA_BASE_URL": f"{WEB}/arena",
            "FAIL_MODE": "closed",
        }
        for k, v in variables.items():
            api.add_space_variable(REPO, k, v)
            print("variable", k)

    srv = ROOT / "server"
    ops = [CommitOperationAdd("README.md", README.encode())]
    for name in ["Dockerfile", "pyproject.toml", "uv.lock", ".python-version"]:
        if (srv / name).exists():
            ops.append(CommitOperationAdd(name, str(srv / name)))
    for d in ["aegis", "api"]:
        for f in sorted((srv / d).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                ops.append(CommitOperationAdd(str(f.relative_to(srv)), str(f)))
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()  # fmt: skip
    api.create_commit(REPO, repo_type="space", operations=ops,
                      commit_message=f"deploy server from {sha}")  # fmt: skip
    print(f"uploaded {len(ops)} files from {sha}")
    print(f"space: https://huggingface.co/spaces/{REPO}")
    print(f"url:   https://{REPO.replace('/', '-')}.hf.space")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
