"use client";

import { SkeletonGroup, SkeletonCards } from "@/components/skeleton";
import { useEffect, useMemo, useState } from "react";
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
  const steps = useMemo(() => [...new Set(events.map((event) => event.step))].sort((a, b) => a - b), [events]);
  const step = steps[index];
  const visible = useMemo(() => step == null ? [] : events.filter((event) => event.step <= step), [events, step]);
  return <>
    <div className="replay-controls"><button disabled={index === 0 || !steps.length} onClick={() => setIndex(index - 1)}>Previous</button><label htmlFor="replay-step">Step {step ?? "—"}</label><input id="replay-step" aria-label="Replay step" type="range" min={0} max={Math.max(0, steps.length - 1)} value={index} disabled={!steps.length} onChange={(event) => setIndex(Number(event.target.value))} /><button disabled={index >= steps.length - 1} onClick={() => setIndex(index + 1)}>Next</button></div>
    {!loaded && !error && <SkeletonGroup label="Loading replay…"><SkeletonCards n={2} /></SkeletonGroup>}
    <RunComparison summary={summary} events={visible} replayStep={step} status={error ? "error" : loaded ? steps.length ? "Stored events" : "No stored events" : "Loading replay…"} error={error} replay />
  </>;
}

function Live({ runId, queue }: { runId: string; queue: number }) {
  return <><RunView runId={runId} queue={queue} /><Link className="secondary-button" href={`/runs/${encodeURIComponent(runId)}?replay=1`} aria-label="Open the stored replay of this run">Stored replay</Link></>;
}

export function RunSession({ runId, replay, queue }: { runId: string; replay: boolean; queue: number }) {
  return <><div className="run-head"><h1>{replay ? "Run replay" : "Live run"}{replay && <strong className="badge">REPLAY · Stored activity</strong>}</h1><Link className="secondary-button" href="/runs">History</Link></div>{replay ? <Replay runId={runId} /> : <Live runId={runId} queue={queue} />}</>;
}
