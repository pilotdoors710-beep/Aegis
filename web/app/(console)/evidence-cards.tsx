import SpotlightCard from "@/components/reactbits/SpotlightCard";
import type { RunEvent, Schema } from "@/lib/api";
import { auditEvidence } from "@/lib/run-evidence";

export function EvidenceCards({ events }: { events: RunEvent[] }) {
  const cards = auditEvidence(events).filter(({ check }) => check.status !== "ok");
  if (!cards.length) return null;
  const label = (status: string) => status === "permitted" ? "Permitted by your request" : status === "uncertain" ? "Needs a human decision" : "Outside your request";
  return <section className="evidence-section" aria-label="Permission and checkout evidence"><div className="section-heading"><h2>From permission to verified result</h2><span>Each row is one constraint from the ledger</span></div>{cards.map(({ key, event, check, correction, correctionExecuted, recheck, recheckStep }) => <SpotlightCard key={key} spotlightColor="#d9541e" intensity={0.4} spotlightSize={420} grain={0} className={`evidence-card check-${check.status}`}>
    <div className="evidence-head"><h3>{check.constraint.replaceAll("_", " ")}</h3><strong className={`chip chip-check-${check.status}`}>{label(check.status)}</strong><span>Step {event.step}</span></div>
    <ol className="evidence-chain">
      <li><h4>Your permission</h4><p>{check.ledger_value}</p></li>
      <li><h4>Observed page evidence</h4><p>{check.observed_value}</p><p className="chain-note">{check.evidence}</p></li>
      <li><h4>Decision</h4><p><strong className={`chip chip-${event.payload.verdict.decision.toLowerCase()}`}>{event.payload.verdict.decision}</strong></p></li>
      {check.status !== "permitted" && <>
        <li><h4>Agent correction</h4><p>{correction ? `${correctionExecuted ? "Executed" : "Proposed"}: ${correction.payload.action.rationale}` : "No correction recorded yet"}</p></li>
        <li><h4>Recheck</h4><p>{recheck ? `Step ${recheckStep}: ${recheck.status} — ${recheck.evidence}` : recheckStep != null ? `Step ${recheckStep}: this constraint was not included in the linked audit` : "No linked recheck recorded yet"}</p></li>
      </>}
    </ol>
  </SpotlightCard>)}</section>;
}

/** Two-view check: what the site showed the agent beside a disposable ordinary-browser copy. */
export function TwoView({ report }: { report: Schema["TwoViewReport"] | null | undefined }) {
  if (report?.status !== "mismatch") return null;
  const views = [
    ["Agent view", "What this site showed the AI agent", report.agent_screenshot_b64],
    ["Ordinary-browser view", "Disposable copy · automation signals removed", report.ordinary_screenshot_b64],
  ] as const;
  return <section className="two-view" aria-label="Agent view compared with ordinary-browser view">
    <h4>This site shows an automated browser a different checkout</h4>
    <ul>{report.diffs?.map((diff) => <li key={diff}>{diff}</li>)}</ul>
    <div className="two-view-grid">{views.map(([title, note, shot]) => <figure key={title}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {shot && <img alt={`${title} of the checkout`} src={`data:image/jpeg;base64,${shot}`} />}
      <figcaption><strong>{title}</strong><span>{note}</span></figcaption>
    </figure>)}</div>
    <p className="two-view-note">Read-only check: nothing was ticked or ordered in the copy. It uses the same browser engine and network, so it is not proof of what a person sees.</p>
  </section>;
}
