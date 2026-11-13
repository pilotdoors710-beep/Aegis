"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, History } from "lucide-react";

import { api, type Schema } from "@/lib/api";

function permissionLabel(ledger: Schema["Ledger"] | null | undefined) {
  if (!ledger) return "Permission ledger unavailable";
  if (ledger.allow_addons && ledger.allow_subscriptions) return "Protection plan authorized";
  return "Protection plan not authorized";
}

function shieldedOutcome(run: Schema["RunSummary"]) {
  return run.outcomes.shielded;
}

function PairSummary({ run, label }: { run: Schema["RunSummary"]; label: string }) {
  const outcome = shieldedOutcome(run);
  return <article className="permission-pair-card">
    <span className="eyebrow">{label}</span>
    <h3>{permissionLabel(run.ledger)}</h3>
    <p>{run.task}</p>
    <dl>
      <div><dt>Add-ons</dt><dd>{run.ledger?.allow_addons ? "Permitted" : "Not permitted"}</dd></div>
      <div><dt>Subscriptions</dt><dd>{run.ledger?.allow_subscriptions ? "Permitted" : "Not permitted"}</dd></div>
      <div><dt>Shielded total</dt><dd>{outcome?.total == null ? "Not recorded" : `₹${outcome.total.toLocaleString("en-IN")}`}</dd></div>
      <div><dt>Executed</dt><dd>{outcome?.commitments.filter((item) => item.state === "executed").map((item) => item.description).join(", ") || "No executed commitments"}</dd></div>
    </dl>
  </article>;
}

export function PermissionPair({ summary, finished }: { summary: Schema["RunSummary"]; finished: boolean }) {
  const router = useRouter();
  const [presets, setPresets] = useState<Schema["Preset"][]>([]);
  const [runs, setRuns] = useState<Schema["RunSummary"][]>([]);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!finished || summary.is_sample) return;
    const controller = new AbortController();
    Promise.all([api.presets(controller.signal), api.runs(controller.signal)])
      .then(([nextPresets, nextRuns]) => { setPresets(nextPresets); setRuns(nextRuns); })
      .catch((cause: Error) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [finished, summary.is_sample]);

  const currentPreset = useMemo(
    () => presets.find((preset) => preset.id === summary.preset_id),
    [presets, summary.preset_id],
  );
  const pairPreset = currentPreset?.pair_of ? presets.find((preset) => preset.id === currentPreset.pair_of) : undefined;
  const storedPair = pairPreset
    ? runs.find((run) => run.preset_id === pairPreset.id && run.status === "done" && run.run_id !== summary.run_id)
    : undefined;

  if (!finished || summary.is_sample || (!currentPreset?.pair_of && !error)) return null;

  async function launchPair() {
    if (!pairPreset) return;
    setLaunching(true); setError(null);
    try {
      const created = await api.createRun({ preset_id: pairPreset.id });
      router.push(`/runs/${encodeURIComponent(created.run_id)}?queue=${created.status === "queued" ? created.queue_position : 0}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start the paired run.");
      setLaunching(false);
    }
  }

  return <section className="permission-pair-section" aria-labelledby="permission-pair-title">
    <div className="section-heading">
      <div><span className="eyebrow">FRESH PERMISSION LEDGER</span><h2 id="permission-pair-title">Change permission, then start a new run</h2></div>
      <span>The completed run is never edited.</span>
    </div>
    {pairPreset && <div className="permission-pair-actions">
      <button className="primary-button" disabled={launching} onClick={launchPair}>
        {launching ? "Starting fresh run…" : `Run again: ${pairPreset.title}`} <ArrowRight size={15} />
      </button>
      {storedPair && <Link className="secondary-button" href={`/runs/${encodeURIComponent(storedPair.run_id)}?replay=1`}><History size={15} /> Show last stored paired run</Link>}
    </div>}
    {error && <p className="error-message" role="alert">Paired run unavailable: {error}</p>}
    {storedPair && <div className="permission-pair-grid">
      <PairSummary run={summary} label="This run" />
      <PairSummary run={storedPair} label="Stored paired run · replay" />
    </div>}
  </section>;
}
