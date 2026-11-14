"""E6 demo: a stock browser-use 0.13 agent on the arena, with and without AegisTools.

    cd server && PYTHONPATH=. uv run --isolated --no-project --with browser-use==0.13.14 \\
      --with playwright==1.65.0 --with 'psycopg[binary]' python ../eval/browser_use_demo.py \\
      [--traps T03] [--unprotected] [--auto-approve]

Serves web/public locally, uses --model (keys from the repo .env) through
browser-use's own ChatOpenAI, and prints every Aegis verdict plus the final page. A pilot
demo, not an eval run: one sample, no repetition, and browser-use's prompt, not ours.
"""

import argparse
import asyncio
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from browser_use import Agent, BrowserSession, ChatGoogle, ChatOpenAI, Tools
from playwright.async_api import async_playwright

from aegis.llm import BASE_URLS, LLMRouter
from aegis.presets import DEFAULT_TASK
from aegis.schemas import AskPayload
from aegis.wrap import AegisTools, _snapshot

PUBLIC = Path(__file__).resolve().parents[1] / "web" / "public"


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        pass


def serve() -> str:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Quiet, directory=str(PUBLIC)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/arena"


async def ask_terminal(ask: AskPayload) -> bool:
    what = f"{ask.action.type} {ask.action.target_id}" if ask.action else "the request"
    print(f"\n[AEGIS ASK] {ask.reason}: {what}")
    for f in ask.findings:
        print(f"  - {f.detector}: {f.evidence}")
    answer = await asyncio.to_thread(input, "Approve? [y/N] ")
    return answer.strip().lower() == "y"


async def auto_approve(ask: AskPayload) -> bool:
    print(f"\n[AEGIS ASK] {ask.reason} -> SIMULATED DEMO APPROVAL (not a human)")
    return True


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--traps", default="T03")
    p.add_argument("--unprotected", action="store_true")
    p.add_argument("--auto-approve", action="store_true")
    p.add_argument("--max-steps", type=int, default=15)
    # browser-use's own prompt (~9K tokens) is over Groq's free 8K TPM: default to Gemini.
    p.add_argument("--model", default="gemini:gemini-3.5-flash-lite", help="provider:model")
    a = p.parse_args()

    router = LLMRouter()
    provider, model = a.model.split(":", 1)
    key = router._keys(provider)[0]
    # Gemini's OpenAI-compatible endpoint rejects browser-use's output schema: use its own client.
    if provider == "gemini":
        llm = ChatGoogle(model=model, api_key=key, temperature=0)
    else:
        llm = ChatOpenAI(model=model, base_url=BASE_URLS[provider], api_key=key, temperature=0)
    url = f"{serve()}/index.html?traps={a.traps}"
    task = f"{DEFAULT_TASK} Start at {url}"
    tools = Tools() if a.unprotected else AegisTools(
        DEFAULT_TASK, approve=auto_approve if a.auto_approve else ask_terminal
    )  # fmt: skip

    async with async_playwright() as pw:
        exe = pw.chromium.executable_path
    session = BrowserSession(headless=True, executable_path=exe, user_data_dir=None,
                             keep_alive=True, viewport={"width": 1280, "height": 720})  # fmt: skip
    agent = Agent(task=task, llm=llm, tools=tools, browser_session=session, use_vision=False)
    print(f"model {provider}:{model} | {'UNPROTECTED' if a.unprotected else 'AEGIS'} | {url}")
    try:
        history = await agent.run(max_steps=a.max_steps)
        final = await session.get_current_page_url()
        snap = await _snapshot(await session.get_or_create_cdp_session())
        seen = [e.text for e in snap.elements if "₹" in e.text or "confirmed" in e.text.lower()]
    finally:
        await session.kill()

    if isinstance(tools, AegisTools):
        print(f"\nledger: {tools.ledger.model_dump_json() if tools.ledger else None}")
        for action, verdict in tools.log:
            print(f"  {verdict.decision:7} {action.type} {action.target_id or action.url or ''}"
                  f"  {[f.detector for f in verdict.findings]}")  # fmt: skip
    print(f"\nfinal page: {final}\n  " + "\n  ".join(seen[:8]))
    print(f"agent says: {history.final_result()}")


if __name__ == "__main__":
    asyncio.run(main())
