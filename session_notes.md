# Session notes

A short, plain-language log of what each work session did. Any agent (Claude Code, Codex, or
another) or human working in this repo follows the same rule.

## Rule

- **At the start of a session:** read the latest entries here so you know where things stand.
- **At the end of a session** (or before your last push): add one entry at the **top** of the log.
- Keep it short: date, who/which agent, 3–6 bullets in simple words. What changed, what works now,
  what's blocked or next. No code, no long explanations; link a file if needed.
- Commit it with your last commit of the session.

Template:

```
### YYYY-MM-DD · <Dev A / Dev B> · <agent>
- Did: ...
- Works now: ...
- Blocked / next: ...
```

## Log

### 2026-11-12 · Dev A · Claude Code
- Built the shared data format (schemas), a sample live run, and the server routes the console uses.
- Built the AI shopper: reads the page, asks the model what to click, clicks by screen position.
  It buys the lamp on the clean shop (₹1,299).
- First baseline test: unprotected agent fell for 1 of 6 traps (T02 overlay). Model chosen:
  Groq `gpt-oss-120b` (limit: ~5 calls/min). Details in `eval/README.md`.
- Hosting: Oracle full, Cloudflare quick tunnel breaks live streaming, Hugging Face needs a paid
  plan. Backend now runs on Dev A's PC via Tailscale at `https://tequila-sunset.tailaa5d70.ts.net`;
  `deploy/smoke.sh` passes. Keep `uvicorn` running on that PC.
- Next: Friday's protection checks (A1–A5, B5, C1) and the live run API. Still want a cloud VM
  for submission, and sneakier trap variants (only 1/6 baseline traps worked).
