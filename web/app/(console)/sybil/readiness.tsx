"use client";

import { SkeletonGroup, SkeletonLines, Skeleton } from "@/components/skeleton";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type Schema } from "@/lib/api";
import { siteOptions, toggleBridge, toggleTakeover, type SiteOptions } from "@/lib/sybil-edits";
import styles from "./sybil.module.css";
import { SybilGraph, type SelectedEdge } from "./graph";
import { RunView } from "../run-view";
import WakeSlider from "@/components/reactbits/WakeSlider";

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


function SiteAction({ active, disabled, onClick, label, note }: { active: boolean; disabled: boolean; onClick: () => void; label: string; note: string }) {
  return (
    <div style={{ marginTop: "var(--s2)", paddingTop: "var(--s2)", borderTop: "1px solid var(--line)" }}>
      <button className={active ? "secondary-button" : "primary-button"} disabled={disabled} onClick={onClick} style={{ width: "100%" }}>
        {label}
      </button>
      <p style={{ color: "var(--muted)", fontSize: "0.75rem", marginTop: "var(--s1)" }}>{note}</p>
    </div>
  );
}

function NodeInspector({
  node,
  recommendations,
  outgoingCount,
  incomingCount,
  options,
  busy,
  onToggleBridge,
  onToggleTakeover,
  onClose,
}: {
  node: GraphNode;
  recommendations: Schema["SybilRecommendation"][];
  outgoingCount: number;
  incomingCount: number;
  options: SiteOptions | null; // null: not a real site, or no revision to edit yet
  busy: boolean;
  onToggleBridge: (nodeId: string) => void;
  onToggleTakeover: (nodeId: string) => void;
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
      {options && (
        <SiteAction
          active={options.compromised}
          disabled={busy || !options.canTakeOver}
          onClick={() => onToggleTakeover(node.id)}
          label={options.compromised
            ? `Release this site (-${options.takeoverCost} credits)`
            : `Take over this ${node.anchor ? "anchor" : "site"} (+${options.takeoverCost} credits)`}
          note={options.compromised
            ? "The attacker controls this real website and links it into the attack cluster."
            : `Seizes ${node.anchor ? "a trusted anchor" : "this real website"} and links it into the attack cluster.`}
        />
      )}
      {options && !node.anchor && !options.compromised && (
        <SiteAction
          active={options.bridged}
          disabled={busy || !options.canBridge}
          onClick={() => onToggleBridge(node.id)}
          label={options.bridged
            ? `Disconnect real-web bridge (-${options.bridgeCost} credits)`
            : `Bridge to attack (+${options.bridgeCost} credits)`}
          note={options.bridged
            ? "This real website has a cooperating link pointing into the attack cluster."
            : "Creates a cooperating link from this real website into the attack cluster."}
        />
      )}
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
          <dd>Cut with the other top 12 outside sources if it is one of them</dd>
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
  const [count, setCount] = useState(300); // more than Shop A's 12 real fans, so the attack visibly misleads the unprotected agent
  const [target, setTarget] = useState<"A" | "B">("B");
  const [pattern, setPattern] = useState<
    "disconnected" | "dense" | "clusters" | "hub" | "chain"
  >("disconnected");
  const [density, setDensity] = useState(0.1);
  const [bridges, setBridges] = useState(0);
  const [revision, setRevision] = useState<Revision | null>(null);
  const [view, setView] = useState<GraphView | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [counterfactual, setCounterfactual] = useState<Counterfactual | null>(null);
  const [draft, setDraft] = useState("");
  const [history, setHistory] = useState<Revision[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<{ id: string; queue: number; ended: boolean } | null>(null);
  const running = run !== null && !run.ended;
  const endRun = useCallback(() => setRun((current) => current && { ...current, ended: true }), []);
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
      const next = await api.generateSybilScenario(dataset.dataset_id, {
        count,
        seed: 1,
        pattern,
        density,
        target,
        bridges,
      });
      await showRevision(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Scenario creation failed.");
    } finally {
      setBusy(false);
    }
  }

  // Every edit path: build the next edit set, let the server price and validate it, show it.
  async function submitEdits(next: () => Schema["SybilScenarioCreate"], failure: string) {
    setBusy(true);
    setError(null);
    try {
      await showRevision(await api.createSybilScenario(next()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : failure);
    } finally {
      setBusy(false);
    }
  }

  const onToggleBridge = (site: string) =>
    revision && void submitEdits(() => toggleBridge(revision.edits, site), "Toggling bridge failed.");
  const onToggleTakeover = (site: string) =>
    revision && void submitEdits(() => toggleTakeover(revision.edits, site), "Takeover failed.");

  function parseDraft() {
    return JSON.parse(draft) as Schema["SybilScenarioCreate"];
  }

  const applyDraft = () => submitEdits(parseDraft, "Scenario edit failed.");

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
      setRun({ id: created.run_id, queue: created.queue_position, ended: false });
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
        <span>
          Common Crawl web graph ({dataset?.release ?? "loading"}):{" "}
          {dataset?.imported_nodes.toLocaleString() ?? "—"} sites,{" "}
          {dataset?.imported_edges.toLocaleString() ?? "—"} links
        </span>
        {!error && dataset && dataset.status !== "available" && <span>Dataset {dataset.status}</span>}
        <span>Real website links · shop recommendations and attack edits are simulated</span>
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
              <WakeSlider
                min={0}
                max={1}
                step={0.05}
                value={density}
                onChange={setDensity}
                disabled={!ready || busy || !["dense", "clusters"].includes(pattern)}
                bars={24}
                height={32}
                restHeight={8}
                gap={3}
                fillColor="#c2a15a"
                trackColor="#1f262d"
                ariaLabel="Internal density"
                formatValue={(value: number) => `${Math.round(value * 100)}%`}
                showValue
              />
            </label>
            <label>
              Real-web bridge links
              <WakeSlider
                min={0}
                max={12}
                step={1}
                value={bridges}
                onChange={setBridges}
                disabled={!ready || busy}
                bars={24}
                height={32}
                restHeight={8}
                gap={3}
                fillColor="#c2a15a"
                trackColor="#1f262d"
                ariaLabel="Real-web bridge links"
                formatValue={(value: number) => `${value} ${value === 1 ? "bridge" : "bridges"}`}
                showValue
              />
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
              <dd>{revision ? `${revision.budget.external_credits} / ${revision.budget.credit_limit}` : "—"}</dd>
            </div>
          </dl>
          <p>Generation uses seed 1. Repeating the same settings produces the same immutable revision.</p>
        </section>
        <section className={view ? styles.graphSection : styles.empty} aria-labelledby="graph-title">
          {!view ? (
            <>
              <h2 id="graph-title">{ready ? "Create a scenario" : "Real graph unavailable"}</h2>
              {dataset || error ? <p>{dataset?.reason ?? "Waiting for the dataset service."}</p> : <SkeletonGroup label="Checking the dataset…"><SkeletonLines n={2} /><Skeleton className="skeleton-frame" /></SkeletonGroup>}
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
              options={
                revision && selectedNode.provenance === "observed"
                  ? siteOptions(revision, selectedNode.id, selectedNode.anchor)
                  : null
              }
              busy={busy}
              onToggleBridge={onToggleBridge}
              onToggleTakeover={onToggleTakeover}
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
              <p>Click a node or edge in the graph to see its details.</p>
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
                  <dd>Support left after cutting every link from the 12 outside websites that send the most flow, all at once.</dd>
                </dl>
                <p>Formula sybil-v2 · restart 0.15.</p>
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
              busy ||
              running
            }
            onClick={() => void launchComparison()}
            aria-describedby="comparison-reason"
            aria-label="Run agent comparison"
          >
            {busy ? "Starting…" : running ? "Running…" : "Compare"}
          </button>
          <p id="comparison-reason">
            {assessment?.status === "complete" && assessment.converged
              ? "Runs both agents against this frozen graph revision."
              : "The comparison needs a complete, converged assessment first."}
          </p>
        </div>
      </section>
      {run && (
        <section id="sybil-run" aria-label="Agent comparison run">
          <RunView key={run.id} runId={run.id} queue={run.queue} showSybil={false} onEnd={endRun} />
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
