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
    <header className="page-head"><h1>Run history</h1><p className="lede">Inspect stored decisions and page evidence, one step at a time.</p></header>
    {message && <p role="status">{message}</p>}
    <Link className="secondary-button" href="/runs/sample?replay=1">Sample replay</Link>
    {runs.length > 0 && <div className="table-scroll" role="region" aria-label="Stored runs" tabIndex={0}><table><thead><tr><th>Preset</th><th>Status</th><th>Task</th><th>Started</th><th>Labels</th></tr></thead><tbody>{runs.map((run) => <tr key={run.run_id}>
      <th>{run.status === "queued" || run.status === "running"
        ? <Link href={`/runs/${encodeURIComponent(run.run_id)}`} aria-label={`Watch ${run.preset_id} run live, started ${new Date(run.created_at).toLocaleString()}`}>{run.preset_id}</Link>
        : <Link href={`/runs/${encodeURIComponent(run.run_id)}?replay=1`} aria-label={`Replay ${run.preset_id} run from ${new Date(run.created_at).toLocaleString()}`}>{run.preset_id}</Link>}</th>
      <td>{run.status}</td><td className="wrap">{run.task}</td><td>{new Date(run.created_at).toLocaleString()}</td>
      <td>{run.is_sample && <strong className="badge">SAMPLE DATA</strong>}{run.own_key && <strong className="badge">Your key · {run.model}</strong>}</td>
    </tr>)}</tbody></table></div>}
  </>;
}
