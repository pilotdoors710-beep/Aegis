# Product

<!-- impeccable:product-schema 1 -->

Source of truth for scope, contracts and claims is `project_brief.md`. This file records only what design work needs.

## Platform

web

## Users

Primary: a hackathon judge watching a two-minute stage demo on a 1280×720 projector while a presenter drives. They must read the difference between an unprotected browser agent and the same agent with Aegis within seconds, then ask about novelty, false positives, latency and limits.

Secondary: the presenter operating the console under time pressure (one click to launch, no typing), and anyone who opens the live URL later on their own.

## Product Purpose

Aegis is runtime security middleware for autonomous browser agents. It inspects each action an agent is about to take on a live page and decides ALLOW, BLOCK, REROUTE or ASK before the action runs. Before anything irreversible (pay, submit, subscribe) it audits the page's final state against what the user actually authorized.

Success for the interface: a judge sees, in one paired run, what the unprotected agent agreed to, what the protected agent agreed to, and the evidence chain that explains the difference.

## Positioning

"We don't try to out-think the trap. We check the receipt before signing." The user's authorization is written to a fixed ledger before browsing; observed cart, totals and recurring terms are compared against it; the agent corrects through ordinary actions and Aegis rechecks. The same checkout is rejected or permitted depending on what the user asked for.

## Operating Context

- Stage demo: 2 minutes plus 2 minutes of questions, hard buzzer, 1280×720 projector, dark room. Demos start at `/console`.
- Paired run: unprotected agent on the left, agent with Aegis on the right, live screenshots streaming, both starting from the same task.
- Routes: `/` entrance, `/console` presets and sample run, `/runs` history and step replay, `/lab` disposable consent trials (experimental), `/scan` read-only scan of a public URL, `/stats` evaluation results, `/health` infrastructure check, `/arena` static trap shop (separate, not part of the console's look).

## Capabilities and Constraints

- Split screen is required: left "Unprotected agent", right "With Aegis", each with a live screenshot and a step counter. No third permanent browser pane.
- Flagged elements get a red box and label on the screenshot; choosing a verdict in the feed highlights its element.
- The permission ledger is always visible on the protected side and never changes during a run.
- Evidence connects user permission, observed page evidence, decision, agent correction and recheck. Authorized extras are shown as permitted, never as malicious.
- ASK opens an approve or deny dialog. Sample approvals, replays, cached decisions and simulated approvals each carry a visible label and are never presented as fresh or live.
- End of run: one outcome per side (what was bought or agreed to, total paid). The divergence must be obvious in under five seconds.
- No layout shift while a run is streaming. Works at 1280×720. Dark by default.
- Terminology is fixed: ALLOW, BLOCK, REROUTE, ASK; trap ids T01 to T11; "Unprotected agent" and "With Aegis".
- All orders, charges and data in the arena are simulated.

## Brand Commitments

- Name: Aegis. Wordmark is "AEGIS" in capitals.
- Dark ground with warm off-white text and one orange accent. The user chose to keep this identity for the console (14 Nov 2026).
- Interface components come from React Bits (reactbits.dev); the user asked for its effects across the console, including the live run view (14 Nov 2026).
- Voice: plain and specific. Claims are bounded by evidence: no "first ever", no universal detection, no production security claim.

## Evidence on Hand

- A recorded sample run (`/runs/sample`) and live presets served by the backend.
- Evaluation results on `/stats`, labelled sample, pilot or final. Counts and denominators stay visible.
- No customers, testimonials, pricing or benchmarks beyond the arena study exist; none may be invented.

## Product Principles

1. Show the receipt. Every non-ALLOW decision carries human-readable evidence.
2. Compare, don't assert. The two agents sit side by side and the outcome speaks.
3. Label what is not live. Samples, replays and simulated approvals say so.
4. Safe completion is the goal, not blocking. Permitted options read as permitted.
5. Nothing moves the ground under a reader: streaming never shifts the layout.

## Accessibility & Inclusion

Keyboard reachable throughout, visible focus, reduced-motion and reduced-transparency paths, forced-colors support (all present in the current console and to be preserved). Text contrast at least 4.5:1 for body copy.
