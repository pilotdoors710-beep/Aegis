"use client";

import { useRunStream } from "@/lib/events";
import type { RunEvent } from "@/lib/api";

function describe(event: RunEvent): string {
  switch (event.kind) {
    case "snapshot": return event.payload.title;
    case "decision": return `${event.payload.cached ? "Replayed decision · " : ""}${event.payload.action.rationale}`;
    case "verdict": return `${event.payload.verdict.decision} · ${event.payload.verdict.findings?.map((finding) => finding.evidence).join(" ") || "Checks passed"}`;
    case "executed": return `${event.payload.ok ? "Executed" : "Execution failed"}: ${event.payload.action.type}`;
    case "ask": return `Sample approval: ${event.payload.status} · ${event.payload.reason.replaceAll("_", " ")}`;
    case "error": return event.payload.message;
    case "done": return `Finished: ${event.payload.reason}`;
  }
}

export function RunView({ runId }: { runId: string }) {
  const { summary, events, status, error } = useRunStream(runId);
  return <section className="run-section" aria-label="Run comparison">
    <div className="section-heading"><h2>Run comparison</h2><div>{summary?.is_sample && <strong className="badge">SAMPLE DATA</strong>} <span role="status">{status}</span></div></div>
    {error && <p className="error-message" role="alert">{error}</p>}
    {summary && <p className="run-task">{summary.task}</p>}
    <div className="comparison-grid">{(["unshielded", "shielded"] as const).map((mode) => {
      const side = events.filter((event) => event.mode === mode);
      const snapshot = side.findLast((event) => event.kind === "snapshot");
      const image = snapshot?.kind === "snapshot" ? snapshot.payload : null;
      const done = side.findLast((event) => event.kind === "done");
      return <article key={mode} className="agent-pane">
        <div className="pane-heading"><h3>{mode === "shielded" ? "With Aegis" : "Unprotected agent"}</h3><span>Step {side.at(-1)?.step ?? 0}</span></div>
        <div className="browser-frame">{image?.screenshot_b64 || image?.screenshot_url ?
          // eslint-disable-next-line @next/next/no-img-element
          <img alt={`${mode} ${summary?.is_sample ? "sample" : "browser"} screenshot`} src={image.screenshot_b64 ? `data:image/jpeg;base64,${image.screenshot_b64}` : image.screenshot_url!} /> : <span>Waiting for a browser snapshot</span>}</div>
        <ol className="event-feed" aria-label={`${mode} events`}>{side.map((event, index) => <li key={index}><span className={`event-kind kind-${event.kind}`}>{event.kind}</span><p>{describe(event)}</p></li>)}</ol>
        {done?.kind === "done" && <div className="sample-outcome"><strong>Sample outcome · {done.payload.outcome.total == null ? "Total unknown" : `₹${done.payload.outcome.total}`}</strong>{done.payload.outcome.commitments?.map((commitment, index) => <p key={index}>{commitment.description} · {commitment.state}</p>)}</div>}
      </article>;
    })}</div>
    <aside className="console-card ledger-panel"><h3>Permission ledger</h3>{summary?.ledger ? <><p>{summary.ledger.goal}</p><dl><div><dt>Budget</dt><dd>{summary.ledger.budget_max == null ? "Not specified" : `₹${summary.ledger.budget_max}`}</dd></div><div><dt>Add-ons</dt><dd>{summary.ledger.allow_addons ? "Permitted" : "Not permitted"}</dd></div><div><dt>Subscriptions</dt><dd>{summary.ledger.allow_subscriptions ? "Permitted" : "Not permitted"}</dd></div><div><dt>Shipping</dt><dd>{summary.ledger.shipping_method ?? "Not specified"}</dd></div></dl></> : <p>Waiting for the server’s interpretation of the task.</p>}</aside>
  </section>;
}
