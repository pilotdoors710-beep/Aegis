"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Schema, type RunEvent } from "@/lib/api";
import { RunComparison, RunView } from "../../run-view";

function Replay({ runId }: { runId: string }) {
  const [summary, setSummary] = useState<Schema["RunSummary"] | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [index, setIndex] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.run(runId, controller.signal), api.events(runId, controller.signal)]).then(([run, rows]) => {
      setSummary(run); setEvents(rows); setLoaded(true);
    }).catch((error: Error) => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
  }, [runId]);
  const steps = [...new Set(events.map((event) => event.step))].sort((a, b) => a - b);
  const step = steps[index];
  const visible = step == null ? [] : events.filter((event) => event.step <= step);
  return <>
    <div className="replay-controls"><button disabled={index === 0 || !steps.length} onClick={() => setIndex(index - 1)}>Previous</button><label htmlFor="replay-step">Step {step ?? "—"}</label><input id="replay-step" aria-label="Replay step" type="range" min={0} max={Math.max(0, steps.length - 1)} value={index} disabled={!steps.length} onChange={(event) => setIndex(Number(event.target.value))} /><button disabled={index >= steps.length - 1} onClick={() => setIndex(index + 1)}>Next</button></div>
    <RunComparison key={index} summary={summary} events={visible} status={error ? "error" : loaded ? steps.length ? "Stored events" : "No stored events" : "Loading replay…"} error={error} replay />
  </>;
}

function Live({ runId, queue }: { runId: string; queue: number }) {
  return <><RunView runId={runId} queue={queue} /><Link href={`/runs/${encodeURIComponent(runId)}?replay=1`}>Open stored replay</Link></>;
}

export function RunSession({ runId, replay, queue }: { runId: string; replay: boolean; queue: number }) {
  return <><div className="section-heading"><h1>{replay ? "Run replay" : "Live run"}</h1><Link href="/runs">Run history</Link></div>{replay && <strong className="badge">REPLAY · Stored activity</strong>}{replay ? <Replay runId={runId} /> : <Live runId={runId} queue={queue} />}</>;
}
