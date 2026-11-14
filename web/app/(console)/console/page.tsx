"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Play } from "lucide-react";
import SpotlightCard from "@/components/reactbits/SpotlightCard";
import StarBorder from "@/components/reactbits/StarBorder";
import { DashboardGlass } from "@/components/glass-refraction";
import { api, ApiError, type Schema } from "@/lib/api";
import { RunView } from "../run-view";
import { consumeConsoleEntry } from "@/lib/landing/phases";

type Preset = Schema["Preset"];

const SPOTLIGHT = { spotlightColor: "#ffffff", intensity: 0.65, spotlightSize: 380, borderGlow: 0.85, grain: 0 } as const;

function groupPresets(presets: Preset[]) {
  const featured = presets.find((preset) => preset.id === "main-demo") ?? presets[0];
  const rest = presets.filter((preset) => preset !== featured);
  const pairs: [Preset, Preset][] = [];
  const paired = new Set<string>();
  for (const preset of rest) {
    const partner = preset.pair_of ? rest.find((other) => other.id === preset.pair_of) : undefined;
    if (!partner || paired.has(preset.id)) continue;
    pairs.push([preset, partner]);
    paired.add(preset.id).add(partner.id);
  }
  const loose = rest.filter((preset) => !paired.has(preset.id));
  return {
    featured,
    pairs,
    permissions: loose.filter((preset) => preset.title.startsWith("Permission")),
    experimental: loose.filter((preset) => preset.title.startsWith("Experimental")),
    traps: loose.filter((preset) => !preset.title.startsWith("Permission") && !preset.title.startsWith("Experimental")),
  };
}

type Provider = Schema["OwnLLM"]["provider"];
// Suggestions only: the visitor types any model id their provider serves.
const MODEL_HINTS: Record<Provider, string> = {
  groq: "openai/gpt-oss-20b",
  gemini: "gemini-2.5-flash",
  openrouter: "meta-llama/llama-3.3-70b-instruct:free",
  cerebras: "llama-3.3-70b",
};

function OwnKeyPanel({ provider, model, apiKey, onChange }: { provider: Provider; model: string; apiKey: string; onChange: (next: { provider?: Provider; model?: string; apiKey?: string }) => void }) {
  const active = apiKey.trim() !== "";
  return <details className="console-card own-key">
    <summary>Use your own API key{active ? <strong className="badge">Your key · {provider}:{model || MODEL_HINTS[provider]}</strong> : <span className="own-key-hint">Optional · otherwise runs use the shared server key</span>}</summary>
    <div className="own-key-fields">
      <label>Provider<select value={provider} onChange={(e) => onChange({ provider: e.target.value as Provider })}>{(Object.keys(MODEL_HINTS) as Provider[]).map((p) => <option key={p} value={p}>{p}</option>)}</select></label>
      <label>Model<input type="text" value={model} placeholder={MODEL_HINTS[provider]} maxLength={100} spellCheck={false} autoComplete="off" onChange={(e) => onChange({ model: e.target.value })} /></label>
      <label>API key<input type="password" value={apiKey} maxLength={300} autoComplete="off" spellCheck={false} onChange={(e) => onChange({ apiKey: e.target.value })} /></label>
      <button type="button" className="secondary-button" disabled={!active && !model} onClick={() => onChange({ model: "", apiKey: "" })}>Clear</button>
    </div>
    <p className="sample-note">Your key is sent to the Aegis server for this run only and is not stored. Use a free-tier or throwaway key. It powers both agents and the ledger reading, so both sides use the same model. Runs with your own key are labelled and are not part of the published evaluation. The key is kept only on this page; it is forgotten when you leave or reload.</p>
  </details>;
}

const short = (title: string) => title.replace(/^(Permission|Experimental): /, "").replace(/^T\d+ · /, "");
const tags = (preset: Preset) => preset.traps.filter((trap) => trap !== "none");

export default function ConsolePage() {
  const router = useRouter();
  const [launching, setLaunching] = useState<string | null>(null);
  const [own, setOwn] = useState<{ provider: Provider; model: string; apiKey: string }>({ provider: "groq", model: "", apiKey: "" });
  async function launch(id: string) {
    setLaunching(id); setError(null);
    const llm = own.apiKey.trim() ? { provider: own.provider, model: own.model.trim() || MODEL_HINTS[own.provider], api_key: own.apiKey.trim() } : undefined;
    try {
      const run = await api.createRun({ preset_id: id, llm });
      router.push(`/runs/${encodeURIComponent(run.run_id)}?queue=${run.status === "queued" ? run.queue_position : 0}`);
    } catch (error) {
      setError(llm && error instanceof ApiError && error.status === 422 ? "The server rejected your key settings. Check the model name (letters, digits and . _ : / @ -) and the key." : error instanceof Error ? error.message : "Could not start the run.");
      setLaunching(null);
    }
  }
  const [presets, setPresets] = useState<Preset[]>([]);
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

  const { featured, pairs, permissions, experimental, traps } = groupPresets(presets);
  const launchButton = (preset: Preset, label = "Launch") => <button className="primary-button launch-button" disabled={launching !== null} aria-label={`Launch live run: ${preset.title}`} onClick={() => launch(preset.id)}>{launching === preset.id ? "Starting…" : label}{launching !== preset.id && <ArrowRight size={15} aria-hidden="true" />}</button>;
  const approval = (preset: Preset) => preset.auto_approve ? <strong className="badge">Simulated demo approval — not human consent</strong> : null;
  const row = (preset: Preset) => <SpotlightCard key={preset.id} {...SPOTLIGHT} className="preset-row">

    <div className="preset-row-text"><h3>{short(preset.title)}</h3><p>{preset.description}</p><details><summary>View task</summary><p>{preset.task}</p></details>{approval(preset)}</div>
    <div className="preset-row-side">{tags(preset).length ? <span className="trap-tag">{tags(preset).join(" · ")}</span> : <span className="trap-tag trap-tag-clean">No trap</span>}{launchButton(preset)}</div>
  </SpotlightCard>;

  return <><DashboardGlass />
    <header className="page-head"><h1 id="console-heading" tabIndex={-1}>Check before committing.</h1><p className="lede">Compare the same browser agent with and without Aegis.</p></header>
    {error && <p role="alert" className="error-message">{error}</p>}
    <OwnKeyPanel {...own} onChange={(next) => setOwn((value) => ({ ...value, ...next }))} />

    <StarBorder as="section" className="featured-run" color="#B8925A" trailColor="#ECEBEF" radius={28} duration={7} trailLength={0.22} glow={0.35} hover="none" clickPulse={false} backgroundColor="transparent" textColor="inherit" borderColor="rgb(255 255 255 / 65%)" aria-label="Main demo">

      <div className="featured-text">
        {featured ? <><h2>{featured.title}</h2><p>{featured.description}</p><p className="task-line"><span>Task</span>{featured.task}</p>{approval(featured)}</>
          : error ? <><h2>Live runs are unavailable</h2><p>The server did not return any presets. The recorded sample still plays.</p></>
          : <div role="status" className="preset-placeholder"><span className="muted-label">Loading presets…</span><span /><span /><span /></div>}
      </div>
      <div className="featured-actions">
        {featured && launchButton(featured, "Launch live run")}
        <button className="secondary-button" onClick={() => setSession((value) => value + 1)}><Play size={14} aria-hidden="true" />{session ? "Restart sample" : "Play sample run"}</button>
        <p className="sample-note"><strong className="badge">SAMPLE DATA</strong> A prepared comparison, not a live run.</p>
      </div>
    </StarBorder>

    {session > 0 && <RunView key={session} runId="sample" />}

    {traps.length > 0 && <section className="preset-section" aria-labelledby="presets-traps">
      <div className="section-heading"><h2 id="presets-traps">One trap at a time</h2><span>Tasks are fixed before each run</span></div>
      <div className="preset-list">{traps.map(row)}</div>
    </section>}

    {(pairs.length > 0 || permissions.length > 0) && <section className="preset-section" aria-labelledby="presets-permission">
      <div className="section-heading"><h2 id="presets-permission">Same checkout, different permission</h2><span>The ledger is written from the task and never edited</span></div>
      {pairs.map(([left, right]) => <div className="preset-pair" key={left.id}>{[left, right].map((preset) => <SpotlightCard key={preset.id} {...SPOTLIGHT} className="preset-pair-side">

        <h3>{short(preset.title)}</h3>
        <p className="task-line"><span>Task</span>{preset.task}</p>
        <p>{preset.description}</p>
        {approval(preset)}
        {launchButton(preset)}
      </SpotlightCard>)}</div>)}
      {permissions.length > 0 && <div className="preset-list">{permissions.map(row)}</div>}
    </section>}

    {experimental.length > 0 && <section className="preset-section" aria-labelledby="presets-experimental">
      <div className="section-heading"><h2 id="presets-experimental">Experimental: disposable consent trials</h2><span>Arena only · both box states are tested in throwaway copies</span></div>
      <div className="preset-list">{experimental.map(row)}</div>
    </section>}
  </>;
}
