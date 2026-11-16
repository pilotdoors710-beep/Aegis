"use client";

import { SkeletonGroup, Skeleton, SkeletonCards } from "@/components/skeleton";
import { useState } from "react";
import { api, type Schema } from "@/lib/api";

type Lab = Schema["LabRequest"];
type Report = Schema["TrialReport"];
type Branch = Schema["TrialBranch"];

const EXAMPLES = [
  ["Double negative", "Uncheck to not stop receiving partner offers"],
  ["Recommended", "Keep my lamp protected (recommended)"],
  ["Don't skip", "Don't skip the care plan"],
] as const;
const money = (value?: number | null) => value == null ? "unknown" : `₹${value.toLocaleString("en-IN")}`;
const plain = (key: string) => key.replace(/^[a-z_]+:/, "");

function headline(report: Report) {
  switch (report.status) {
    case "resolved": return `Leave the box ${report.recommended_checked ? "ticked" : "unticked"}`;
    case "both_ok": return "Either setting is fine";
    case "uncertain": return "Aegis would ask you";
    default: return "Trial unavailable: Aegis would ask you";
  }
}

function Receipt({ branch }: { branch: Branch }) {
  const box = branch.control_checked ? "Box ticked" : "Box unticked";
  return <article className="pane">
    <div className="pane-heading"><h3>{box}</h3><span>{branch.disposable_actions} actions</span></div>
    <div className="browser-frame">{branch.screenshot_b64
      // eslint-disable-next-line @next/next/no-img-element
      ? <img src={`data:image/jpeg;base64,${branch.screenshot_b64}`} alt={`Disposable copy confirmation, ${box.toLowerCase()}`} />
      : "No screenshot"}</div>
    <div className="lab-receipt">
      <span className="badge">DISPOSABLE COPY · SIMULATED ORDER</span>
      {branch.outcome && <ul>{branch.outcome.commitments.map((c, i) => <li key={i}>{c.description}</li>)}<li>Total {money(branch.outcome.total)}</li></ul>}
      {branch.error && <p className="bad">{branch.error}</p>}
      {!branch.error && (branch.unauthorized.length
        ? branch.unauthorized.map((v, i) => <p key={i} className="bad">✕ Not allowed: {plain(v)}</p>)
        : <p className="ok">Matches the user&apos;s permission</p>)}
    </div>
  </article>;
}

export default function LabPage() {
  const [form, setForm] = useState<Lab>({ label: EXAMPLES[0][1], effect: "share", ticked_means_on: false, starts_ticked: true, permit_plan: false, permit_sharing: false });
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<Lab>) => setForm((f) => ({ ...f, ...patch }));

  const test = async () => {
    setBusy(true); setError(null); setReport(null);
    try { setReport(await api.labTrial(form)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const actions = report?.branches.reduce((n, b) => n + b.disposable_actions, 0) ?? 0;

  return <>
    <header className="page-head"><span className="label">Experimental · disposable trials</span><h1>Write a tricky checkbox and see what Aegis makes of it</h1>
      <p className="lede">Write any checkbox label and secretly choose what it really does. Aegis never sees your choice. It places a simulated order in two throwaway copies of the checkout, one with the box each way, and compares both receipts with the user&apos;s permission. No AI model is involved in the trial.</p>
      <ul className="facts"><li>Experimental</li><li>Disposable consent trials</li><li>Arena only</li><li>No AI model</li></ul></header>

    <form className="lab-form" onSubmit={(e) => { e.preventDefault(); void test(); }}>
      <div className="lab-column">
        <h2 className="label"><label htmlFor="lab-label">1 · Label</label></h2>
        <input id="lab-label" type="text" maxLength={160} required value={form.label} onChange={(e) => set({ label: e.target.value })} />
        <p className="muted">The text shown next to the checkbox on the checkout.</p>
        <div className="chip-row">{EXAMPLES.map(([name, text]) => <button type="button" className="text-button" key={name} title={text} aria-label={`Use example: ${text}`} onClick={() => set({ label: text })}>{name}</button>)}</div>
      </div>
      <fieldset className="lab-column">
        <legend className="label">2 · Secret effect</legend>
        <p className="muted">Hidden from Aegis.</p>
        <select aria-label="Real effect" value={form.effect} onChange={(e) => set({ effect: e.target.value as Lab["effect"] })}>
          <option value="plan">Adds a ₹299/yr auto-renewing care plan</option>
          <option value="share">Shares the user&apos;s email with partners</option>
          <option value="none">Nothing at all</option>
        </select>
        <select aria-label="Ticking the box" value={String(form.ticked_means_on)} onChange={(e) => set({ ticked_means_on: e.target.value === "true" })}>
          <option value="true">Ticking turns it on</option>
          <option value="false">Ticking turns it off</option>
        </select>
        <label className="check"><input type="checkbox" checked={!!form.starts_ticked} onChange={(e) => set({ starts_ticked: e.target.checked })} /> Box starts ticked</label>
      </fieldset>
      <fieldset className="lab-column">
        <legend className="label">3 · Permission</legend>
        <p className="muted">One Aurora desk lamp under ₹2,000.</p>
        <label className="check"><input type="checkbox" checked={!!form.permit_plan} onChange={(e) => set({ permit_plan: e.target.checked })} /> Allow a care plan subscription</label>
        <label className="check"><input type="checkbox" checked={!!form.permit_sharing} onChange={(e) => set({ permit_sharing: e.target.checked })} /> Allow sharing my email</label>
        <button className="primary-button" type="submit" disabled={busy} aria-label="Test both checkbox states in disposable copies">{busy ? "Testing…" : "Test"}</button>
      </fieldset>
    </form>

    {error && <p role="alert" className="error-message">Trial failed: {error}</p>}
    {busy && <SkeletonGroup label="Testing both states in disposable copies…"><Skeleton className="skeleton-line is-title" /><SkeletonCards n={2} /></SkeletonGroup>}
    {report && !busy && <section className="result" aria-live="polite">
      <div className={`verdict ${report.status === "resolved" || report.status === "both_ok" ? "good" : ""}`}>
        <h2>{headline(report)}</h2>
        <p>{report.reason.replace(/\b[a-z_]+:/g, "")}</p>
        {report.control_label && <p className="muted">Label tested: “{report.control_label}”</p>}
        <ul className="facts"><li>{actions} disposable actions</li><li>{report.elapsed_ms} ms</li><li>No LLM calls</li>{report.original_unchanged && <li>Original checkout unchanged</li>}</ul>
      </div>
      <div className="comparison-grid">{report.branches.map((b) => <Receipt key={String(b.control_checked)} branch={b} />)}</div>
    </section>}
  </>;
}
