# Aegis: website trust and manufactured-consensus discussion

Saved: 14 November 2026, from the user's side conversation with Codex.

> Discussion reference only. This is proposed work, not an implementation plan,
> implementation authorization, or evidence that the features exist. Do not use
> this document to start work, change priorities, switch tracks, or expand scope.
> `project_brief.md` remains authoritative. A future explicit human request and
> reconciliation with that brief are needed before implementation.

## The idea in simple words

Attackers can create many websites that recommend the same shop. An AI shopping
agent might mistake that apparent popularity for strong evidence.

The proposed extension would check how those websites connect to trusted sources
before the agent relies on their recommendations. It would supplement Aegis's
existing page defenses, permission checks, correction/recheck flow and human gate.

The user preferred choosing between websites over checking individual accounts.
They also wanted an understandable, interactive demonstration with substance
beyond a graph visualization or a manually programmed answer.

## Example and limits

Two simulated shops sell a desk lamp within the user's budget. Both can have the
same number of recommending websites. For one shop, recommendations connect to
several established communities. For the other, they mostly come from a tightly
connected group with few connections to the trusted region.

The proposed engine measures structural support. It does not conclude that many
websites are suspicious, that a small community is fake, or that a well-connected
shop is safe. A legitimate newcomer can have little structural support. A link
can also be criticism or ordinary navigation rather than an endorsement.

A low score should support an "insufficient evidence" response: investigate,
consider alternatives, or ask the user. It must not automatically imply fraud.

The graph result must actually reach the agent and affect its decision process.
A separate animation turning a cluster red would not establish added protection.

## Suggested first algorithm

For directed website links, the suggested starting point was **Personalized
PageRank with a declared trusted seed set**, following a TrustRank-style approach.
SybilRank was discussed as an account/social-network baseline; it should not be
silently treated as the same algorithm or graph model.

Simple explanation:

1. Choose a small set of trusted starting websites.
2. Pass limited trust through outgoing links, dividing it across destinations.
3. Repeatedly return some probability mass to the trusted starting set.
4. Rank websites by the support reaching them.

The starting set is explicitly curated. Other scores are calculated from graph
structure, not manually assigned based on whether a website belongs to a test
attack. This is not an invented algorithm or a guarantee of Sybil resistance.
Attack connections, compromised seeds and ranking parameters can affect results.

A possible later explanation tool would examine graph bottlenecks or bounded
flows. It could show the effect of removing a connection in a disposable graph
copy. Any flow bound applies to the declared graph and capacity assumptions; it
does not prove identity, ownership, independence of opinions or merchant safety.

## Where the graph would come from

Aegis cannot recover a website's recommendation network from a screenshot alone.
The first demonstration would use a controlled test environment with explicit
website IDs, links and recommendation-to-shop mappings. Hundreds of graph nodes
do not require registering hundreds of real domains.

A real deployment would require an appropriate crawl, link-data provider or
platform registry, with known coverage and freshness. Reliable inbound-link data
is a separate challenge. Self-declared ownership or recommendation metadata must
not be treated as verified provenance.

The structural scoring engine would receive IDs, edges and trusted seeds only.
It would not use review wording, embeddings, KYC, biometrics or LLM judgments.
Evaluator labels identifying injected attack nodes stay separate from the engine.
The downstream browser agent can still read page content; these are different
components with different roles.

Graph-only processing is not cryptographic zero knowledge. Pseudonymous graph
structure can still reveal information through linkage. Privacy claims need to
describe what is actually collected, processed and exposed.

## Proposed judge experience: Attack Playground

The judge would use controls inside Aegis, rather than build actual websites:

1. Select Shop B as the shop they want the agent to choose.
2. Create 10, 100 or 1,000 simulated recommending websites with a slider.
3. Choose a connection pattern: a dense group, several groups or a hub network.
4. Make the generated websites recommend Shop B.
5. Use a limited attack budget to simulate external connections. Separately,
   optionally simulate compromising a trusted source.
6. Run the same shopping task with and without the graph assessment.
7. Inspect the scores, agent choices, uncertainty and final outcomes.
8. Change the attack and try again.

An attacker can freely edit its own simulated websites. Creating a link from an
established website requires an explicit compromise/cooperation assumption and
budget; it cannot be granted as an unexplained real-world capability.

The unprotected agent is not scripted to fail. Some attacks may influence neither
agent. Some attacks may defeat the proposed defense. All such outcomes count.

## Additional ideas discussed

- **Connection explanation:** select an influential connection and recompute the
  score with and without it in a graph copy. Explain score sensitivity, not what
  is happening inside the model's brain.
- **Automated attack search:** search different allowed graph edits within a
  fixed budget. Report the strongest attack found, not the strongest possible
  attack or a globally minimal attack unless that is actually established.
- **Trusted-source compromise test:** simulate one compromised seed/source and
  check how dependent the result is on it. High dependence could trigger a request
  for more evidence instead of an unsupported confident choice.

These are optional proposals. The smallest useful experiment is two shops, a
recommendation graph, an actual structural score and a downstream agent decision.

## How to avoid a hardcoded demonstration

- Compare legitimate and injected groups with the same number of websites.
- Use varied, held-out network arrangements and multiple graph-generation seeds.
- Keep attack labels, node naming hints and evaluator truth out of scoring inputs.
- Test newcomers, legitimate peripheral communities, extra attack edges and seed
  compromise; include failures and uncertainty.
- Compare simple link counting with the structural algorithm.
- Compare the base agent, current Aegis, topology-only assistance and the combined
  system while holding model configuration and initial task/state fixed.
- Measure manipulated seller choice separately from unauthorized commitments.
  Selecting a suspiciously supported seller is not automatically a ledger breach.
- Report task completion, unnecessary refusal/escalation, latency and resource
  cost alongside attack success. Show whether current Aegis already solves a case.
- A real background graph with injected attacks is a semi-synthetic benchmark.
  Do not claim its background nodes are verified honest without suitable labels.

## Pitch and track discussion

Possible pitch wording, usable as a capability claim only after implementation
and testing:

> Anyone can manufacture popularity by creating more websites. Aegis checks the
> connections behind that popularity before an AI agent relies on it.

Possible interactive challenge:

> Build a fake crowd. Try to influence our agent. Inspect the evidence it uses
> before it acts.

The broader proposed story connects three questions: what evidence influences the
agent, whether the page is deceptive, and whether the final commitment matches the
user's permission. Its value depends on improved behavior, not implementation
effort, visual complexity or a claim that PageRank is new.

The recommendation was to retain the working permission-sensitive demonstration
as the centrepiece unless this extension produces a clearer, stronger measured
demonstration. Until then it is a proposed extension, not a shipped capability.

The user supplied Track 04, "SYBIL: Topological Trust Engine," as inspiration. That
track calls for graph-only scoring, structural trust propagation, bottleneck
detection and a benchmark/interactive interface. A standalone topology engine
could address that brief, with Aegis as a downstream application. Existing Aegis
content-processing defenses are not themselves graph-only detection.

The active project brief still selects Track 03. No track switch or combined-entry
eligibility was established in this discussion. Any switch needs explicit review
of the active brief and applicable organizer rules.

## Earlier idea: occlusion saliency

The conversation began with masking suspicious webpage elements and asking the
agent what it would do instead. This remains a separate possible experiment.

It must alter the actual agent observation: for a DOM-text agent, blurring a
screenshot it never receives changes nothing. Repeated unchanged-input trials,
masked-input trials and harmless-mask controls are needed to distinguish input
influence from model variability. Existing sanitization may already remove the
suspect text; history can also retain it.

An action change is evidence of sensitivity under the tested intervention, not
proof of malicious intent or an X-ray of the model's reasoning. No change does not
clear an element. A "94% causal impact" label has no basis without a defined,
measured statistic. Extra model calls consume quota and add latency. None of this
replaces permission checks or human approval.

## Research precedents and actual products

The user explicitly distinguished research papers from working products. Both
exist in related areas, but an exact matching end-to-end Aegis product was not
verified in the discussion. Absence of a verified match is not proof of novelty.

### Research

- [TrustRank (2004)](https://snap.stanford.edu/class/cs224w-readings/gyongyi04trustrank.pdf):
  trusted seed pages and link-based propagation for web-spam assessment.
- [SybilRank (2012)](https://www.usenix.org/system/files/conference/nsdi12/nsdi12-final42_2.pdf):
  social-graph trust propagation and degree-normalized account ranking.
- [Anduin (2026)](https://arxiv.org/abs/2611.05586): graph-flow reputation for
  agentic marketplaces using buyer/provider payment relationships.
- [Epistemic Sybil Resistance (2026)](https://arxiv.org/abs/2609.01873): distinguishes
  multiplying reports from adding independent evidence.
- [Analysis of social-network Sybil defenses](https://www.khoury.northeastern.edu/home/amislove/publications/Sybil-SIGCOMM.pdf):
  community structure and limitations of topology-based defenses.
- [De-anonymizing Social Networks](https://arxiv.org/abs/0903.3276): privacy risks
  from topology even when direct identifying fields are removed.
- [RISE](https://arxiv.org/abs/1806.07421): established masking-based black-box
  explanation research relevant to the earlier saliency idea.

### Working products with related capabilities

- [Majestic Trust Flow](https://majestic.com/trust-flow) and its
  [glossary](https://majestic.com/help/glossary): website backlink-quality metrics
  using trusted seeds. An SEO/link-analysis product, not a merchant-safety guarantee.
- [BrightID](https://www.brightid.org/about): a social-connection identity network
  with an app intended to help applications assess unique participation.
- [Trusta TrustScan](https://trusta-labs.gitbook.io/trustalabs/trustscan/introduction-to-sybil-score-and-media-score):
  wallet Sybil scoring using transfer graphs and on-chain behavior; not strictly
  topology-only.

The potential Aegis contribution would be an evaluated integration from structural
evidence to agent behavior and controlled action execution. Do not claim to have
invented graph trust, website reputation, Sybil detection or graph explanations.

## Open decisions for a future discussion

- Whether this extension is worth the remaining time and quota.
- Whether Track 03 remains the target or a Track 04 entry is being considered.
- What the graph's links mean and where reliable data would come from.
- How structural evidence reaches the agent and what uncertainty changes in the UX.
- Which attack budgets, trusted-seed assumptions and evaluation cases are fixed.
- Which optional playground features are feasible after the smallest end-to-end
  example demonstrates value.

Saving this context does not resolve or authorize these decisions.
