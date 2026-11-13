"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Play, ShieldCheck } from "lucide-react";
import { api, type Schema } from "@/lib/api";
import { RunView } from "../run-view";
import { consumeConsoleEntry } from "@/lib/landing/phases";

export default function ConsolePage() {
  const router = useRouter();
  const [launching, setLaunching] = useState<string | null>(null);
  async function launch(id: string) {
    setLaunching(id); setError(null);
    try {
      const run = await api.createRun({ preset_id: id });
      router.push(`/runs/${encodeURIComponent(run.run_id)}?queue=${run.status === "queued" ? run.queue_position : 0}`);
    } catch (error) { setError(error instanceof Error ? error.message : "Could not start the run."); setLaunching(null); }
  }
  const [presets, setPresets] = useState<Schema["Preset"][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState(0);
  useEffect(() => {
    if (consumeConsoleEntry()) {
      document.getElementById("console-heading")?.focus({ preventScroll: true });
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    api.presets(controller.signal).then(setPresets).catch((error: Error) => {
      if (!controller.signal.aborted) setError(error.message);
    });
    return () => controller.abort();
  }, []);
  return <>
    <div className="console-intro"><div><p className="eyebrow">Runtime security for browser agents</p><h1 id="console-heading" tabIndex={-1}>Check before committing.</h1><p>Compare the same browser agent with and without Aegis.</p></div><ShieldCheck className="intro-shield" size={48} /></div>
    <section className="sample-banner"><div><strong className="badge">SAMPLE DATA</strong><span>Prepared comparison for exploring the console. Use a preset below to request a live run.</span></div><button className="primary-button" onClick={() => setSession((value) => value + 1)}><Play size={14} />{session ? "Restart sample" : "Play sample run"}</button></section>
    {session > 0 && <RunView key={session} runId="sample" />}
    <section className="preset-section"><div className="section-heading"><h2>Demo presets</h2><span>Tasks fixed before each run</span></div>
      {error && <p role="alert" className="error-message">{error}</p>}
      {!presets.length && !error && <div role="status"><span className="muted-label">Loading presets...</span><div className="preset-grid" aria-hidden="true">{[0, 1, 2].map((key) => <div className="console-card preset-placeholder" key={key}><span /><span /><span /></div>)}</div></div>}
      <div className="preset-grid">{presets.map((preset) => <article className="console-card" key={preset.id}><div className="section-heading"><span className="eyebrow">{preset.traps.join(" / ")}</span><ArrowRight size={16} /></div><h3>{preset.title}</h3><p>{preset.description}</p><details><summary>View task</summary><p>{preset.task}</p>{preset.auto_approve && <p><strong className="badge">Simulated demo approval — not human consent</strong></p>}</details><button className="primary-button" disabled={launching !== null} onClick={() => launch(preset.id)}>{launching === preset.id ? "Starting..." : "Launch live run"}</button></article>)}</div>
    </section>
  </>;
}
