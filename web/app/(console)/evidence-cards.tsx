import type { RunEvent } from "@/lib/api";
import { auditEvidence } from "@/lib/run-evidence";

export function EvidenceCards({ events }: { events: RunEvent[] }) {
  const cards = auditEvidence(events).filter(({ check }) => check.status !== "ok");
  if (!cards.length) return null;
  return <section className="evidence-section" aria-label="Permission and checkout evidence"><h2>Permission → page evidence → decision</h2><div className="evidence-grid">{cards.map(({ key, event, check, correction, correctionExecuted, recheck, recheckStep }) => <article key={key} className={`evidence-card check-${check.status}`}>
    <div className="section-heading"><h3>{check.constraint.replaceAll("_", " ")}</h3><span>Step {event.step}</span></div>
    <p className="check-label">{check.status === "permitted" ? "Permitted by your request" : check.status === "uncertain" ? "Needs a human decision" : "Outside your request"}</p>
    <dl><div><dt>Your permission</dt><dd>{check.ledger_value}</dd></div><div><dt>Observed page evidence</dt><dd>{check.observed_value}<p>{check.evidence}</p></dd></div><div><dt>Decision</dt><dd>{event.payload.verdict.decision}</dd></div>
      {check.status !== "permitted" && <><div><dt>Agent correction</dt><dd>{correction ? `${correctionExecuted ? "Executed" : "Proposed"}: ${correction.payload.action.rationale}` : "No correction recorded yet"}</dd></div><div><dt>Recheck</dt><dd>{recheck ? `Step ${recheckStep}: ${recheck.status} — ${recheck.evidence}` : recheckStep != null ? `Step ${recheckStep}: this constraint was not included in the linked audit` : "No linked recheck recorded yet"}</dd></div></>}
    </dl>
  </article>)}</div></section>;
}
