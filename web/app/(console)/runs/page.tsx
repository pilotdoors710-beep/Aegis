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
    <div className="run-list">{runs.map((run) => <Link key={run.run_id} href={`/runs/${encodeURIComponent(run.run_id)}?replay=1`}><strong>{run.preset_id} · {run.status}</strong><p>{run.task}</p><small>{new Date(run.created_at).toLocaleString()} · Replay{run.is_sample ? " · SAMPLE DATA" : ""}</small></Link>)}</div>
    <Link className="primary-button" href="/runs/sample?replay=1">Open sample replay</Link>
  </>;
}
