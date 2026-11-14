"use client";

import { useEffect, useState } from "react";
import { Database, Network } from "lucide-react";
import { api, type Schema } from "@/lib/api";
import styles from "./sybil.module.css";

export function SybilReadiness() {
  const [datasets, setDatasets] = useState<Schema["SybilDatasetStatus"][] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.sybilDatasets(controller.signal).then((data) => {
      if (!controller.signal.aborted) setDatasets(data);
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Dataset request failed.");
    });
    return () => controller.abort();
  }, [attempt]);
  const dataset = datasets?.[0];
  return <div className={styles.page}>
    <header className="page-head">
      <h1>Sybil Playground</h1>
      <p className="lede">Change a recommendation network. Inspect structural support. Compare the agent’s choice.</p>
      <p>Real website-link background. Shop recommendations and attack edits are simulated.</p>
    </header>
    <section className={`console-card ${styles.strip}`} aria-label="Dataset status" aria-live="polite">
      <span><Database size={18} aria-hidden="true" /> {dataset?.release ?? "Pinned release pending server response"}</span>
      <span>{error ? "Unavailable" : datasets ? "Data unavailable" : "Checking dataset…"}</span>
      <span>Observation: {dataset?.observation_date ?? "Not imported"}</span>
      <span>Revision: none</span>
    </section>
    {error && <div className="console-card" role="alert"><p>{error}</p>
      <button className="secondary-button" onClick={() => { setError(null); setDatasets(null); setAttempt(attempt + 1); }}>Retry dataset check</button>
    </div>}
    <div className={styles.workspace}>
      <section className="console-card" aria-labelledby="scenario-title">
        <h2 id="scenario-title">Scenario</h2>
        <p>Challenge mode will keep the background, anchors and scoring settings fixed.</p>
        <dl className={styles.facts}>
          <div><dt>Injected website limit</dt><dd>1,000</dd></div>
          <div><dt>Internal link limit</dt><dd>100,000</dd></div>
          <div><dt>External credit limit</dt><dd>25</dd></div>
        </dl>
        <p>Editing opens after a validated real dataset is available.</p>
      </section>
      <section className={`console-card ${styles.empty}`} aria-labelledby="graph-title">
        <Network size={36} aria-hidden="true" />
        <h2 id="graph-title">Real graph not imported</h2>
        <p>{dataset?.reason ?? "The playground needs a validated Common Crawl extraction before it can display or score a network."}</p>
        <p>Imported: {dataset?.imported_nodes.toLocaleString() ?? "—"} nodes / {dataset?.imported_edges.toLocaleString() ?? "—"} edges<br />Scored: none · Displayed: none</p>
        <p>The browser will display a subset. Visual filters will not change the scored graph.</p>
      </section>
      <section className="console-card" aria-labelledby="evidence-title">
        <h2 id="evidence-title">Evidence</h2>
        <p>No assessment is available. Neither shop can pass the graph evidence check.</p>
        <details className={styles.formula}>
          <summary>Inspect the score formula</summary>
          <p><code>R = 100S (0.40 + 0.20D + 0.20L + 0.20E)</code></p>
          <dl><dt>S · Structural support</dt><dd>Trust mass normalized with the frozen dataset scale.</dd>
            <dt>D · Anchor breadth</dt><dd>How widely support is distributed across curated anchors.</dd>
            <dt>L · Anchor withdrawal</dt><dd>Support retained without the strongest starting source.</dd>
            <dt>E · Tested connections</dt><dd>Support retained after each of up to five influential links is removed.</dd></dl>
          <p>Formula sybil-v1 · restart 0.15. Not yet evaluated on the deployment graph.</p>
        </details>
      </section>
    </div>
    <section className={`console-card ${styles.comparison}`} aria-label="Shop comparison">
      {["Shop A", "Shop B"].map((shop) => <div key={shop}><h2>{shop}</h2><p><strong>Unavailable</strong> / 100</p><p>Recommendations, trust support and score deltas await a frozen scenario.</p></div>)}
      <div><button className="primary-button" disabled aria-describedby="comparison-reason">Run agent comparison</button><p id="comparison-reason">Requires a real dataset, full assessment and marketplace integration.</p></div>
    </section>
    <p className={styles.disclosure}>A heuristic measure of structural support and tested sensitivity. Not a probability that this shop is safe.</p>
  </div>;
}
