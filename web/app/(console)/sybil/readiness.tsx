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
type BottleneckWitness = Schema["SybilBottleneckWitness"];
type AttackSearchResult = Schema["SybilAttackSearchResult"];
type BenchmarkSummary = Schema["SybilBenchmarkSummary"];

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
        <h3 id="node-inspector-title">Website: {node.label}</h3>
        <button className="secondary-button" onClick={onClose} aria-label="Close node inspector">
          Clear
        </button>
      </div>
      <dl className={styles.facts}>
        <div>
          <dt>ID</dt>
          <dd>{node.id}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{node.provenance === "simulated" ? "Fake (made by the attack)" : "Real (from web data)"}</dd>
        </div>
        <div>
          <dt>Trusted site</dt>
          <dd>{node.anchor ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt>Outgoing links (kept / total)</dt>
          <dd>
            {node.retained_outdegree} / {node.original_outdegree}
          </dd>
        </div>
        <div>
          <dt>Links pointing here (shown)</dt>
          <dd>{incomingCount}</dd>
        </div>
        <div>
          <dt>Links going out (shown)</dt>
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
            : `Take over this ${node.anchor ? "trusted site" : "site"} (+${options.takeoverCost} credits)`}
          note={options.compromised
            ? "The attacker controls this real site and points it at the fake sites."
            : `The attacker takes over this ${node.anchor ? "trusted" : "real"} site and points it at the fake sites.`}
        />
      )}
      {options && !node.anchor && !options.compromised && (
        <SiteAction
          active={options.bridged}
          disabled={busy || !options.canBridge}
          onClick={() => onToggleBridge(node.id)}
          label={options.bridged
            ? `Remove paid link (-${options.bridgeCost} credits)`
            : `Pay this site to link in (+${options.bridgeCost} credits)`}
          note={options.bridged
            ? "This real site links to the fake sites because the attacker paid it."
            : "The attacker pays this real site to add one link to the fake sites."}
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
          Link: {edge.source} → {edge.target}
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
          <dt>Source</dt>
          <dd>
            {edge.provenance === "simulated"
              ? "Fake (added by the attack)"
              : "Real (from web data)"}
          </dd>
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
            <dt>Trust</dt>
            <dd>{(score.structural_support * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>Spread</dt>
            <dd>{(score.anchor_breadth * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>Without top trusted site</dt>
            <dd>{(score.anchor_withdrawal_resilience * 100).toFixed(1)}</dd>
          </div>
          <div>
            <dt>After cutting top links</dt>
            <dd>{(score.tested_connection_resilience * 100).toFixed(1)}</dd>
          </div>
        </dl>
      ) : (
        <p>
          {assessment?.status === "unavailable"
            ? assessment.reason
            : "Calculating…"}
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
            Shop {shop}: score {delta.total_robustness.toFixed(1)} · trust{" "}
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
  const [witness, setWitness] = useState<BottleneckWitness | null>(null);
  const [searchResult, setSearchResult] = useState<AttackSearchResult | null>(null);
  const [benchmarkSummary, setBenchmarkSummary] = useState<BenchmarkSummary | null>(null);
  const [stage4Busy, setStage4Busy] = useState<string | null>(null);

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
        setError(cause instanceof Error ? cause.message : "Could not load the saved attack."),
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
    setWitness(null);
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
      setError(cause instanceof Error ? cause.message : "Could not load this attack.");
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
      setError(cause instanceof Error ? cause.message : "Could not build the attack.");
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
    revision && void submitEdits(() => toggleBridge(revision.edits, site), "Could not change the paid link.");
  const onToggleTakeover = (site: string) =>
    revision && void submitEdits(() => toggleTakeover(revision.edits, site), "Takeover failed.");

  function parseDraft() {
    return JSON.parse(draft) as Schema["SybilScenarioCreate"];
  }

  const applyDraft = () => submitEdits(parseDraft, "Could not apply the edit.");

  async function previewDraft() {
    if (!revision) return;
    setBusy(true);
    setError(null);
    setCounterfactual(null);
    try {
      setCounterfactual(await api.sybilCounterfactual(revision.id, parseDraft()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preview failed.");
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
      setError(cause instanceof Error ? cause.message : "Could not start the comparison.");
    } finally {
      setBusy(false);
    }
  }

  async function runWitness(targetShop: "A" | "B") {
    if (!revision) return;
    setStage4Busy(`witness-${targetShop}`);
    setError(null);
    try {
      const res = await api.sybilBottleneck(revision.id, targetShop);
      setWitness(res);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not find the weak points.");
    } finally {
      setStage4Busy(null);
    }
  }

  async function runSearch() {
    if (!dataset?.dataset_id) return;
    setStage4Busy("search");
    setError(null);
    try {
      const res = await api.sybilAttackSearch(dataset.dataset_id, {
        target: "B",
        max_proposals: 500,
        max_seconds: 60,
        seed: 1,
      });
      setSearchResult(res);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Attack search failed.");
    } finally {
      setStage4Busy(null);
    }
  }

  async function loadSearchedAttack() {
    if (!searchResult?.best_revision_id) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api.sybilScenario(searchResult.best_revision_id);
      await showRevision(saved);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load that attack.");
    } finally {
      setBusy(false);
    }
  }

  async function runBenchmark(sample: boolean) {
    setStage4Busy(sample ? "benchmark-sample" : "benchmark-full");
    setError(null);
    try {
      const res = await api.sybilBenchmark(sample);
      setBenchmarkSummary(res);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Attack test failed.");
    } finally {
      setStage4Busy(null);
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
        <span>Real website links. The shop recommendations and the attack are made up.</span>
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
              How the fake sites link together
              <select
                value={pattern}
                onChange={(event) => setPattern(event.target.value as typeof pattern)}
                disabled={!ready || busy}
              >
                <option value="disconnected">Not linked</option>
                <option value="dense">One tight group</option>
                <option value="clusters">Several groups</option>
                <option value="hub">One central site</option>
                <option value="chain">A chain</option>
              </select>
            </label>
            <label>
              Fake sites recommending the shop
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
              How tightly they link
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
                ariaLabel="How tightly the fake sites link"
                formatValue={(value: number) => `${Math.round(value * 100)}%`}
                showValue
              />
            </label>
            <label>
              Real sites paid to link in
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
                ariaLabel="Real sites paid to link in"
                formatValue={(value: number) => `${value} ${value === 1 ? "site" : "sites"}`}
                showValue
              />
            </label>
            <button className="primary-button" disabled={!ready || busy}>
              {busy ? "Building…" : "Build attack"}
            </button>
          </form>
          <dl className={styles.facts}>
            <div>
              <dt>Fake sites</dt>
              <dd>{revision?.budget.injected_websites ?? 0} / 1,000</dd>
            </div>
            <div>
              <dt>Links between fake sites</dt>
              <dd>{revision?.budget.internal_links ?? 0} / 100,000</dd>
            </div>
            <div>
              <dt>Credits spent</dt>
              <dd>{revision ? `${revision.budget.external_credits} / ${revision.budget.credit_limit}` : "—"}</dd>
            </div>
          </dl>
          <p>The same settings always build the same attack.</p>
        </section>
        <section className={view ? styles.graphSection : styles.empty} aria-labelledby="graph-title">
          {!view ? (
            <>
              <h2 id="graph-title">{ready ? "Build an attack to start" : "Web data not loaded"}</h2>
              {dataset || error ? <p>{dataset?.reason ?? "Waiting for the dataset service."}</p> : <SkeletonGroup label="Checking the dataset…"><SkeletonLines n={2} /><Skeleton className="skeleton-frame" /></SkeletonGroup>}
            </>
          ) : (
            <>
              <h2 id="graph-title">Website map</h2>
              <p>
                Showing {view.displayed_nodes.toLocaleString()} of{" "}
                {view.total_nodes.toLocaleString()} sites and{" "}
                {view.displayed_edges.toLocaleString()} of{" "}
                {view.total_edges.toLocaleString()} links. Click a site or link for details.
              </p>
              <SybilGraph
                view={view}
                selectedNodeId={selectedNodeId}
                selectedEdge={selectedEdge}
                witnessCutEdges={witness?.cut_edges}
                witnessNodes={witness?.bottleneck_nodes}
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
          <h2 id="evidence-title">Details</h2>
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
                  ? `Scores ready (${assessment.elapsed_ms?.toFixed(0)} ms).`
                  : assessment?.reason ?? "Build an attack to see the scores."}
              </p>
              <p>Click a site or link on the map to see its details.</p>
              <details className={styles.formula}>
                <summary>How the score works</summary>
                <p>
                  <code>R = 100S (0.40 + 0.20D + 0.20L + 0.20E)</code>
                </p>
                <dl>
                  <dt>S · Trust</dt>
                  <dd>How much trust reaches the sites that recommend this shop, starting from 8 well-known sites (Wikipedia, MIT and others).</dd>
                  <dt>D · Spread</dt>
                  <dd>Whether that trust comes from many of the 8 sites or only one or two.</dd>
                  <dt>L · Without top trusted site</dt>
                  <dd>How much trust is left if the most helpful of the 8 sites is removed.</dd>
                  <dt>E · After cutting top links</dt>
                  <dd>How much trust is left after cutting the 12 outside sites that send the most trust.</dd>
                </dl>
                <p>Score version sybil-v2.</p>
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
              ? "Runs both agents on this exact attack."
              : "Wait for the scores to finish first."}
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
        A rough score based on how trust flows through website links. It is not the chance that a
        shop is safe.
      </p>
      <section className={styles.stage4Section} aria-labelledby="stage4-title">
        <div className={styles.stage4Header}>
          <div>
            <h2 id="stage4-title">Deeper analysis</h2>
            <p>
              Find the weak points in a shop&apos;s trust, let the computer hunt for the strongest attack, and test many attacks at once.
            </p>
          </div>
          {stage4Busy && <span className={styles.stage4Meta}>Working…</span>}
        </div>

        <div className={styles.stage4Grid}>
          {/* Card 1: weak points */}
          <div className={styles.stage4Card}>
            <div>
              <h3>
                Weak points
                {witness && (
                  <span className={styles.cutEdgeBadge}>
                    Shop {witness.shop}
                  </span>
                )}
              </h3>
              <p className={styles.stage4Meta}>
                The fewest websites that all of a shop&apos;s trust has to pass through. Remove them and the trust is cut off.
              </p>
            </div>

            {witness ? (
              <>
                <dl className={styles.facts}>
                  <div>
                    <dt>Trust that gets through / weak points</dt>
                    <dd>
                      <strong>{witness.max_flow.toFixed(1)}</strong> ({witness.cut_size} weak points)
                    </dd>
                  </div>
                  <div>
                    <dt>Part of the map checked</dt>
                    <dd>
                      {witness.subgraph_nodes} sites · {witness.subgraph_edges} links
                      {witness.complete ? " (every path checked, so this is exact)" : " (only part of the map, so exact for this part only)"}
                    </dd>
                  </div>
                  <div>
                    <dt>Weak point sites</dt>
                    <dd>{witness.bottleneck_nodes.length ? witness.bottleneck_nodes.slice(0, 8).join(", ") : "none"}{witness.bottleneck_nodes.length > 8 && ` +${witness.bottleneck_nodes.length - 8} more`}</dd>
                  </div>
                  <div>
                    <dt>Links into them</dt>
                    <dd>{witness.cut_edges.length} links</dd>
                  </div>
                </dl>
                <p className={styles.stage4Meta}>Checks up to 2,500 sites on the shortest paths from the trusted sites to the shop&apos;s recommenders.</p>
                {(witness.bottleneck_nodes.length > 0 || witness.cut_edges.length > 0) && (
                  <span className={styles.cutEdgeBadge}>Shown as amber rings and dashed links on the map</span>
                )}
              </>
            ) : (
              <p className={styles.stage4Meta}>
                Shows which few websites a shop&apos;s trust depends on. A real shop usually has many paths; a faked one often hangs on a few.
              </p>
            )}

            <div className={styles.actions}>
              <button
                className="secondary-button"
                disabled={!revision || busy || stage4Busy !== null}
                onClick={() => void runWitness("B")}
              >
                {stage4Busy === "witness-B" ? "Checking B…" : "Check Shop B (attacked)"}
              </button>
              <button
                className="secondary-button"
                disabled={!revision || busy || stage4Busy !== null}
                onClick={() => void runWitness("A")}
              >
                {stage4Busy === "witness-A" ? "Checking A…" : "Check Shop A (real)"}
              </button>
              {witness && (
                <button
                  className="secondary-button"
                  disabled={stage4Busy !== null}
                  onClick={() => setWitness(null)}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Card 2: attack search */}
          <div className={styles.stage4Card}>
            <div>
              <h3>
                Find the strongest attack
                {searchResult && (
                  <span className={searchResult.best_passed_policy ? styles.failBadge : styles.passBadge}>
                    {searchResult.best_passed_policy ? "An attack got past Aegis" : "No attack got past Aegis"}
                  </span>
                )}
              </h3>
              <p className={styles.stage4Meta}>
                The computer tries up to 500 attacks in 60 seconds, each within the 25-credit budget, and keeps the one that scores highest. No AI model is used.
              </p>
            </div>

            {searchResult ? (
              <>
                <dl className={styles.facts}>
                  <div>
                    <dt>Attacks tried</dt>
                    <dd>{searchResult.proposals_evaluated} in {searchResult.elapsed_s.toFixed(2)} s</dd>
                  </div>
                  <div>
                    <dt>Best attack shape</dt>
                    <dd><code>{searchResult.best_proposal.pattern}</code> ({searchResult.best_proposal.count} sites)</dd>
                  </div>
                  <div>
                    <dt>Credits used</dt>
                    <dd>{searchResult.best_proposal.credits} / 25 credits</dd>
                  </div>
                  <div>
                    <dt>Highest Shop B score</dt>
                    <dd>
                      <strong>{searchResult.best_score.toFixed(1)}</strong> (trust {searchResult.best_proposal.support.toFixed(2)} · without top trusted site {searchResult.best_proposal.withdrawal.toFixed(2)} · after cutting top links {searchResult.best_proposal.connection.toFixed(2)})
                    </dd>
                  </div>
                  <div>
                    <dt>Stopped because</dt>
                    <dd>{{ iteration_limit: "tried all 500 attacks", time_limit: "60 seconds ran out", space_exhausted: "no more attacks left to try" }[searchResult.stopped_reason]}</dd>
                  </div>
                </dl>
                <p className={styles.stage4Meta}>This is the strongest attack it found. There may be a stronger one.</p>
                {searchResult.history.length > 0 && (
                  <div>
                    <span className={styles.stage4Meta}>Each time it found a better attack:</span>
                    <div className={styles.trajectoryList}>
                      {searchResult.history.map((h) => (
                        <div key={h.iteration}>
                          #{h.iteration}: {h.pattern} ({h.count} sites, {h.credits} cr) → score {h.score.toFixed(2)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className={styles.stage4Meta}>
                Tries different shapes of fake sites, paid links and site takeovers. It finds a strong attack, but there could be a stronger one it missed.
              </p>
            )}

            <div className={styles.actions}>
              <button
                className="primary-button"
                disabled={!ready || busy || stage4Busy !== null}
                onClick={() => void runSearch()}
              >
                {stage4Busy === "search" ? "Searching (up to 60 s)…" : "Find the strongest attack"}
              </button>
              {searchResult && (
                <button
                  className="secondary-button"
                  disabled={busy || stage4Busy !== null}
                  onClick={() => void loadSearchedAttack()}
                >
                  Load this attack
                </button>
              )}
            </div>
          </div>

          {/* Card 3: attack test */}
          <div className={styles.stage4Card}>
            <div>
              <h3>
                Test many attacks
              </h3>
              <p className={styles.stage4Meta}>
                Runs 180 different attacks on Shop B, plus 30 runs with no attack to compare against.
              </p>
            </div>

            {benchmarkSummary ? (
              <>
                <dl className={styles.facts}>
                  <div>
                    <dt>Runs</dt>
                    <dd>
                      {benchmarkSummary.total_scenarios} ({benchmarkSummary.attacks_tested} attacks, {benchmarkSummary.controls_tested} with no attack
                      {benchmarkSummary.unavailable > 0 && `, ${benchmarkSummary.unavailable} could not be scored`})
                    </dd>
                  </div>
                  <div>
                    <dt>Time taken</dt>
                    <dd>{benchmarkSummary.elapsed_s.toFixed(1)} s</dd>
                  </div>
                </dl>

                <table className={styles.stage4Table} aria-label="Attack test results">
                  <thead>
                    <tr>
                      <th>Shop B…</th>
                      <th>Under attack</th>
                      <th>Without attack</th>
                    </tr>
                  </thead>
                  <tbody>
                    {([
                      ["beats A on number of recommendations", benchmarkSummary.count_beats_a_rate, benchmarkSummary.reference.count_beats_a],
                      ["beats A on plain Google-style ranking (PageRank)", benchmarkSummary.pagerank_beats_a_rate, benchmarkSummary.reference.pagerank_beats_a],
                      ["beats A on trust from the 8 trusted sites", benchmarkSummary.support_beats_a_rate, benchmarkSummary.reference.support_beats_a],
                      ["beats A on the full Aegis score", benchmarkSummary.score_beats_a_rate, benchmarkSummary.reference.score_beats_a],
                      ["gets past Aegis without a warning", benchmarkSummary.policy_pass_rate, benchmarkSummary.reference.passed_policy],
                    ] as const).map(([label, rate, reference]) => (
                      <tr key={label}>
                        <td>{label}</td>
                        <td>{(rate * 100).toFixed(1)}%</td>
                        <td>{reference ? "yes" : "no"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className={styles.stage4Meta}>
                  How often attacks get past Aegis if one part of the score is switched off:{" "}
                  {Object.entries(benchmarkSummary.ablation_policy_pass_rates)
                    .map(([name, rate]) => `${name.replaceAll("_", " ")} ${(rate * 100).toFixed(1)}%`)
                    .join(" · ")}
                  . Runs with no attack that pass: {(benchmarkSummary.control_policy_pass_rate * 100).toFixed(1)}%.
                </p>
                <p className={styles.stage4Meta}>The no-attack runs use random real websites. We have not checked that those sites are honest, and this test does not prove any shop is safe.</p>

                <details className={styles.formula}>
                  <summary>See every run ({benchmarkSummary.rows.length + benchmarkSummary.controls.length})</summary>
                  <div style={{ maxHeight: "160px", overflowY: "auto", marginTop: "8px" }}>
                    <table className={styles.stage4Table}>
                      <thead>
                        <tr>
                          <th>Shape</th>
                          <th>Size</th>
                          <th>Credits</th>
                          <th>Count</th>
                          <th>PageRank</th>
                          <th>Trust</th>
                          <th>Score</th>
                          <th>Aegis</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...benchmarkSummary.rows, ...benchmarkSummary.controls].map((r, i) => (
                          <tr key={i}>
                            <td>{r.family}</td>
                            <td>{r.size}</td>
                            <td>{r.credits_used}</td>
                            <td>{r.count_beats_a ? "beats A" : "–"}</td>
                            <td>{r.pagerank_beats_a ? "beats A" : "–"}</td>
                            <td>{r.support_beats_a ? "beats A" : "–"}</td>
                            <td>{r.converged ? r.total_robustness.toFixed(1) : "unavailable"}</td>
                            <td>{r.passed_policy ? "passed" : "warned"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </>
            ) : (
              <p className={styles.stage4Meta}>
                Shows how often simple measures (like counting recommendations) get fooled, compared with the full Aegis score.
              </p>
            )}

            <div className={styles.actions}>
              <button
                className="secondary-button"
                disabled={busy || stage4Busy !== null}
                onClick={() => void runBenchmark(true)}
              >
                {stage4Busy === "benchmark-sample" ? "Running…" : "Quick test (42 runs)"}
              </button>
              <button
                className="secondary-button"
                disabled={busy || stage4Busy !== null}
                onClick={() => void runBenchmark(false)}
              >
                {stage4Busy === "benchmark-full" ? "Running (a few minutes the first time)…" : "Full test (210 runs)"}
              </button>
            </div>
          </div>
        </div>
      </section>
      {revision && (
        <details className={styles.advanced}>
          <summary>Edit the attack by hand (JSON)</summary>
        <section className={styles.editor} aria-labelledby="editor-title">
          <div className={styles.editorHead}>
            <div>
              <h2 id="editor-title">JSON editor</h2>
              <p>
                Change any part of the attack. The server checks the credit budget and rejects
                edits that are not allowed.
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
            Attack edits (JSON)
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              spellCheck={false}
              disabled={busy}
            />
          </label>
          <div className={styles.actions}>
            <button className="secondary-button" disabled={busy} onClick={() => void previewDraft()}>
              Preview score change
            </button>
            <button className="primary-button" disabled={busy} onClick={() => void applyDraft()}>
              Apply
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
                <strong>Preview:</strong> {counterfactual.status} in{" "}
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
