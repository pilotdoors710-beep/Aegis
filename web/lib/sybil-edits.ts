// Pure Challenge edits on a Sybil scenario: each takes the current edit set and returns the
// next one. The server re-validates every edit and owns the prices (revision.budget).
import type { Schema } from "./api";

type Edits = Schema["SybilScenarioCreate"];
type Revision = Schema["SybilScenarioRevision"];

const bridgeOf = (edits: Edits, site: string) => edits.cooperating_links.filter((l) => l.source === site);

function attackEntry(edits: Edits) {
  const target = edits.injected_nodes[0];
  if (!target) throw new Error("Create an attack with simulated websites first.");
  return target;
}

/** Bridge a real site into the attack, or remove its bridge and the link that bridge paid for. */
export function toggleBridge(edits: Edits, site: string): Edits {
  const paid = bridgeOf(edits, site);
  if (paid.length) {
    const targets = new Set(paid.map((l) => l.target));
    return {
      ...edits,
      cooperating_links: edits.cooperating_links.filter((l) => l.source !== site),
      added_links: edits.added_links.filter((l) => !(l.source === site && targets.has(l.target))),
    };
  }
  const bridge = { source: site, target: attackEntry(edits) };
  return { ...edits, cooperating_links: [...edits.cooperating_links, bridge], added_links: [...edits.added_links, bridge] };
}

/** Take over a real site (it links into the attack), or release it and every link it added. */
export function toggleTakeover(edits: Edits, site: string): Edits {
  // A taken-over site needs no cooperation credit, and the server rejects both at once.
  const cooperating_links = edits.cooperating_links.filter((l) => l.source !== site);
  if (edits.compromised.includes(site)) {
    return {
      ...edits,
      compromised: edits.compromised.filter((id) => id !== site),
      cooperating_links,
      added_links: edits.added_links.filter((l) => l.source !== site),
    };
  }
  const target = attackEntry(edits);
  const linked = edits.added_links.some((l) => l.source === site && l.target === target);
  return {
    ...edits,
    compromised: [...edits.compromised, site],
    cooperating_links,
    added_links: linked ? edits.added_links : [...edits.added_links, { source: site, target }],
  };
}

/** What the node inspector may offer for one real site, priced from the revision's budget. */
export function siteOptions(revision: Revision, site: string, anchor: boolean) {
  const { edits, budget } = revision;
  const bridged = bridgeOf(edits, site).length > 0;
  const compromised = edits.compromised.includes(site);
  const bridgeCost = budget.cooperating_link_cost;
  const takeoverCost = anchor ? budget.anchor_compromise_cost : budget.compromise_cost;
  const room = budget.credit_limit - budget.external_credits;
  return {
    bridged,
    compromised,
    bridgeCost,
    takeoverCost,
    canBridge: bridged || bridgeCost <= room,
    // A takeover replaces the site's bridge, so that bridge's cost comes back.
    canTakeOver: compromised || takeoverCost - (bridged ? bridgeCost : 0) <= room,
  };
}

export type SiteOptions = ReturnType<typeof siteOptions>;
