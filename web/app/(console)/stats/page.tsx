"use client";

import { SkeletonGroup, Skeleton, SkeletonRows } from "@/components/skeleton";
import { useEffect, useState, type CSSProperties } from "react";
import { api, type Schema } from "@/lib/api";

type Config = Schema["ConfigStats"];

const NAMES: Record<Config["config"], string> = {
  U: "U · unprotected",
  F: "F · detectors + filtering",
  I: "I · full Aegis",
  "I-minus-audit": "I minus audit",
  "I+R2": "I + R2 trials",
};

// Count and denominator stay as text; the bar only repeats the same ratio. null = not applicable.
const ratio = (value: Schema["Count"] | null | undefined, none = "—") => value == null || value.of === 0
  ? <span className="event-meta">{value ? "0 / 0" : none}</span>
  : <span className="ratio">{value.count} / {value.of}<i style={{ "--r": value.count / value.of } as CSSProperties} /></span>;
const ms = (v: number | null | undefined, unit = "ms") => v == null ? "—" : `${v} ${unit}`;

function StatsTable({ rows, caption }: { rows: Config[]; caption: string }) {
  return <div className="table-scroll" role="region" aria-label={`${caption}, scroll for all metrics`} tabIndex={0}><table>
    <caption>{caption}</caption>
    <thead><tr><th>Configuration</th><th>Runs</th><th>Correct end</th><th>Held-out correct</th><th>Trap took effect</th><th>Unauthorized commitments</th><th>Task completed</th><th>Safe completion</th><th>Clean false blocks</th><th>Unnecessary asks</th><th>Authorized option rejected</th><th>Final approvals</th><th>Uncertainty asks</th><th>Denials</th><th>Fast detectors (median)</th><th>Shield step (median)</th><th>Audit step (median)</th><th>Run duration (median)</th></tr></thead>
    <tbody>{rows.map((c) => <tr key={c.config}>
      <th>{NAMES[c.config]}</th>
      <td>{c.runs}{c.infra_excluded ? <span className="event-meta"> (+{c.infra_excluded} infra)</span> : null}</td>
      <td>{ratio(c.correct_end)}</td><td>{ratio(c.held_out_correct)}</td>
      <td>{ratio(c.trap_success)}</td><td>{ratio(c.unauthorized_commitments)}</td>
      <td>{ratio(c.task_success)}</td><td>{ratio(c.safe_task_completion)}</td>
      <td>{ratio(c.clean_false_block, "no shield")}</td><td>{ratio(c.unnecessary_ask, "no shield")}</td><td>{ratio(c.authorized_option_rejection, "no shield")}</td>
      <td>{c.expected_final_approvals}</td><td>{c.uncertainty_escalations}</td><td>{c.denials}</td>
      <td>{ms(c.fast_detector_ms_median)}</td><td>{ms(c.shield_added_ms_median)}</td><td>{ms(c.audit_ms_median)}</td><td>{ms(c.run_duration_s_median, "s")}</td>
    </tr>)}</tbody>
  </table></div>;
}

export default function StatsPage() {
  const [stats, setStats] = useState<Schema["EvalStats"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api.stats(controller.signal).then(setStats).catch((error: Error) => {
      if (!controller.signal.aborted) setError(error.message);
    });
    return () => controller.abort();
  }, []);
  const label = stats?.label === "sample" ? "SAMPLE DATA" : stats?.label === "pilot" ? "PILOT · not a result" : "FINAL";
  const about = stats?.label === "sample" ? "Illustrative values only. These are not measured Aegis results."
    : stats?.label === "pilot" ? "Preliminary measurements; excluded from final claims."
    : `Exploratory${stats?.n === 1 ? " (one run per case)" : ""}, simulated arena shop only`;
  return <>
    <header className="page-head"><span className="label">Evaluation</span><h1>Measured outcomes</h1>
      <p className="lede">The same agent and model on the same arena cases, with and without protection. One row per configuration; every rate shows count / denominator. Provider failures are left out of the counts and kept in the raw files.</p></header>
    {error && <p role="alert" className="error-message">Could not load statistics: {error}</p>}
    {!stats && !error && <SkeletonGroup label="Loading evaluation data…"><Skeleton className="skeleton-line" /><SkeletonRows n={4} /></SkeletonGroup>}
    {stats && <>
      <div className="banner"><strong className="badge">{label}</strong><span>{about} · N={stats.n} · {stats.model ?? "Model not specified"} · Generated {new Date(stats.generated_at).toLocaleString()}{stats.source && <> · Raw rows: <code>{stats.source}</code></>}</span></div>
      <StatsTable rows={stats.configs} caption="Core comparison. Correct end = the case's expected outcome: an order with nothing unauthorized, or stopping safely. Held out = wording never used in development. Clean = clean or authorized cases." />
      {stats.r2_study.length > 0 && <>
        <h2 style={{ marginTop: "2.5rem" }}>Disposable consent trials (R2)</h2>
        <p className="lede">A separate study on ambiguous consent checkboxes, with its own cases. Never pooled with the table above. The audit step includes the trial time.</p>
        <StatsTable rows={stats.r2_study} caption="I vs I + R2 on the consent and cloaking cases" />
      </>}
      <p className="event-meta">Shield and audit times run from the agent&apos;s decision to the verdict. Page snapshot and LLM time are not included. Detector times round to whole milliseconds.</p>
    </>}
  </>;
}
