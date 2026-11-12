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

### 2026-11-12 - Dev B - Codex side conversation - partner reference document
- Saved [DEFERRED_EXTENSIONS.md](DEFERRED_EXTENSIONS.md) in the project root for the human partner to review.
- Records ideas for supported external websites, disposable control experiments, and an optional Deep check mode.
- Agents must not use this document as a work plan or activate it after core completion. A new explicit human instruction and reconciliation with the active brief are required.
- Documentation only; no implementation, active scope, budget, contracts, or current priorities changed. User requested publishing this reference on main.

### 2026-11-12 · Dev A · Claude Code
- Did: fixed `SUPABASE_URL` in `.env` (it had `/rest/v1/` on the end, so screenshot uploads got 404).
- Did: the approval popup now closes as soon as the server accepts Approve/Deny (`web/app/(console)/approval-dialog.tsx`); before, it could stay open until a reload.
- Works now: live run → approve → popup closes → run finishes (tested locally and on Vercel through the tunnel).
- Next: the popup text shows code names (`items[0].max_price`, `e36`); make it plain English with a one-line "everything matches" summary.


### 2026-11-12 - Dev B - Codex - approval and evidence integration
- Pulled Dev A's audit, recovery, R1 tests and page-load fixes. Built the approval dialog, audit evidence chains, and outcome comparison grouped by proposed/approved/executed commitments.
- Added the existing-contract Gift wrap option: INR 49 once, clean total INR 1,348, persisted selection and visible receipt. The backend's benign-option test now runs and passes.
- Checks: types, lint, production build, 12 frontend tests, Chrome approval/error/timeout/sample/replay tests, and all 111 backend tests on local Chrome. Backend tests used Python 3.13 and installed packages, not uv's locked environment. Production gift wrap, read-only sample approval, evidence, outcomes and replay also passed. Outcome cards wait for both sides to finish to keep the live panes in place.
- Live run `f46b652a4bbc`: shielded bought the lamp for INR 1,299; unshielded aborted. The deployed server sent no ledger, asks or commitments, so this does not verify the full audit/approval flow. No retry was hidden.
- Next: Dev A must restart the backend at current main. Then verify real ledger, correction/recheck, approve/deny and both final outcomes through the production console; the successful full paired-run gate is still open.

### 2026-11-12 (late, Saturday cards early) · Dev A · Claude Code
- Did: T02 overlay neutralization; Supabase saving + replay; smoke.sh paired-run check; ledger
  (B1), checkout audit (B2), approve/deny gate (D2), fail-closed checks (D4), full protection
  in the loop (config I), R1 permission tests, outcome commitments, eval configs F/I.
- Works now: real r1-forbidden run: both sides buy the lamp for ₹1,299; protected side gets a
  labelled payment approval. 111 tests pass. Real runs also exposed and fixed: page-load race,
  agent chasing hidden popups, agent saying "done" at checkout.
- Blocked / next: apply `supabase/migrations/0001_init.sql` in Supabase, then restart the
  server. Gift wrap (Dev B, B-D3-04) unlocks the last R1 test. Run the eval pilot (A-D3-07).
- Risk: this model resists T03 too (unticks the plan itself); paired run is ~1:50, too slow.


### 2026-11-12 - Dev B - Codex
- Built Day 2 console highlights, clickable verdict evidence, the shielded permission panel, and replay step controls.
- Wired preset launch and run history to the existing API, including queue and unavailable-server messages. Samples and replays stay labelled.
- Added T07 faint instructions and T08 trick consent with clean twins. T08 checked shares data; clearing it stops sharing. Handoff details are in `web/README.md`.
- Checks passed: frontend types, lint, build, seven stream/verifier tests, and Chrome checks of the arena, replay, highlights, and mocked live launch at 1280x720. Vercel replay navigation and T08 deployment were verified after push; real stored-run replay also passed.
- Synced Dev A's new backend and displayed overlay-neutralization evidence. Real run `7512266a1d89` launched from the local production console and streamed both sides to completion, but both aborted without a purchase.
- Blocked: saved product/checkout snapshots had only four elements and an empty shop before deferred JavaScript ran. Dev A should wait for navigation and page readiness before snapshotting (executor/snapshot ownership). The successful paired-purchase gate remains open; Dev A also owns T07/T08 detector tests.

### 2026-11-12 (evening, Friday cards early) · Dev A · Claude Code
- Did: live run API (`POST /runs`, live SSE stream with reconnect, queue), arena-only network
  guard, detectors A1–A5 + B5 + C1, verdict engine, and the shielded side (blocks, feedback to
  the agent, 3 retries then an ask).
- Works now: a real paired run streams both sides; shielded T01 run blocked a click under the
  popup and still bought the lamp for ₹1,299. 63 tests pass.
- Blocked / next: restart `uvicorn` on the PC to deploy (Dev B needs it). Then save runs to
  Supabase (A-D2-07). Paired run takes ~2:45, above the 90 s demo gate: LLM rate limits.
- Open question: T02's invisible overlay leaves the shielded agent no way forward (it ends in an
  ask). Decide whether Aegis may neutralize an invisible overlay, or keep it as block + ask.


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
