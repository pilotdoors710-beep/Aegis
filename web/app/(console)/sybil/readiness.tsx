"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, type Schema } from "@/lib/api";
import styles from "./sybil.module.css";

type Dataset = Schema["SybilDatasetStatus"];
type Revision = Schema["SybilScenarioRevision"];
type GraphView = Schema["SybilGraphView"];
type Assessment = Schema["SybilAssessmentRecord"];

function GraphPreview({ view }: { view: GraphView }) {
  const plotted = useMemo(() => {
    const minX = Math.min(...view.nodes.map((node) => node.x));
    const maxX = Math.max(...view.nodes.map((node) => node.x));
    const minY = Math.min(...view.nodes.map((node) => node.y));
    const maxY = Math.max(...view.nodes.map((node) => node.y));
    const scale = (value: number, low: number, high: number, size: number) =>
      20 + ((value - low) / (high - low || 1)) * size;
    return new Map(view.nodes.map((node) => [node.id, {
      ...node, px: scale(node.x, minX, maxX, 620), py: scale(node.y, minY, maxY, 280),
    }]));
  }, [view.nodes]);
  const shops = { A: { x: 750, y: 105 }, B: { x: 750, y: 245 } };
  return <>
    <svg className={styles.graph} viewBox="0 0 800 340" role="img" aria-label={`Graph subset with ${view.displayed_nodes} websites and ${view.displayed_edges} links`}>
      <g className={styles.observedEdges}>{view.edges.slice(0, 1000).map((edge) => {
        const source = plotted.get(edge.source), target = plotted.get(edge.target);
        return source && target ? <line key={`${edge.source}-${edge.target}`} x1={source.px} y1={source.py} x2={target.px} y2={target.py} className={edge.provenance === "simulated" ? styles.simulatedEdge : undefined} /> : null;
      })}</g>
      <g className={styles.recommendationEdges}>{view.recommendations.map((recommendation) => {
        const source = plotted.get(recommendation.website), target = shops[recommendation.shop];
        return source ? <line key={`${recommendation.website}-${recommendation.shop}`} x1={source.px} y1={source.py} x2={target.x} y2={target.y} /> : null;
      })}</g>
      {(["A", "B"] as const).map((shop) => <g key={shop} transform={`translate(${shops[shop].x - 34} ${shops[shop].y - 18})`}><rect width="68" height="36" rx="5" /><text x="34" y="23">Shop {shop}</text></g>)}
      {[...plotted.values()].map((node) => node.anchor
        ? <rect key={node.id} className={styles.anchorNode} x={node.px - 5} y={node.py - 5} width="10" height="10" transform={`rotate(45 ${node.px} ${node.py})`} />
        : <circle key={node.id} className={node.provenance === "simulated" ? styles.simulatedNode : styles.observedNode} cx={node.px} cy={node.py} r={node.provenance === "simulated" ? 4 : 3} />)}
    </svg>
    <details className={styles.nodeTable}><summary>Keyboard graph table</summary><div className={styles.tableScroll}><table><thead><tr><th>Website</th><th>Type</th><th>Anchor</th><th>Retained / original outdegree</th></tr></thead><tbody>{view.nodes.slice(0, 100).map((node) => <tr key={node.id}><td>{node.label}</td><td>{node.provenance}</td><td>{node.anchor ? "Yes" : "No"}</td><td>{node.retained_outdegree} / {node.original_outdegree}</td></tr>)}</tbody></table></div></details>
  </>;
}

function Score({ shop, assessment }: { shop: "A" | "B"; assessment: Assessment | null }) {
  const score = assessment?.scores?.[shop];
  return <div><h2>Shop {shop}</h2><p className={styles.total}><strong>{score ? score.total_robustness.toFixed(1) : "—"}</strong> / 100</p>
    {score ? <dl className={styles.metrics}><div><dt>Recommendations</dt><dd>{score.recommendation_count}</dd></div><div><dt>Structural support</dt><dd>{(score.structural_support * 100).toFixed(1)}</dd></div><div><dt>Anchor breadth</dt><dd>{(score.anchor_breadth * 100).toFixed(1)}</dd></div><div><dt>Anchor withdrawal</dt><dd>{(score.anchor_withdrawal_resilience * 100).toFixed(1)}</dd></div><div><dt>Tested connections</dt><dd>{(score.tested_connection_resilience * 100).toFixed(1)}</dd></div><div><dt>Trust support</dt><dd>{score.trust_weighted_support.toExponential(3)}</dd></div></dl> : <p>{assessment?.status === "unavailable" ? assessment.reason : "Assessment pending."}</p>}
  </div>;
}

export function SybilReadiness() {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [count, setCount] = useState(10);
  const [target, setTarget] = useState<"A" | "B">("B");
  const [pattern, setPattern] = useState<"disconnected" | "dense" | "clusters" | "hub" | "chain">("disconnected");
  const [density, setDensity] = useState(0.1);
  const [revision, setRevision] = useState<Revision | null>(null);
  const [view, setView] = useState<GraphView | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api.sybilDatasets(controller.signal).then(setDatasets).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Dataset request failed.");
    });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    if (!assessment || !["queued", "running"].includes(assessment.status)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => api.sybilAssessment(assessment.id, controller.signal).then(setAssessment).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Assessment polling failed.");
    }), 500);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [assessment]);
  const dataset = datasets?.[0];
  const ready = dataset?.status === "available" && Boolean(dataset.dataset_id);

  async function createScenario(event: FormEvent) {
    event.preventDefault();
    if (!dataset?.dataset_id) return;
    setBusy(true); setError(null); setAssessment(null);
    try {
      const nodes = Array.from({ length: count }, (_, i) => `sim:judge-${i}`);
      const next = pattern === "disconnected"
        ? await api.createSybilScenario({
          dataset_id: dataset.dataset_id, mode: "challenge", injected_nodes: nodes,
          added_links: [], removed_links: [], removed_recommendations: [], compromised: [],
          cooperating_links: [], restart: 0.15,
          recommendations: nodes.map((website) => ({ website, shop: target })),
        })
        : await api.generateSybilScenario(dataset.dataset_id, {
          count, seed: 1, pattern, density, target,
        });
      setRevision(next);
      const [nextView, job] = await Promise.all([api.sybilView(next.id), api.createSybilAssessment(next.id)]);
      setView(nextView); setAssessment(job);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Scenario creation failed.");
    } finally { setBusy(false); }
  }

  return <div className={styles.page}>
    <header className="page-head"><span className="label">Experimental · recommendation graph</span><h1>Sybil Playground</h1><p className="lede">Change a recommendation network. Inspect structural support. Compare the agent’s choice.</p><p>Real website-link background. Shop recommendations and attack edits are simulated.</p></header>
    <section className={styles.strip} aria-label="Dataset status" aria-live="polite"><span>{dataset?.release ?? "Checking pinned release"}</span><span>{error ? "Error" : dataset?.status ?? "Checking"}</span><span>Imported: {dataset?.imported_nodes.toLocaleString() ?? "—"} nodes / {dataset?.imported_edges.toLocaleString() ?? "—"} edges</span><span>Mode: Challenge</span><span>Revision: {revision?.id.slice(0, 12) ?? "none"}</span><span>Scores: {assessment?.status ?? "none"}</span></section>
    {error && <div className={styles.alert} role="alert"><p>{error}</p><button className="secondary-button" onClick={() => { setError(null); setAttempt((value) => value + 1); }} aria-label="Retry the dataset check">Retry</button></div>}
    <div className={styles.workspace}>
      <section aria-labelledby="scenario-title"><h2 id="scenario-title">Attack controls</h2><form onSubmit={createScenario} className={styles.controls}><label>Target shop<select value={target} onChange={(event) => setTarget(event.target.value as "A" | "B")} disabled={!ready || busy}><option value="A">Shop A</option><option value="B">Shop B</option></select></label><label>Connection pattern<select value={pattern} onChange={(event) => setPattern(event.target.value as typeof pattern)} disabled={!ready || busy}><option value="disconnected">Disconnected</option><option value="dense">Dense cluster</option><option value="clusters">Multiple clusters</option><option value="hub">Hub and spoke</option><option value="chain">Chain</option></select></label><label>Generated recommending websites<input type="number" min="10" max="1000" value={count} onChange={(event) => setCount(Number(event.target.value))} disabled={!ready || busy} /></label><label>Internal density<input type="range" min="0" max="1" step="0.05" value={density} onChange={(event) => setDensity(Number(event.target.value))} disabled={!ready || busy || !["dense", "clusters"].includes(pattern)} /><span>{Math.round(density * 100)}%</span></label><button className="primary-button" disabled={!ready || busy}>{busy ? "Creating…" : "Create revision"}</button></form><dl className={styles.facts}><div><dt>Injected websites</dt><dd>{revision?.budget.injected_websites ?? 0} / 1,000</dd></div><div><dt>Internal links</dt><dd>{revision?.budget.internal_links ?? 0} / 100,000</dd></div><div><dt>External credits</dt><dd>{revision?.budget.external_credits ?? 0} / 25</dd></div></dl><p>Generation uses seed 1. Repeating the same settings produces the same immutable revision.</p></section>
      <section className={styles.empty} aria-labelledby="graph-title">{!view ? <><h2 id="graph-title">{ready ? "Create a scenario" : "Real graph unavailable"}</h2><p>{dataset?.reason ?? "Waiting for the dataset service."}</p></> : <><h2 id="graph-title">Topology subset</h2><p>Displaying {view.displayed_nodes.toLocaleString()} of {view.total_nodes.toLocaleString()} nodes and {view.displayed_edges.toLocaleString()} of {view.total_edges.toLocaleString()} links.</p><GraphPreview view={view} /></>}</section>
      <section aria-labelledby="evidence-title"><h2 id="evidence-title">Evidence inspector</h2><p>{assessment?.status === "complete" ? `Converged in ${assessment.iterations} iterations (${assessment.elapsed_ms?.toFixed(0)} ms).` : assessment?.reason ?? "Create a revision to calculate evidence."}</p><details className={styles.formula}><summary>Inspect the score formula</summary><p><code>R = 100S (0.40 + 0.20D + 0.20L + 0.20E)</code></p><dl><dt>S · Structural support</dt><dd>Trust mass normalized with the frozen dataset scale.</dd><dt>D · Anchor breadth</dt><dd>How widely support is distributed across curated anchors.</dd><dt>L · Anchor withdrawal</dt><dd>Support retained without the strongest starting source.</dd><dt>E · Tested connections</dt><dd>Support retained after each of up to five influential links is removed.</dd></dl><p>Formula sybil-v1 · restart 0.15.</p></details></section>
    </div>
    <section className={styles.comparison} aria-label="Shop comparison"><Score shop="A" assessment={assessment} /><Score shop="B" assessment={assessment} /><div><button className="primary-button" disabled aria-describedby="comparison-reason" aria-label="Run agent comparison">Compare</button><p id="comparison-reason">Marketplace and frozen-run integration are the next release stage.</p></div></section>
    <p className={styles.disclosure}>A heuristic measure of structural support and tested sensitivity. Not a probability that this shop is safe.</p>
  </div>;
}
