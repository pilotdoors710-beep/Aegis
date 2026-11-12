"use client";

import { useState } from "react";
import { useRunStream } from "@/lib/events";
import type { RunEvent, Schema } from "@/lib/api";
import { approvalLabels, latestAsks, pendingAsk } from "@/lib/run-evidence";
import { ApprovalDialog } from "./approval-dialog";
import { EvidenceCards } from "./evidence-cards";
import { OutcomeCards } from "./outcome-cards";

type VerdictEvent = Extract<RunEvent, { kind: "verdict" }>;

function describe(event: RunEvent): string {
  switch (event.kind) {
    case "snapshot": return event.payload.title;
    case "decision": return event.payload.action.rationale;
    case "verdict": return event.payload.verdict.decision;
    case "executed": return `${event.payload.ok ? "Executed" : "Execution failed"}: ${event.payload.action.type}`;
    case "ask": return `${approvalLabels[event.payload.status]} · ${event.payload.reason.replaceAll("_", " ")}`;
    case "error": return event.payload.message;
    case "done": return `Finished: ${event.payload.reason}`;
  }
}

function Ledger({ ledger }: { ledger: Schema["Ledger"] | null | undefined }) {
  return <aside className="ledger-panel" aria-label="Permission ledger"><h4>Permission ledger</h4>{ledger ? <><p>{ledger.goal}</p><dl>
    <div><dt>Items</dt><dd>{ledger.items?.map((item) => `${item.qty ?? 1} × ${item.name}`).join(", ") || "Not specified"}</dd></div>
    <div><dt>Budget</dt><dd>{ledger.budget_max == null ? "Not specified" : `₹${ledger.budget_max}`}</dd></div>
    <div><dt>Add-ons</dt><dd>{ledger.allow_addons ? "Permitted as requested" : "Not permitted"}</dd></div>
    <div><dt>Subscriptions</dt><dd>{ledger.allow_subscriptions ? "Permitted as requested" : "Not permitted"}</dd></div>
    <div><dt>Shipping</dt><dd>{ledger.shipping_method ?? "Not specified"}</dd></div>
    <div><dt>Data</dt><dd>{ledger.data_allowed?.join(", ") || "No sharing authorized"}</dd></div>
  </dl></> : <p role="status">Parsing your request…</p>}</aside>;
}

function AgentPane({ mode, events, summary }: { mode: RunEvent["mode"]; events: RunEvent[]; summary: Schema["RunSummary"] | null }) {
  const [selected, setSelected] = useState<VerdictEvent | null>(null);
  const side = events.filter((event) => event.mode === mode);
  const inspected = selected && side.includes(selected) ? selected : null;
  const snapshots = side.filter((event) => event.kind === "snapshot");
  const snapshot = inspected ? snapshots.findLast((event) => event.step === inspected.step) : snapshots.at(-1);
  const image = snapshot?.payload;
  // A verdict's coordinates apply only to its own snapshot, never to a later page.
  const verdict = inspected ?? side.findLast((event) => event.kind === "verdict" && event.step === snapshot?.step);
  const highlights = verdict?.kind === "verdict" ? verdict.payload.highlights ?? [] : [];
  return <article className="agent-pane">
    <div className="pane-heading"><h3>{mode === "shielded" ? "With Aegis" : "Unprotected agent"}</h3><span>Step {inspected?.step ?? side.at(-1)?.step ?? 0}</span></div>
    <div className="browser-frame">
      {image?.screenshot_b64 || image?.screenshot_url ? <>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt={`${mode} browser at step ${snapshot?.step}`} src={image.screenshot_url || `data:image/jpeg;base64,${image.screenshot_b64}`} />
        {mode === "shielded" && <svg className="highlight-layer" viewBox="0 0 1280 720" role="img" aria-label="Flagged page elements">{highlights.map((highlight) => {
          const [x, y, width, height] = highlight.bbox;
          return <g key={highlight.element_id}><rect x={x} y={y} width={width} height={height} /><text x={Math.max(2, Math.min(x, 1000))} y={Math.max(24, y - 8)}>{highlight.label}</text></g>;
        })}</svg>}
      </> : <span>Waiting for a browser snapshot</span>}
    </div>
    {mode === "shielded" && <Ledger ledger={summary?.ledger} />}
    {inspected && <button className="inspect-button" onClick={() => setSelected(null)}>Inspecting step {inspected.step} · Return to latest</button>}
    <ol className="event-feed" aria-label={`${mode} events`}>{side.filter((event) => mode === "shielded" || event.kind !== "verdict").map((event, index) => <li key={index}>
      <span className={`event-kind kind-${event.kind}`}>{event.kind}</span><div>
        {event.kind === "verdict" ? <button className="verdict-row" aria-pressed={inspected === event} onClick={() => setSelected(event)}>
          <strong>{event.payload.verdict.decision}</strong><span> · {event.payload.verdict.latency_ms} ms · Step {event.step}</span>
          {event.payload.verdict.findings?.map((finding, i) => <p key={i}><strong>{finding.detector} · {finding.trap_type}</strong><br />{finding.evidence}</p>)}
          {!event.payload.verdict.findings?.length && <p>Checks passed</p>}
          {event.payload.neutralized?.map((cover) => <p key={cover.element_id}><strong>Overlay neutralized</strong><br />{cover.evidence}</p>)}
          {event.payload.verdict.reroute_hint && <p>Next: {event.payload.verdict.reroute_hint}</p>}
        </button> : <p>{event.kind === "ask" && summary?.is_sample ? "Recorded sample · " : ""}{describe(event)}</p>}
        {event.kind === "decision" && <><span className="event-meta">{event.payload.provider} · {event.payload.model} · {event.payload.llm_latency_ms} ms</span>{event.payload.cached && <strong className="badge">Replayed decision</strong>}</>}
        {event.kind === "snapshot" && event.payload.removed?.map((removed, i) => <p key={i}>Removed ({removed.reason}): {removed.text}</p>)}
      </div>
    </li>)}</ol>
  </article>;
}

export function RunComparison({ summary, events, status, error, replay = false }: { summary: Schema["RunSummary"] | null; events: RunEvent[]; status: string; error?: string | null; replay?: boolean }) {
  return <section className="run-section" aria-label="Run comparison">
    <div className="section-heading"><h2>Run comparison</h2><div>{replay && <strong className="badge">REPLAY</strong>} {summary?.is_sample && <strong className="badge">SAMPLE DATA</strong>} <span role="status">{status}</span></div></div>
    {error && <p className="error-message" role="alert">{error}</p>}
    {summary && <p className="run-task">{summary.task}</p>}
    <OutcomeCards events={events} summary={summary} />
    <div className="comparison-grid">{(["unshielded", "shielded"] as const).map((mode) => <AgentPane key={mode} mode={mode} events={events} summary={summary} />)}</div>
    {latestAsks(events).length > 0 && <section className="approval-history" aria-label="Approval history"><h2>Approval history</h2>{latestAsks(events).map((ask) => <p key={ask.payload.ask_id}>{summary?.is_sample ? "Recorded sample · " : replay ? "Recorded response · " : ""}{approvalLabels[ask.payload.status]} · {ask.payload.reason.replaceAll("_", " ")}</p>)}</section>}
    <EvidenceCards events={events} />
  </section>;
}

export function RunView({ runId, queue = 0 }: { runId: string; queue?: number }) {
  const stream = useRunStream(runId);
  const ask = pendingAsk(stream.events);
  const canReview = stream.summary && (stream.summary.is_sample || (stream.summary.status !== "done" && stream.summary.status !== "error"));
  return <>{queue > 0 && !stream.events.length && stream.status !== "error" && <p role="status">Queued at launch: position {queue}. Waiting for this run to start.</p>}<RunComparison {...stream} />{ask && stream.summary && canReview && <ApprovalDialog key={ask.payload.ask_id} ask={ask} sample={stream.summary.is_sample} connected={stream.status === "streaming"} />}</>;
}
