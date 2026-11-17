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

const of = (c: Schema["Count"] | null | undefined) => c ? `${c.count} of ${c.of}` : "—";

// Plain-language reading of the tables. Numbers come from the data; the wording only claims what
// the declared protocol and eval/README.md support (N=1, arena only).
function Summary({ stats }: { stats: Schema["EvalStats"] }) {
  const get = (rows: Config[], name: Config["config"]) => rows.find((c) => c.config === name);
  const [u, f, i, noAudit] = (["U", "F", "I", "I-minus-audit"] as const).map((n) => get(stats.configs, n));
  const [r2Off, r2On] = (["I", "I+R2"] as const).map((n) => get(stats.r2_study, n));
  if (!u || !i) return null;
  const points: [string, React.ReactNode][] = [
    ["Traps", <>Without protection the agent fell for <b>{of(u.trap_success)}</b> traps. With full Aegis it fell for <b>{of(i.trap_success)}</b>. The one it still misses is a checkout that shows the AI a different summary than a person sees (T11), a limit we declared before the run.</>],
    ["Right outcome", <>The run ended the way the user would want (the right order, or a safe stop) in <b>{of(u.correct_end)}</b> runs without protection, <b>{of(f?.correct_end)}</b> with detectors only, and <b>{of(i.correct_end)}</b> with full Aegis.</>],
    ["Why the final check matters", <>Detectors alone still let traps through in <b>{of(f?.trap_success)}</b> cases, and full Aegis without its final check in <b>{of(noAudit?.trap_success)}</b>. Hidden fees and pre-ticked extras are caught by comparing the checkout against what the user asked for before paying.</>],
    ["New wording", <>On pages worded differently from anything used while building Aegis, full Aegis ended correctly in <b>{of(i.held_out_correct)}</b> runs (unprotected: {of(u.held_out_correct)}).</>],
    ["False alarms", <>On clean pages and on extras the user did allow, Aegis blocked or rerouted the agent in <b>{of(i.clean_false_block)}</b> runs. When the user allowed the protection plan, it was bought.</>],
    ["Speed", <>The checks add about <b>{ms(i.shield_added_ms_median)}</b> per step (not counting the AI model or page capture). A whole run took a median <b>{ms(i.run_duration_s_median, "s")}</b> with Aegis and {ms(u.run_duration_s_median, "s")} without.</>],
  ];
  if (r2Off && r2On) points.push(["Confusing checkboxes (R2)", <>On deliberately confusing consent boxes, full Aegis stayed safe but kept stopping to ask, so it ended correctly in only <b>{of(r2Off.correct_end)}</b>. Trying both choices in throwaway copies (R2) got <b>{of(r2On.correct_end)}</b> right, at about 2 seconds per trial.</>]);
  return <section className="stats-summary" aria-labelledby="summary-title">
    <h2 id="summary-title">What the numbers show</h2>
    <ul>{points.map(([title, body]) => <li key={title}><strong>{title}</strong><p>{body}</p></li>)}</ul>
    <p className="event-meta">How far to trust this: one run per case, a simulated shop, one free AI model. Some runs also failed because the model gave up early on a page it could read; those runs are kept in the counts. Treat this as early evidence, not proof.</p>
  </section>;
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
  const label = stats?.label === "pilot" ? "PILOT · not a result" : "FINAL";
  const about = stats?.label === "pilot" ? "Preliminary measurements; excluded from final claims."
    : `Exploratory${stats?.n === 1 ? " (one run per case)" : ""}, simulated arena shop only`;
  return <>
    <header className="page-head"><span className="label">Evaluation</span><h1>Measured outcomes</h1>
      <p className="lede">The same agent and model on the same arena cases, with and without protection. One row per configuration; every rate shows count / denominator. Provider failures are left out of the counts and kept in the raw files.</p></header>
    {error && <p role="alert" className="error-message">Could not load statistics: {error}</p>}
    {!stats && !error && <SkeletonGroup label="Loading evaluation data…"><Skeleton className="skeleton-line" /><SkeletonRows n={4} /></SkeletonGroup>}
    {stats && <>
      <div className="banner"><strong className="badge">{label}</strong><span>{about} · N={stats.n} · {stats.model ?? "Model not specified"} · Generated {new Date(stats.generated_at).toLocaleString()}{stats.source && <> · Raw rows: <code>{stats.source}</code></>}</span></div>
      {stats.label === "final" && <Summary stats={stats} />}
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
