"""Bounded scenario catalog, graph views, and one-process numerical assessment queue."""

import asyncio
import hashlib
import logging
import math
import multiprocessing
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

from aegis.schemas import (
    SybilAssessmentRecord,
    SybilCounterfactualResult,
    SybilGraphEdge,
    SybilGraphEvidence,
    SybilGraphNode,
    SybilGraphView,
    SybilLink,
    SybilRecommendation,
    SybilScenarioCreate,
    SybilScoreDelta,
    SybilShopEvidence,
    SybilShopScore,
)
from aegis.sybil import FORMULA_VERSION
from aegis.sybil_dataset import Dataset, load_dataset
from aegis.sybil_scenario import AppliedScenario, apply, assess_scenario

log = logging.getLogger("aegis.sybil")


@lru_cache(maxsize=1)
def _worker_dataset(directory: str) -> Dataset:
    return load_dataset(Path(directory))


def calculate_assessment(directory: str, edits_json: str) -> dict:
    """Process-pool entrypoint; the worker retains one validated read-only dataset."""
    dataset = _worker_dataset(directory)
    scenario = apply(dataset.base, SybilScenarioCreate.model_validate_json(edits_json))
    assessment = assess_scenario(dataset.base, scenario)
    assessment_id = assessment_identity(scenario.revision.id)
    if assessment.scores is None:
        return SybilAssessmentRecord(
            id=assessment_id,
            revision_id=scenario.revision.id,
            status="unavailable",
            converged=False,
            residual=assessment.propagation.residual,
            iterations=assessment.propagation.iterations,
            elapsed_ms=assessment.elapsed_ms,
            reason="Trust propagation did not converge; this result cannot pass graph policy.",
        ).model_dump(mode="json")
    scores = {}
    for shop, score in assessment.scores.items():
        scores[shop] = SybilShopScore(
            recommendation_count=score.count,
            trust_weighted_support=score.mass,
            structural_support=score.support,
            effective_anchors=score.effective_anchors,
            anchor_breadth=score.breadth,
            anchor_withdrawal_resilience=score.withdrawal,
            tested_connection_resilience=score.connection,
            total_robustness=score.total,
            tested_edges=tuple(
                SybilLink(source=scenario.ids[u], target=scenario.ids[v])
                for u, v in score.tested_edges
            ),
        )
    return SybilAssessmentRecord(
        id=assessment_id,
        revision_id=scenario.revision.id,
        status="complete",
        converged=True,
        residual=assessment.propagation.residual,
        iterations=assessment.propagation.iterations,
        elapsed_ms=assessment.elapsed_ms,
        scores=scores,
    ).model_dump(mode="json")


def assessment_identity(revision_id: str) -> str:
    return hashlib.sha256(f"{FORMULA_VERSION}:{revision_id}".encode()).hexdigest()


def graph_evidence(assessment: SybilAssessmentRecord) -> SybilGraphEvidence:
    if assessment.status != "complete" or assessment.scores is None:
        raise ValueError("A complete converged assessment is required for graph evidence")
    return SybilGraphEvidence(
        revision_id=assessment.revision_id,
        assessment_id=assessment.id,
        shops={
            shop: SybilShopEvidence(
                recommendation_count=score.recommendation_count,
                structural_support=score.structural_support,
                anchor_breadth=score.anchor_breadth,
                anchor_withdrawal_resilience=score.anchor_withdrawal_resilience,
                tested_connection_resilience=score.tested_connection_resilience,
                total_robustness=score.total_robustness,
                policy_passed=(
                    score.total_robustness >= 60 and score.structural_support >= 0.5
                ),
            )
            for shop, score in assessment.scores.items()
        },
    )


def calculate_counterfactual(
    directory: str,
    baseline_json: str,
    counterfactual_json: str,
    baseline_assessment_json: str | None = None,
) -> dict:
    """Process-pool entrypoint for revision-correct score and rank deltas."""
    started = time.perf_counter()
    before = (
        SybilAssessmentRecord.model_validate_json(baseline_assessment_json).model_dump(mode="json")
        if baseline_assessment_json
        else calculate_assessment(directory, baseline_json)
    )
    after = calculate_assessment(directory, counterfactual_json)
    before_scores, after_scores = before.get("scores"), after.get("scores")
    elapsed_ms = (time.perf_counter() - started) * 1000
    if before_scores is None or after_scores is None:
        return SybilCounterfactualResult(
            baseline_revision_id=before["revision_id"],
            counterfactual_revision_id=after["revision_id"],
            status="unavailable",
            elapsed_ms=elapsed_ms,
            reason="Both revisions must converge before deltas are available.",
        ).model_dump(mode="json")

    def rank(scores: dict, shop: str) -> int:
        total = scores[shop]["total_robustness"]
        return 1 + sum(score["total_robustness"] > total for score in scores.values())

    deltas = {}
    for shop in ("A", "B"):
        old, new = before_scores[shop], after_scores[shop]
        deltas[shop] = SybilScoreDelta(
            trust_weighted_support=new["trust_weighted_support"]
            - old["trust_weighted_support"],
            structural_support=new["structural_support"] - old["structural_support"],
            anchor_breadth=new["anchor_breadth"] - old["anchor_breadth"],
            anchor_withdrawal_resilience=new["anchor_withdrawal_resilience"]
            - old["anchor_withdrawal_resilience"],
            tested_connection_resilience=new["tested_connection_resilience"]
            - old["tested_connection_resilience"],
            total_robustness=new["total_robustness"] - old["total_robustness"],
            rank=rank(after_scores, shop) - rank(before_scores, shop),
        )
    return SybilCounterfactualResult(
        baseline_revision_id=before["revision_id"],
        counterfactual_revision_id=after["revision_id"],
        status="complete",
        elapsed_ms=elapsed_ms,
        deltas=deltas,
    ).model_dump(mode="json")


class SybilRuntime:
    def __init__(self, queue_limit: int = 20):
        self.scenarios: dict[str, AppliedScenario] = {}
        self.assessments: dict[str, SybilAssessmentRecord] = {}
        self._tasks: set[asyncio.Task] = set()
        self._executor: ProcessPoolExecutor | None = None
        self._worker_slot = asyncio.Semaphore(1)
        self._queue_limit = queue_limit
        self.on_assessment: Callable[[SybilAssessmentRecord], Awaitable[None]] | None = None

    def create(self, dataset: Dataset, edits: SybilScenarioCreate) -> AppliedScenario:
        scenario = apply(dataset.base, edits)
        self.scenarios.setdefault(scenario.revision.id, scenario)
        return self.scenarios[scenario.revision.id]

    def get(self, revision_id: str) -> AppliedScenario | None:
        return self.scenarios.get(revision_id)

    def view(self, dataset: Dataset, scenario: AppliedScenario, limit: int) -> SybilGraphView:
        base_count = len(dataset.nodes)
        required = list(scenario.anchors)
        # Real recommenders first: a large attack must not push the honest ones out of view.
        required.extend(i for i, _ in scenario.recommendations if i < base_count)
        # Real bridge sources before injected nodes, so a big attack cannot crowd them out.
        index = dataset.base.index
        required.extend(
            index[link.source]
            for link in scenario.revision.edits.cooperating_links
            if link.source in index
        )
        required.extend(range(base_count, len(scenario.ids)))
        visible_indices = list(dict.fromkeys(required))[:limit]
        if len(visible_indices) < limit:
            selected = set(visible_indices)
            visible_indices.extend(i for i in range(base_count) if i not in selected)
            visible_indices = visible_indices[:limit]
        visible = set(visible_indices)
        edges = [edge for edge in scenario.graph.edges if edge[0] in visible and edge[1] in visible]
        edges = edges[:20000]
        retained = Counter(u for u, _ in scenario.graph.edges)
        added = {(edge.source, edge.target) for edge in scenario.revision.edits.added_links}
        nodes = []
        for i in visible_indices:
            if i < base_count:
                source = dataset.nodes[i]
                label, provenance = source.domain, "observed"
                x, y = source.x, source.y
            else:
                source = None
                label = scenario.ids[i]
                provenance = "simulated"
                angle = i * 2.399963229728653
                x, y = math.cos(angle) * math.sqrt(i + 1), math.sin(angle) * math.sqrt(i + 1)
            nodes.append(
                SybilGraphNode(
                    id=scenario.ids[i],
                    label=label,
                    provenance=provenance,
                    anchor=i in scenario.anchors,
                    original_outdegree=scenario.graph.original_outdegree[i],
                    retained_outdegree=retained[i],
                    x=x,
                    y=y,
                )
            )
        recommendations = tuple(
            SybilRecommendation(website=scenario.ids[i], shop=shop)
            for i, shops in scenario.recommendations
            if i in visible
            for shop in shops
        )
        return SybilGraphView(
            revision_id=scenario.revision.id,
            total_nodes=scenario.graph.node_count,
            total_edges=len(scenario.graph.edges),
            displayed_nodes=len(nodes),
            displayed_edges=len(edges),
            nodes=tuple(nodes),
            edges=tuple(
                SybilGraphEdge(
                    source=scenario.ids[u],
                    target=scenario.ids[v],
                    provenance=(
                        "simulated" if (scenario.ids[u], scenario.ids[v]) in added else "observed"
                    ),
                )
                for u, v in edges
            ),
            recommendations=recommendations,
            subset=len(nodes) < scenario.graph.node_count or len(edges) < len(scenario.graph.edges),
        )

    def submit(self, directory: str, scenario: AppliedScenario) -> SybilAssessmentRecord:
        assessment_id = assessment_identity(scenario.revision.id)
        if existing := self.assessments.get(assessment_id):
            return existing
        active = sum(v.status in ("queued", "running") for v in self.assessments.values())
        if active >= self._queue_limit:
            raise OverflowError(
                "Graph assessment queue is full; retry after an active job finishes"
            )
        record = SybilAssessmentRecord(
            id=assessment_id, revision_id=scenario.revision.id, status="queued"
        )
        self.assessments[assessment_id] = record
        if self._executor is None:
            self._executor = ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn")
            )
        task = asyncio.create_task(self._run(directory, scenario, assessment_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    async def counterfactual(
        self, directory: str, baseline: AppliedScenario, proposed: AppliedScenario
    ) -> SybilCounterfactualResult:
        if self._executor is None:
            self._executor = ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn")
            )
        async with self._worker_slot:
            assert self._executor is not None
            started = time.perf_counter()
            try:
                baseline_assessment = self.assessments.get(
                    assessment_identity(baseline.revision.id)
                )
                raw = await asyncio.get_running_loop().run_in_executor(
                    self._executor,
                    calculate_counterfactual,
                    directory,
                    baseline.revision.edits.model_dump_json(),
                    proposed.revision.edits.model_dump_json(),
                    (
                        baseline_assessment.model_dump_json()
                        if baseline_assessment is not None
                        and baseline_assessment.status == "complete"
                        else None
                    ),
                )
            except Exception as error:
                return SybilCounterfactualResult(
                    baseline_revision_id=baseline.revision.id,
                    counterfactual_revision_id=proposed.revision.id,
                    status="unavailable",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    reason=f"Counterfactual worker failed: {type(error).__name__}",
                )
        return SybilCounterfactualResult.model_validate(raw)

    async def _run(self, directory: str, scenario: AppliedScenario, assessment_id: str) -> None:
        async with self._worker_slot:
            self.assessments[assessment_id] = self.assessments[assessment_id].model_copy(
                update={"status": "running"}
            )
            await self._persist(assessment_id)
            try:
                assert self._executor is not None
                raw = await asyncio.get_running_loop().run_in_executor(
                    self._executor,
                    calculate_assessment,
                    directory,
                    scenario.revision.edits.model_dump_json(),
                )
                self.assessments[assessment_id] = SybilAssessmentRecord.model_validate(raw)
            except Exception as error:
                self.assessments[assessment_id] = SybilAssessmentRecord(
                    id=assessment_id,
                    revision_id=scenario.revision.id,
                    status="unavailable",
                    reason=f"Assessment worker failed: {type(error).__name__}",
                )
            await self._persist(assessment_id)

    def assessment(self, assessment_id: str) -> SybilAssessmentRecord | None:
        return self.assessments.get(assessment_id)

    def remember_assessment(self, assessment: SybilAssessmentRecord) -> None:
        self.assessments[assessment.id] = assessment

    async def _persist(self, assessment_id: str) -> None:
        if self.on_assessment is not None:
            try:
                await self.on_assessment(self.assessments[assessment_id])
            except Exception as error:
                log.warning("persist Sybil assessment failed: %s", error)

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
