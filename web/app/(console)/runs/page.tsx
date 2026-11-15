"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type Schema } from "@/lib/api";

export default function RunsPage() {
  const [runs, setRuns] = useState<Schema["RunSummary"][]>([]);
  const [message, setMessage] = useState("Loading run history…");
  useEffect(() => {
    const controller = new AbortController();
    api.runs(controller.signal).then((rows) => { setRuns(rows); setMessage(rows.length ? "" : "No stored runs yet."); }).catch((error: Error) => {
      if (!controller.signal.aborted) setMessage(error instanceof ApiError && error.status === 501 ? "Stored run history is awaiting backend persistence. The sample replay is available below." : `Could not load history: ${error.message}`);
    });
    return () => controller.abort();
  }, []);
  return <>
    <header className="page-head"><span className="label">Audit trail</span><h1>Run history</h1><p className="lede">Inspect stored decisions and page evidence, one step at a time.</p></header>
    {message && <p role="status">{message}</p>}
    <Link className="secondary-button" href="/runs/sample?replay=1">Sample replay</Link>
    {runs.length > 0 && <div className="table-scroll runs-table" role="region" aria-label="Stored runs" tabIndex={0}><table><thead><tr><th>Run</th><th>Unprotected agent</th><th>With Aegis</th><th>Status</th><th>Started</th></tr></thead><tbody>{runs.map((run) => {
      const live = run.status === "queued" || run.status === "running";
      const started = new Date(run.created_at).toLocaleString();
      return <tr key={run.run_id}>
        <th><div className="run-name"><Link href={`/runs/${encodeURIComponent(run.run_id)}${live ? "" : "?replay=1"}`} aria-label={`${live ? "Watch" : "Replay"} ${run.preset_id} run, started ${started}`}>{run.preset_id}</Link>
          <span className="run-task">{run.task}</span>
          {(run.is_sample || run.own_key) && <span>{run.is_sample && <strong className="badge">SAMPLE DATA</strong>}{run.own_key && <strong className="badge">Your key · {run.model}</strong>}</span>}</div></th>
        <td><OutcomeCell outcome={run.outcomes.unshielded} ledger={run.ledger} /></td>
        <td><OutcomeCell outcome={run.outcomes.shielded} ledger={run.ledger} /></td>
        <td><span className={`run-status is-${run.status}`}>{run.status}</span></td>
        <td className="run-time">{started}</td>
      </tr>;
    })}</tbody></table></div>}
  </>;
}

function OutcomeCell({ outcome, ledger }: { outcome?: Schema["Outcome"] | null; ledger?: Schema["Ledger"] | null }) {
  if (!outcome) return <span className="run-muted">—</span>;
  const extras = outcome.commitments.filter((c) => c.state === "executed" && c.kind !== "item");
  return <span className="run-outcome">
    {outcome.total != null ? <strong>₹{outcome.total.toLocaleString("en-IN")}</strong> : <span className="run-muted">{outcome.task_completed ? "Completed" : "Nothing bought"}</span>}
    {extras.map((c, i) => <span key={i} className={permitted(c, ledger) ? "run-allowed" : "run-extra"}>+ {c.description}{permitted(c, ledger) && " (permitted)"}</span>)}
  </span>;
}

// Authorized extras are shown as permitted, not as violations (brief §8).
const permitted = (c: Schema["Commitment"], ledger?: Schema["Ledger"] | null) =>
  !!ledger && ((c.kind === "subscription" && ledger.allow_subscriptions) || (c.kind === "addon" && ledger.allow_addons));
