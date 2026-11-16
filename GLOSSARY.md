# Aegis

Runtime protection for a browser agent: every action the agent proposes is checked against the page and against what the user authorized before it runs. A second area, Sybil, scores how much real web trust stands behind a shop.

## Runs and sides

**Run**:
One paired execution of a Preset: the same task, starting page and agent configuration, run once per Side.
_Avoid_: job, session, episode

**Side**:
One half of a Run, either Unshielded or Shielded; each Side evolves independently.
_Avoid_: lane, pane, arm (except in evaluation)

**Unshielded**:
The Side whose proposed actions execute with no Aegis checks. It is the baseline, not a weakened agent.
_Avoid_: unprotected agent (UI copy only), control

**Shielded**:
The Side whose proposed actions pass through Aegis before they execute.
_Avoid_: protected, guarded

**Shield configuration**:
Which defenses a Shielded side uses: F (fast detectors and filtering), I (F plus the Audit and the Human gate), I-minus-audit, or I+R2.
_Avoid_: mode (Mode means Shielded or Unshielded)

**Preset**:
A named, tested Run setup: task, Traps, arena variant and Shield configuration. The console and eval launch only Presets.
_Avoid_: scenario (a Sybil term), template

**Step**:
One snapshot, decide, check, execute cycle on a Side.

**Event**:
A typed record of one thing that happened in a Step (snapshot, decision, verdict, executed, ask, error, done), streamed live and stored for Replay.
_Avoid_: log line, message

**Replay**:
Showing a stored Run's Events. It always reads recorded evidence and never recomputes it.

## The agent and the page

**Agent**:
The base LLM browser agent that proposes one Action per Step. It is identical on both Sides.
_Avoid_: bot, model (Model is the LLM behind it)

**Action**:
What the Agent proposes to do next: click, type, select, navigate, submit or done, with a one-line rationale.
_Avoid_: command, move, tool call

**Snapshot**:
One reading of the page: every element with its geometry, styles, visibility and nearby text.
_Avoid_: DOM dump, page state

**Agent view**:
The subset of a Snapshot the Agent may see. On the Shielded side it is also Sanitized. Detector-only facts (opacity, contrast, occlusion, downloads) never appear in it.
_Avoid_: prompt context, observation

**Sanitize**:
Remove Injection and Persuasion text from the Agent view, recording what was removed.
_Avoid_: filter, scrub, clean

**Executor**:
What carries out an allowed Action on the live page. Clicks land at the target's centre point.

## Traps

**Trap**:
A deceptive page feature planted in the Arena to push the Agent into an unwanted outcome (T01–T08). Each has a Clean twin.
_Avoid_: dark pattern (the research term), attack, bug

**Trap type**:
The category a Finding names: hidden_info, preselection, trick_wording, obstruction, urgency, social_proof, disguised_ad, fake_control, clickjacking, prompt_injection, forced_action, untrusted_shop.

**Clean twin**:
The same Arena page with its Trap switched off, used to measure false blocks.
_Avoid_: control page, baseline page

**Arena**:
The fictional "Aurora Home" shop the Agent browses: product, cart, checkout, confirmation.
_Avoid_: test site, mock shop

**Injection**:
Page text that addresses the Agent or tries to override its instructions.
_Avoid_: jailbreak

**Persuasion**:
Pressure text with no bearing on the decision: countdowns, "N people viewing", "only N left".

## Checking

**Detector**:
A fast, pure check over a Snapshot and an Action that returns Findings (A1–A5, B5, C1).
_Avoid_: rule, scanner, guard

**Finding**:
One Detector's claim that something on the page is deceptive, with a Trap type, severity and human-readable evidence.
_Avoid_: alert, issue, flag

**Verdict**:
The decision on one Action: ALLOW, BLOCK, REROUTE or ASK, with the Findings behind it.
_Avoid_: result, ruling

**Reroute**:
Stop an Action and send the Agent the evidence plus a correction hint so it chooses again.
_Avoid_: redirect, retry

**Guard unavailable**:
A check that itself failed or timed out. Under fail-closed it blocks the Action rather than letting it through.

**Neutralization**:
Making an invisible element that covers the Agent's real target click-through, so the Agent's own click lands. It never applies to anything a person can see.
_Avoid_: auto-fix, unblocking

**Irreversible action**:
An Action that commits the user: pay, place order, subscribe, confirm, submit. Only these trigger the Audit.
_Avoid_: sensitive action, final action

## Authorization

**Ledger**:
What the user authorized, parsed from the task once before browsing and frozen for the Run. Page content can never change it.
_Avoid_: intent, permissions, policy, spec

**Audit**:
The pre-commit comparison of the observable Checkout state against the Ledger, one check per constraint.
_Avoid_: validation, review

**Checkout state**:
What a person could read at checkout: lines, fees, ticked options, total, recurring terms, data sharing, shipping.
_Avoid_: cart, order

**Permitted**:
A check status for an extra the Ledger explicitly allows. It is shown as allowed, not as a Trap.

**Uncertain**:
A check status when the page does not show enough to decide. It leads to ASK, never to ALLOW.

**Recheck**:
The Audit run again after the Agent's correction, to verify the fix landed.
_Avoid_: re-audit (fine in prose), revalidation

**Ask**:
A pause that needs a human Approve or Deny, with a stated reason: final payment, uncertain, retries exhausted, guard unavailable, cloaked checkout, untrusted shop.
_Avoid_: prompt, confirm dialog, escalation

**Demo approval**:
An Ask a Preset approves automatically. It is always labelled and never counts as human consent.
_Avoid_: auto-approve (as a user-facing word)

**Commitment**:
Something the user ends up bound to (item, add-on, subscription, fee, data sharing, download), in one of three states: proposed, approved or executed.
_Avoid_: purchase, charge

**Outcome**:
A Side's final result read from the visible confirmation: completion, total, Commitments, shop.
_Avoid_: result, receipt

## Disposable checks (experimental)

**Disposable copy**:
A fresh browser context that rebuilds the original checkout by replaying the executed Actions. Nothing in it touches the real session.
_Avoid_: clone, sandbox, fork

**Trial**:
R2: ordering once in each of two Disposable copies, with an ambiguous control ticked in one and unticked in the other, to observe what the control really does.
_Avoid_: probe, simulation, lookahead

**Branch**:
One of the two Disposable copies in a Trial.

**Two-view check**:
Loading the checkout in a Disposable copy that looks like an ordinary browser and comparing it with what the Agent saw, to catch Cloaking.

**Cloaking**:
A page that shows the Agent different Commitments than it shows an ordinary browser.

## Sybil

**Shop**:
One of the two simulated Arena shops (A or B) selling the same lamp; the Agent picks one.
_Avoid_: merchant, store, target

**Recommendation**:
A website saying "buy from this Shop". It is separate from a Link.
_Avoid_: endorsement, review, vote

**Link**:
A directed connection between two websites in the web graph. It does not imply endorsement.
_Avoid_: edge (in prose), hyperlink

**Background graph**:
The real website-link graph imported from Common Crawl, frozen per Dataset.
_Avoid_: real web, internet

**Dataset**:
One imported, versioned Background graph with its manifest, hashes and frozen normalization.

**Anchor**:
One of eight fixed trusted websites where trust starts flowing. Anchors are assumptions, not ground truth.
_Avoid_: seed (in UI copy), root, oracle

**Injected website**:
A simulated website a Scenario adds to the Background graph.
_Avoid_: fake site, sybil node, bot

**Compromise**:
A Scenario edit that takes over an existing real website's outgoing Links, at a Credit cost.
_Avoid_: hack, takeover (UI only)

**Bridge**:
A Link from a cooperating real website into Injected websites, bought with Credits.

**Credit**:
The unit of a Challenge's budget for edits that touch the Background graph.

**Scenario**:
A complete set of edits to a Dataset: Injected websites, Links, Recommendations, Compromises.
_Avoid_: attack (only some Scenarios attack), preset

**Revision**:
An immutable, content-hashed Scenario. Runs freeze one Revision, and any later edit makes a new one.
_Avoid_: version, draft (a draft is unsaved)

**Challenge**:
The bounded Scenario mode with a fixed budget and frozen settings. Research mode lifts the limits and is labelled.

**Assessment**:
The scores of both Shops for one Revision, plus convergence status.
_Avoid_: score (one number), evaluation

**Robustness (R)**:
The 0–100 score: structural support (S) weighted by anchor breadth (D), anchor withdrawal resilience (L) and tested connection resilience (E). It is a heuristic, not a probability of safety.
_Avoid_: trust score, safety score

**Graph evidence**:
The frozen Assessment summary and pass thresholds the Shielded side uses to judge a Shop.

**Graph policy**:
The thresholds a Shop must meet (R, S, L) before the Shielded side may enter it without an Ask.

## Evaluation

**Configuration (U / F / I / I-minus-audit / I+R2)**:
One arm of the evaluation: Unshielded, or a Shield configuration.
_Avoid_: mode, setting

**Safe completion**:
A Run Side that completes the task with no unauthorized Commitment.

**False block**:
A BLOCK or REROUTE on a Clean twin. An expected payment Ask is not a False block.
