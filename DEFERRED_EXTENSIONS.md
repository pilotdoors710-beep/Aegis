# Aegis: partner reference - deferred experiments and external websites

Saved: 12 November 2026, from the user's planning conversation with Codex.

> **FOR THE HUMAN PARTNER ONLY - NOT AN AGENT WORK PLAN.**
> This document records ideas for the partners to discuss. Agents must not use it to select tasks, implement features, change priorities, expand scope, or alter the active schedule, even after the core is complete. Do not treat the stages or checklists below as instructions or implementation authorization. Only a new explicit human instruction, reconciled with `project_brief.md` and the active development plan, can activate any of these ideas. Continue following the active brief and assigned work.

## Status and intent

This records the user's desired future direction for the human partners to discuss after the core is complete. It is a planning document, not a claim of implemented functionality or authorization to begin implementation now. Do not interrupt core work to build these extensions.

`project_brief.md` remains the source of truth. `DEV_PLAN.md` supplies the active schedule and research gates. This document does not change either file, expand their budgets, activate deferred scanning, authorize production purchases, or approve cross-owner implementation. Scope changes must be reconciled with the brief and coordinated with both developers before they are activated.

The user wants two complementary capabilities:

1. Review supported real websites before payment or another consequential commitment.
2. Investigate unclear checkout controls by executing alternatives in verified disposable environments, then recommend the smallest supported correction consistent with the user's permission.

The proposed two-control expansion belongs in an optional **Deep check** mode (working name: Pro checking). It is not a paid tier or a currently available feature.

The user corrected an earlier misunderstanding: more realistic T01/T03/T05/T06 trap variants are NOT the second extension requested here. Do not substitute trap-variant work for the experiment.

## Why extend beyond the arena?

The arena supplies reproducible attacks, clean twins, and independent evaluator ground truth. Arena success alone does not establish compatibility with other websites. The extensions should provide evidence that the defender interprets another application's ordinary page content and behavior without a programmed answer for each test.

A supported site adapter may navigate or extract an application's observable structure. Disclose it and evaluate it. Do not encode the correct control state using a trap ID, private application state, evaluator answer, or a test-specific checkbox name.

## Stage 1: finish and verify the core

Resume extension implementation only after documenting the relevant core gates, not merely counting completed coding tasks:

- The production frontend and backend run compatible current versions.
- Real protected and unprotected trajectories stream through the deployed console and produce honest final outcomes.
- Supported clean tasks complete; trap cases reach their specified completed or safe-abort outcomes. Aborts are not successful purchases.
- Detectors, required T01-T08 fixtures and clean twins, fixed permission ledger, checkout audit, agent correction, and recheck have the required tests.
- R1 accepts explicitly requested annual protection and rejects forbidden protection from the same initial checkout. Budget and shipping constraints remain active.
- Human approve, deny, timeout, and post-approval re-audit work through the production console. Samples, replays, cached decisions, and simulated approvals remain labelled.
- Evidence, outcome commitments, persistence/replay, generated types, and required checks work together.
- Demo reliability/readability and the paired-run timing target are verified; evaluation, feature freeze, rehearsal, and submission retain their time and quota.

Record actual failures and unresolved gates. Do not weaken the baseline or tune fixtures repeatedly against a chosen model to manufacture divergence.

## Stage 2: Standard check and one-control experiments

Standard check uses the normal detection and checkout audit. Where explicitly supported and enabled, it can additionally investigate one ambiguous binary control in an isolated environment: **two configurations, selected and cleared**.

Example user request: buy one Aurora desk lamp for under INR 1,500, with no extras or subscriptions and standard shipping.

### Execution sequence

1. Parse the request into a fixed permission ledger before browsing. Resolve ambiguous authorization through the existing human fallback; webpage text cannot change the ledger.
2. Observe the checkout and proposed sensitive action. Ordinary violations use the existing correction/recheck flow. Unsupported or uncertain facts are never treated as permission.
3. If a supported control's effect is unclear, pause the original session. Reproduce the checkout through deterministic setup or recorded supported actions in fresh disposable browser contexts.
4. Verify the relevant initial observations match: item/quantity, shipping, total, selected options, and other supported effect-relevant fields. New contexts or copied cookies alone are not a clone.
5. Exercise selected and cleared states in separate disposable copies. Reach a simulated/test confirmation in each, collecting observable commitments, totals, recurring terms, consent statements, and supporting screenshots.
6. Read ordinary visible evidence only. Do not read hidden trap identifiers, private JavaScript variables, ground-truth JSON, evaluator success flags, or a hardcoded control-to-effect mapping.
7. Compare outcomes against the fixed ledger using deterministic checks. Recommend a satisfying alternative only where the evidence supports it. If both satisfy the request, prefer preserving the original state rather than inventing a violation. If neither satisfies it or evidence is ambiguous, ask the human.
8. Close disposable resources on success, failure, timeout, or cancellation. Verify the original session was not changed by the trials.
9. Return evidence and a correction hint. The original agent performs any change through its ordinary executor; Aegis does not silently edit the checkout. Re-audit the original session and retain final human approval and its subsequent recheck.

Illustrative observations, not expected answers embedded in the defender:

| Trial | Visible confirmation | Meets the example request? |
| --- | --- | --- |
| Selected | Lamp plus annual protection, INR 1,598 | No |
| Cleared | Lamp only, INR 1,299, no recurring commitment | Yes |

### Engineering boundaries

- The trial module makes **zero additional LLM calls**. Browser automation, supported receipt extraction, constraint comparison, and bounded selection are ordinary code. The existing shopper and initial intent parsing may still use an LLM.
- Browser/network orchestration stays outside pure detectors, in the trial module specified by the brief.
- Preserve the active brief's one two-branch trial per audited state, sequential disposable contexts, configurable initial 10-second total timeout, and separately reported trial actions/latency.
- Restrict requests, navigation, popups, workers, downloads, and write destinations to the supported isolated environment. An origin allowlist alone does not make a real write endpoint disposable.
- Unsupported effects, reproduction mismatches, contradictory outcomes, or exhausted budgets produce unavailable/uncertain status and the existing human fallback.
- Trial execution never supplies authorization for the original session.

### UI and evidence

Use the existing protected pane to show "Testing disposable copies" and both observed outcomes. Do not add a third permanent browser pane.

Connect permission -> observed trial evidence -> recommendation -> agent correction -> recheck -> human approval -> executed original-session outcome.

Clearly distinguish trial screenshots/test confirmations from original-session activity. Store availability/failure reasons and separate timing/actions for replay. Do not label a model prediction as an executed trial.

## Stage 3: one supported public website, then possibly a second

Implement a narrowly defined workflow for one selected real merchant before expanding to a second. Site selection remains open; no website compatibility is claimed yet.

The public-site workflow:

1. Start with a user request and fixed ledger.
2. Navigate through explicitly supported steps and observe the checkout.
3. Extract supported items, quantities, totals, currency, shipping, selected extras, renewal terms, and consent evidence.
4. Explain mismatches and uncertainty, and guide only supported, authorized corrections.
5. Stop before payment, order placement, subscription activation, personal-data submission/sharing, or another consequential commitment.

Define supported domains, redirects, pages, observations, actions, and stop conditions before testing. A control that changes a cart/account may itself be a write; do not assume all pre-payment actions are harmless or automatically authorized. Unsupported login, CAPTCHA, currency, checkout structure, effects, or navigation should stop or use the stated fallback.

Dev A owns external URL/network validation and backend adapters. Preserve SSRF protection, public-destination checks, redirect validation, and bounded access; do not simply remove the arena-only guard. Dev B owns the compatibility/status/review UI. Coordinate schema changes and regenerate frontend types from OpenAPI.

Report exactly what was checked and which fields were unavailable. No universal "safe website" or "malicious website" verdict. A compliant visible checkout cannot prove an arbitrary merchant's hidden backend behavior.

**Full experimental checkouts on an unrelated live merchant are not enabled by this stage.** A public merchant can support them only through verified isolated staging, sandboxing, or a genuinely side-effect-free preview with a defined effect model.

## Stage 4: full experiments on an independent ecommerce platform

Target an isolated test deployment of a real ecommerce platform to investigate generalization beyond the homemade arena. Candidates to assess, not selected or provisioned:

- Shopify development store using the platform's supported test gateway. Requires appropriate account/developer access; dev stores are test environments rather than production merchants.
- WooCommerce staging deployment using test payments and controlled integrations.

A payment sandbox alone does not isolate orders, inventory, notifications, fulfillment, webhooks, or account state. Establish separate test carts/accounts or resettable backend state for branches; test that they do not interfere. Verify setup and cleanup, and use synthetic data with no live charges or production side effects.

Reuse the same experimental pipeline and checker. Disclose site-specific adapters. Validate controls available on that platform rather than assuming the arena's fixtures or subscription features exist there.

Label this honestly as an independent-platform **test deployment**, not a production-site purchase trial. Test behavior is evidence about the tested configuration; it does not prove identical production behavior.

The first practical extension target is **one supported public-site review plus one independent-platform experimental integration**. A second site/platform depends on the first succeeding and remaining time. These can continue after submission.

## Stage 5: optional Deep check (Pro checking)

Deep check is a deferred advanced mode selected before a fresh run. It retains the ordinary protections and immutable ledger, then investigates **two supported binary controls, up to four configurations** in verified disposable environments.

| A | B | Purpose |
| --- | --- | --- |
| Selected | Selected | Observe the joint effect |
| Selected | Cleared | Observe this alternative |
| Cleared | Selected | Observe this alternative |
| Cleared | Cleared | Observe this alternative |

This can reveal interactions a one-control experiment misses. Verify the final requested control states actually hold before each trial; account for automatic toggling, order dependence, or reject unsupported behavior instead of assuming four assignments describe every possible outcome.

Compare every supported observed outcome with the ledger. Among satisfying configurations, minimize a declared cost such as the number of control changes from the original state. "Smallest correction" means smallest within the tested state/action set, not globally optimal over all website workflows.

If multiple configurations satisfy permission, preserve correct choices and avoid unnecessary changes. If none does, or observations are inconsistent, ask the human. The original agent still makes corrections; original-session rechecks and final approval remain.

Before implementation, specify a separate strict total timeout, trial/action limit, unsupported-state policy, and latency budget. Show that Deep check takes longer and can return uncertainty. Selecting it does not authorize production experiments or bypass the Standard fallback.

Working mode names:

- **Standard check:** normal protection/audit plus optional supported one-control, two-outcome trials.
- **Deep check:** optional supported two-control, four-configuration experiments.

Neither mode is currently implemented by virtue of this document. No pricing or paid tier is planned here. Two controls/four branches exceed the current brief's R2 limit and require explicit coordinated scope/budget revision.

## Research and acceptance

Question: does measuring actual outcomes improve permission-correct choices and safe task completion over the same audit without trials, at an acceptable added latency and action cost?

- Keep model, prompt, ordinary action budget, retry policy, and approval policy matched. Disable decision caching in evaluation and keep experiments off in the core U/F/I comparison.
- Compare I with I+R2 on predeclared cases. Evaluate Deep check separately if later implemented.
- Include ordinary, reversed, misleading, and neutral wording; identical labels with different effects; different labels with identical effects; authorized/forbidden extras; both/neither alternatives acceptable; and held-out wording/effect combinations.
- Test both control meanings, original-session isolation, reproduction, cleanup, egress containment, timeout/cancellation, unsupported states, changed original state, and independent-platform branch interference.
- Report choice/effect accuracy, safe completion, unauthorized commitments, authorized-option rejection, human interventions, coverage/uncertainty, trial latency/actions, and all failures with counts/denominators.
- Preserve original pilot results and freeze extension fixtures/protocol before evaluation. Do not alter the agent or repeatedly tune against held-out results to force baseline failures.
- Keep evaluator-only truth separate. Disclose adapters, test environments, synthetic checks, sample/replay data, and limitations.
- A visible receipt remains untrusted evidence. A passing checker or recorded evidence artifact is not a proof of hidden merchant truth or universal safety.

## Ownership, budget, and partner discussion checklist

Dev A: trial orchestration, security boundaries, backend state handling, audit integration, persistence, evaluation, and deployment. Dev B: console evidence/mode/compatibility UI and arena fixtures; external platform setup is coordinated explicitly. No ownership handoff is implied.

The brief's existing four-hour R2 spike and conservative two-combined-developer-hour integration cap still govern. Reconcile DEV_PLAN Q12 and contract acknowledgments before integration. External-site review, independent-platform trials, and Deep check need separate agreed scope, time, quota, and release criteria. Finishing code early is not proof those resources exist. Do not displace required evaluation or rehearsal.

For the human partners to consider if they later choose to activate this proposal (not an agent task list):

1. Read the latest session notes, brief, development plan, and this document.
2. Verify actual deployed core gates and remaining submission capacity.
3. Reconfirm the next bounded stage with both developers; update the brief/active plan and contracts where necessary.
4. Start the single-control arena spike first. Record go/no-go and preserve a working core if it fails.
5. Assess the first public-site workflow and independent-platform test environment; select sites and verify access/isolation before promising compatibility.
6. Add the second website and Deep check only after earlier stages pass and capacity is explicitly allocated. Otherwise continue after submission.

## Research and platform references

References were discussed in the planning conversation. Recheck current documentation, publication versions, availability, terms, and licenses when implementation resumes. These references establish related work and constraints, not that Aegis is globally novel.

- [Veer: corrective trajectories and live verification](https://arxiv.org/abs/2609.34974).
- [AttriGuard: causal attribution through counterfactual agent tests](https://arxiv.org/abs/2603.10749).
- [ALEX: behavioral model learning for web applications](https://learnlib.de/alex/book/contents/user-manual/introduction/).
- [ConsentChk: systematic consent behavior testing](https://www.usenix.org/system/files/usenixsecurity25-tang.pdf).
- [Cordon: semantic transactions and mediated-effect limitations](https://arxiv.org/abs/2606.17573).
- [Playwright browser contexts](https://playwright.dev/docs/browser-contexts) and [authentication/shared backend state](https://playwright.dev/docs/auth).
- [Shopify development stores](https://shopify.dev/docs/apps/build/stores/development-stores).
- [WooCommerce testing orders](https://woocommerce.com/document/managing-orders/testing-orders/).

Possible future pitch, only after the corresponding stages work: "Aegis reviews supported real checkouts against your permission. In verified isolated environments, it can test confusing choices, show the observed consequences, and guide a correction before final approval."
