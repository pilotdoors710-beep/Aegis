"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Play, ShieldCheck } from "lucide-react";
import { api, type Schema } from "@/lib/api";
import { RunView } from "./run-view";

export default function ConsolePage() {
  const [presets, setPresets] = useState<Schema["Preset"][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.presets(controller.signal).then(setPresets).catch((error: Error) => {
      if (!controller.signal.aborted) setError(error.message);
    });
    return () => controller.abort();
  }, []);
  return <>
    <div className="console-intro"><div><p className="eyebrow">RUNTIME SECURITY / BROWSER AGENTS</p><h1>Check before committing.</h1><p>Compare the same browser agent with and without Aegis.</p></div><ShieldCheck className="intro-shield" size={48} /></div>
    <section className="sample-banner"><div><strong className="badge">SAMPLE DATA</strong><span>Prepared event stream. Live run launch is awaiting backend integration.</span></div><button className="primary-button" onClick={() => setSession((value) => value + 1)}><Play size={14} />{session ? "Restart sample" : "Play sample run"}</button></section>
    {session > 0 && <RunView key={session} runId="sample" />}
    <section className="preset-section"><div className="section-heading"><h2>Demo presets</h2><span>Tasks fixed before each run</span></div>
      {error && <p role="alert" className="error-message">Could not load presets: {error}</p>}
      {!presets.length && !error && <p role="status">Loading presets…</p>}
      <div className="preset-grid">{presets.map((preset) => <article className="console-card" key={preset.id}><div className="section-heading"><span className="eyebrow">{preset.traps.join(" / ")}</span><ArrowRight size={16} /></div><h3>{preset.title}</h3><p>{preset.description}</p><details><summary>View task</summary><p>{preset.task}</p>{preset.auto_approve && <p>Simulated demo approval preset</p>}</details><span className="muted-label">Live launch pending</span></article>)}</div>
    </section>
  </>;
}
