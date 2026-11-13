import type { RunEvent, Schema } from "@/lib/api";
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
