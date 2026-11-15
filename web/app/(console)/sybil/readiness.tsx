"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type Schema } from "@/lib/api";
import styles from "./sybil.module.css";
import { SybilGraph, type SelectedEdge } from "./graph";
import { RunView } from "../run-view";

type Dataset = Schema["SybilDatasetStatus"];
type Revision = Schema["SybilScenarioRevision"];
type GraphView = Schema["SybilGraphView"];
type GraphNode = Schema["SybilGraphNode"];
type Assessment = Schema["SybilAssessmentRecord"];
type Counterfactual = Schema["SybilCounterfactualResult"];

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}


function NodeInspector({
  node,
  recommendations,
  outgoingCount,
  incomingCount,
  onClose,
}: {
  node: GraphNode;
  recommendations: Schema["SybilRecommendation"][];
  outgoingCount: number;
  incomingCount: number;
  onClose: () => void;
}) {
  return (
    <div className={styles.inspector} aria-labelledby="node-inspector-title">
      <div className={styles.inspectorHead}>
        <h3 id="node-inspector-title">Node: {node.label}</h3>
        <button className="secondary-button" onClick={onClose} aria-label="Close node inspector">
          Clear
        </button>
      </div>
      <dl className={styles.facts}>
        <div>
          <dt>Identity</dt>
          <dd>{node.id}</dd>
        </div>
        <div>
          <dt>Provenance</dt>
          <dd>{node.provenance}</dd>
        </div>
        <div>
          <dt>Curated anchor</dt>
          <dd>{node.anchor ? "Yes (seed anchor)" : "No"}</dd>
        </div>
        <div>
          <dt>Outdegree (retained / original)</dt>
          <dd>
            {node.retained_outdegree} / {node.original_outdegree}
          </dd>
        </div>
        <div>
          <dt>Incoming links (in view)</dt>
          <dd>{incomingCount}</dd>
        </div>
        <div>
          <dt>Outgoing links (in view)</dt>
          <dd>{outgoingCount}</dd>
        </div>
        <div>
          <dt>Recommends</dt>
          <dd>
            {recommendations.length > 0
              ? recommendations.map((r) => `Shop ${r.shop}`).join(", ")
              : "None"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function EdgeInspector({
  edge,
  sourceLabel,
  targetLabel,
  onClose,
}: {
  edge: SelectedEdge;
  sourceLabel: string;
  targetLabel: string;
  onClose: () => void;
}) {
  return (
    <div className={styles.inspector} aria-labelledby="edge-inspector-title">
      <div className={styles.inspectorHead}>
        <h3 id="edge-inspector-title">
          Edge: {edge.source} → {edge.target}
        </h3>
        <button className="secondary-button" onClick={onClose} aria-label="Close edge inspector">
          Clear
        </button>
      </div>
      <dl className={styles.facts}>
        <div>
          <dt>Direction</dt>
          <dd>
            {sourceLabel} → {targetLabel}
          </dd>
        </div>
        <div>
          <dt>Provenance</dt>
          <dd>
            {edge.provenance === "simulated"
              ? "Simulated (attack link)"
              : "Observed (web graph)"}
          </dd>
        </div>
        <div>
          <dt>Sensitivity testing</dt>
          <dd>Evaluated in leave-one-out steady-state flow if in top 5 candidates</dd>
        </div>
      </dl>
    </div>
  );
}

function Score({ shop, assessment }: { shop: "A" | "B"; assessment: Assessment | null }) {
  const score = assessment?.scores?.[shop];
  return (
    <div>
      <h2>Shop {shop}</h2>
      <p className={styles.total}>
        <strong>{score ? score.total_robustness.toFixed(1) : "—"}</strong> / 100
      </p>
      {score ? (
        <dl className={styles.metrics}>
          <div>
            <dt>Recommendations</dt>
            <dd>{score.recommendation_count}</dd>
          </div>
          <div>
            <dt>Structural support</dt>
            <dd>{(score.structural_support * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>Anchor breadth</dt>
            <dd>{(score.anchor_breadth * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>Anchor withdrawal</dt>
            <dd>{(score.anchor_withdrawal_resilience * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>Tested connections</dt>
            <dd>{(score.tested_connection_resilience * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>Trust support</dt>
            <dd>{score.trust_weighted_support.toExponential(3)}</dd>
          </div>
        </dl>
      ) : (
        <p>
          {assessment?.status === "unavailable"
            ? assessment.reason
            : "Assessment pending."}
        </p>
      )}
    </div>
  );
}

function ScoreDeltas({ result }: { result: Counterfactual }) {
  const deltas = result.deltas;
  if (!deltas) return null;
  return (
    <div>
      {(["A", "B"] as const).map((shop) => {
        const delta = deltas[shop];
        return (
          <p key={shop}>
            Shop {shop}: total {delta.total_robustness.toFixed(1)} · support{" "}
            {(delta.structural_support * 100).toFixed(1)} points · rank{" "}
            {delta.rank > 0 ? "+" : ""}
            {delta.rank}
          </p>
        );
      })}
    </div>
  );
}

export function SybilReadiness() {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [count, setCount] = useState(10);
  const [target, setTarget] = useState<"A" | "B">("B");
  const [pattern, setPattern] = useState<
    "disconnected" | "dense" | "clusters" | "hub" | "chain"
  >("disconnected");
  const [density, setDensity] = useState(0.1);
  const [revision, setRevision] = useState<Revision | null>(null);
  const [view, setView] = useState<GraphView | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [counterfactual, setCounterfactual] = useState<Counterfactual | null>(null);
  const [draft, setDraft] = useState("");
  const [history, setHistory] = useState<Revision[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<{ id: string; queue: number } | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdge | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .sybilDatasets(controller.signal)
      .then(setDatasets)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error ? cause.message : "Dataset request failed.",
          );
      });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    if (!assessment || !["queued", "running"].includes(assessment.status)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(
      () =>
        api
          .sybilAssessment(assessment.id, controller.signal)
          .then(setAssessment)
          .catch((cause: unknown) => {
            if (!controller.signal.aborted)
              setError(
                cause instanceof Error ? cause.message : "Assessment polling failed.",
              );
          }),
      500,
    );
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [assessment]);

  const dataset = datasets?.[0];
  const ready = dataset?.status === "available" && Boolean(dataset.dataset_id);

  // Opened from a run (/sybil?revision=...): load that saved revision, its graph and scores.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("revision");
    if (!ready || !id) return;
    api
      .sybilScenario(id)
      .then((saved) => showRevision(saved))
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "Saved revision could not be loaded."),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the dataset becomes ready
  }, [ready]);

  const selectedNode = useMemo(
    () => view?.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [view, selectedNodeId],
  );
  const nodeRecommendations = useMemo(
    () =>
      view?.recommendations.filter(
        (r) => r.website === selectedNode?.id || r.website === selectedNode?.label,
      ) ?? [],
    [view, selectedNode],
  );
  const outgoingCount = useMemo(
    () => view?.edges.filter((e) => e.source === selectedNode?.id).length ?? 0,
    [view, selectedNode],
  );
  const incomingCount = useMemo(
    () => view?.edges.filter((e) => e.target === selectedNode?.id).length ?? 0,
    [view, selectedNode],
  );

  async function showRevision(next: Revision, remember = true) {
    setBusy(true);
    setError(null);
    setAssessment(null);
    setCounterfactual(null);
    setRun(null);
    setSelectedNodeId(null);
    setSelectedEdge(null);
    try {
      const [nextView, job] = await Promise.all([
        api.sybilView(next.id),
        api.createSybilAssessment(next.id),
      ]);
      setRevision(next);
      setView(nextView);
      setAssessment(job);
      setDraft(JSON.stringify(next.edits, null, 2));
      // Keep the URL pointing at this revision so runs (and reloads) can come back to it.
      window.history.replaceState(null, "", `/sybil?revision=${next.id}`);
      if (remember) {
        const nextHistory = [...history.slice(0, historyIndex + 1), next];
        setHistory(nextHistory);
        setHistoryIndex(nextHistory.length - 1);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Revision loading failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createScenario(event: FormEvent) {
    event.preventDefault();
    if (!dataset?.dataset_id) return;
    setBusy(true);
    setError(null);
    setAssessment(null);
    try {
      const nodes = Array.from({ length: count }, (_, i) => `sim:judge-${i}`);
      const next =
        pattern === "disconnected"
          ? await api.createSybilScenario({
              dataset_id: dataset.dataset_id,
              mode: "challenge",
              injected_nodes: nodes,
              added_links: [],
              removed_links: [],
              removed_recommendations: [],
              compromised: [],
              cooperating_links: [],
              restart: 0.15,
              recommendations: nodes.map((website) => ({ website, shop: target })),
            })
          : await api.generateSybilScenario(dataset.dataset_id, {
              count,
              seed: 1,
              pattern,
              density,
              target,
            });
      await showRevision(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Scenario creation failed.");
    } finally {
      setBusy(false);
    }
  }

  function parseDraft() {
    return JSON.parse(draft) as Schema["SybilScenarioCreate"];
  }

  async function applyDraft() {
    setBusy(true);
    setError(null);
    try {
      await showRevision(await api.createSybilScenario(parseDraft()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Scenario edit failed.");
    } finally {
      setBusy(false);
    }
  }

  async function previewDraft() {
    if (!revision) return;
    setBusy(true);
    setError(null);
    setCounterfactual(null);
    try {
      setCounterfactual(await api.sybilCounterfactual(revision.id, parseDraft()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Counterfactual failed.");
    } finally {
      setBusy(false);
    }
  }

  async function moveHistory(nextIndex: number) {
    const next = history[nextIndex];
    if (!next) return;
    await showRevision(next, false);
    setHistoryIndex(nextIndex);
  }

  function exportScenario() {
    if (revision)
      download(
        `sybil-${revision.id.slice(0, 12)}.json`,
        JSON.stringify({ revision, assessment }, null, 2),
        "application/json",
      );
  }

  function exportScores() {
    if (!assessment?.scores) return;
    const rows = [
      "shop,total,structural_support,anchor_breadth,anchor_withdrawal,tested_connections,recommendations",
    ];
    for (const shop of ["A", "B"] as const) {
      const score = assessment.scores[shop];
      rows.push(
        [
          shop,
          score.total_robustness,
          score.structural_support,
          score.anchor_breadth,
          score.anchor_withdrawal_resilience,
          score.tested_connection_resilience,
          score.recommendation_count,
        ].join(","),
      );
    }
    download(`sybil-${revision?.id.slice(0, 12)}-scores.csv`, rows.join("\n"), "text/csv");
  }

  function exportGraph() {
    const graph = document.getElementById("sybil-graph");
    if (!(graph instanceof HTMLCanvasElement)) return;
    graph.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `sybil-${revision?.id.slice(0, 12)}-graph.png`;
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  async function launchComparison() {
    if (!ready || !revision || assessment?.status !== "complete" || !assessment.converged) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRun({
        preset_id: "sybil-two-shop",
        sybil_revision_id: revision.id,
      });
      setRun({ id: created.run_id, queue: created.queue_position });
      window.setTimeout(() => document.getElementById("sybil-run")?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Launching comparison run failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <h1 className="sr-only">Sybil Playground</h1>
      <section className={styles.strip} aria-label="Dataset status" aria-live="polite">
        <span>{dataset?.release ?? "Checking pinned release"}</span>
        <span>{error ? "Error" : dataset?.status ?? "Checking"}</span>
        <span>
          Imported: {dataset?.imported_nodes.toLocaleString() ?? "—"} nodes /{" "}
          {dataset?.imported_edges.toLocaleString() ?? "—"} edges
        </span>
        <span>Mode: Challenge</span>
        <span>Revision: {revision?.id.slice(0, 12) ?? "none"}</span>
        <span>Scores: {assessment?.status ?? "none"}</span>
        <span>Real website-link background · shop recommendations and attack edits are simulated</span>
      </section>
      {error && (
        <div className={styles.alert} role="alert">
          <p>{error}</p>
          <button
            className="secondary-button"
            onClick={() => {
              setError(null);
              setAttempt((value) => value + 1);
            }}
            aria-label="Retry the dataset check"
          >
            Retry
          </button>
        </div>
      )}
      <div className={styles.workspace}>
        <section aria-labelledby="scenario-title">
          <h2 id="scenario-title">Attack controls</h2>
          <form onSubmit={createScenario} className={styles.controls}>
            <label>
              Target shop
              <select
                value={target}
                onChange={(event) => setTarget(event.target.value as "A" | "B")}
                disabled={!ready || busy}
              >
                <option value="A">Shop A</option>
                <option value="B">Shop B</option>
              </select>
            </label>
            <label>
              Connection pattern
              <select
                value={pattern}
                onChange={(event) => setPattern(event.target.value as typeof pattern)}
                disabled={!ready || busy}
              >
                <option value="disconnected">Disconnected</option>
                <option value="dense">Dense cluster</option>
                <option value="clusters">Multiple clusters</option>
                <option value="hub">Hub and spoke</option>
                <option value="chain">Chain</option>
              </select>
            </label>
            <label>
              Generated recommending websites
              <input
                type="number"
                min="10"
                max="1000"
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
                disabled={!ready || busy}
              />
            </label>
            <label>
              Internal density
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={density}
                onChange={(event) => setDensity(Number(event.target.value))}
                disabled={!ready || busy || !["dense", "clusters"].includes(pattern)}
              />
              <span>{Math.round(density * 100)}%</span>
            </label>
            <button className="primary-button" disabled={!ready || busy}>
              {busy ? "Creating…" : "Create revision"}
            </button>
          </form>
          <dl className={styles.facts}>
            <div>
              <dt>Injected websites</dt>
              <dd>{revision?.budget.injected_websites ?? 0} / 1,000</dd>
            </div>
            <div>
              <dt>Internal links</dt>
              <dd>{revision?.budget.internal_links ?? 0} / 100,000</dd>
            </div>
            <div>
              <dt>External credits</dt>
              <dd>{revision?.budget.external_credits ?? 0} / 25</dd>
            </div>
          </dl>
          <p>Generation uses seed 1. Repeating the same settings produces the same immutable revision.</p>
        </section>
        <section className={view ? styles.graphSection : styles.empty} aria-labelledby="graph-title">
          {!view ? (
            <>
              <h2 id="graph-title">{ready ? "Create a scenario" : "Real graph unavailable"}</h2>
              <p>{dataset?.reason ?? "Waiting for the dataset service."}</p>
            </>
          ) : (
            <>
              <h2 id="graph-title">Topology subset</h2>
              <p>
                Displaying {view.displayed_nodes.toLocaleString()} of{" "}
                {view.total_nodes.toLocaleString()} nodes and{" "}
                {view.displayed_edges.toLocaleString()} of{" "}
                {view.total_edges.toLocaleString()} links. Click any node or edge to inspect.
              </p>
              <SybilGraph
                view={view}
                selectedNodeId={selectedNodeId}
                selectedEdge={selectedEdge}
                onSelectNode={(id) => {
                  setSelectedNodeId(id);
                  setSelectedEdge(null);
                }}
                onSelectEdge={(edge) => {
                  setSelectedEdge(edge);
                  setSelectedNodeId(null);
                }}
                onClearSelection={() => {
                  setSelectedNodeId(null);
                  setSelectedEdge(null);
                }}
              />
            </>
          )}
        </section>
        <section aria-labelledby="evidence-title">
          <h2 id="evidence-title">Evidence inspector</h2>
          {selectedNode ? (
            <NodeInspector
              node={selectedNode}
              recommendations={nodeRecommendations}
              outgoingCount={outgoingCount}
              incomingCount={incomingCount}
              onClose={() => setSelectedNodeId(null)}
            />
          ) : selectedEdge ? (
            <EdgeInspector
              edge={selectedEdge}
              sourceLabel={
                view?.nodes.find((n) => n.id === selectedEdge.source)?.label ?? selectedEdge.source
              }
              targetLabel={
                view?.nodes.find((n) => n.id === selectedEdge.target)?.label ?? selectedEdge.target
              }
              onClose={() => setSelectedEdge(null)}
            />
          ) : (
            <>
              <p>
                {assessment?.status === "complete"
                  ? `Converged in ${assessment.iterations} iterations (${assessment.elapsed_ms?.toFixed(0)} ms).`
                  : assessment?.reason ?? "Create a revision to calculate evidence."}
              </p>
              <p>Select any node or edge in the graph or table to view specific topology details.</p>
              <details className={styles.formula}>
                <summary>Inspect the score formula</summary>
                <p>
                  <code>R = 100S (0.40 + 0.20D + 0.20L + 0.20E)</code>
                </p>
                <dl>
                  <dt>S · Structural support</dt>
                  <dd>Trust mass normalized with the frozen dataset scale.</dd>
                  <dt>D · Anchor breadth</dt>
                  <dd>How widely support is distributed across curated anchors.</dd>
                  <dt>L · Anchor withdrawal</dt>
                  <dd>Support retained without the strongest starting source.</dd>
                  <dt>E · Tested connections</dt>
                  <dd>Support retained after each of up to five influential links is removed.</dd>
                </dl>
                <p>Formula sybil-v1 · restart 0.15.</p>
              </details>
            </>
          )}
        </section>
      </div>
      <section className={styles.comparison} aria-label="Shop comparison">
        <Score shop="A" assessment={assessment} />
        <Score shop="B" assessment={assessment} />
        <div>
          <button
            className="primary-button"
            disabled={
              !ready ||
              !revision ||
              assessment?.status !== "complete" ||
              !assessment.converged ||
              busy
            }
            onClick={() => void launchComparison()}
            aria-describedby="comparison-reason"
            aria-label="Run agent comparison"
          >
            {busy ? "Starting…" : "Compare"}
          </button>
          <p id="comparison-reason">
            {assessment?.status === "complete" && assessment.converged
              ? "Launch paired browser comparison with this frozen graph revision."
              : "Complete, converged assessment required to run agent comparison."}
          </p>
        </div>
      </section>
      {run && (
        <section id="sybil-run" aria-label="Agent comparison run">
          <RunView key={run.id} runId={run.id} queue={run.queue} showSybil={false} />
          <Link className="secondary-button" href={`/runs/${encodeURIComponent(run.id)}?replay=1`}>
            Open in Runs
          </Link>
        </section>
      )}
      <p className={styles.disclosure}>
        A heuristic measure of structural support and tested sensitivity. Not a probability that this
        shop is safe.
      </p>
      {revision && (
        <details className={styles.advanced}>
          <summary>Advanced: edit the scenario as JSON</summary>
        <section className={styles.editor} aria-labelledby="editor-title">
          <div className={styles.editorHead}>
            <div>
              <h2 id="editor-title">Revision editor</h2>
              <p>
                Advanced mode accepts the complete permitted edit set. The server recalculates
                budgets and rejects forbidden edits.
              </p>
            </div>
            <div className={styles.actions}>
              <button
                className="secondary-button"
                disabled={busy || historyIndex <= 0}
                onClick={() => void moveHistory(historyIndex - 1)}
              >
                Undo
              </button>
              <button
                className="secondary-button"
                disabled={busy || historyIndex >= history.length - 1}
                onClick={() => void moveHistory(historyIndex + 1)}
              >
                Redo
              </button>
              <button
                className="secondary-button"
                disabled={busy}
                onClick={() => setDraft(JSON.stringify(revision.edits, null, 2))}
              >
                Reset draft
              </button>
            </div>
          </div>
          <label className={styles.jsonLabel}>
            Active edit set (JSON)
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              spellCheck={false}
              disabled={busy}
            />
          </label>
          <div className={styles.actions}>
            <button className="secondary-button" disabled={busy} onClick={() => void previewDraft()}>
              Preview score delta
            </button>
            <button className="primary-button" disabled={busy} onClick={() => void applyDraft()}>
              Create immutable revision
            </button>
            <button className="secondary-button" onClick={exportScenario}>
              Export JSON
            </button>
            <button
              className="secondary-button"
              disabled={!assessment?.scores}
              onClick={exportScores}
            >
              Export score CSV
            </button>
            <button className="secondary-button" disabled={!view} onClick={exportGraph}>
              Export graph PNG
            </button>
          </div>
          {counterfactual && (
            <div className={styles.delta} aria-live="polite">
              <p>
                <strong>Counterfactual:</strong> {counterfactual.status} in{" "}
                {counterfactual.elapsed_ms.toFixed(0)} ms
              </p>
              <ScoreDeltas result={counterfactual} />
              {counterfactual.reason && <p>{counterfactual.reason}</p>}
            </div>
          )}
        </section>
        </details>
      )}
    </div>
  );
}
