"""Bounded scenario catalog, graph views, and one-process numerical assessment queue."""

import asyncio
import hashlib
import math
import multiprocessing
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

from aegis.schemas import (
    SybilAssessmentRecord,
    SybilGraphEdge,
    SybilGraphNode,
    SybilGraphView,
    SybilLink,
    SybilRecommendation,
    SybilScenarioCreate,
    SybilShopScore,
)
from aegis.sybil import FORMULA_VERSION
from aegis.sybil_dataset import Dataset, load_dataset
from aegis.sybil_scenario import AppliedScenario, apply, assess_scenario


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


class SybilRuntime:
    def __init__(self, queue_limit: int = 20):
        self.scenarios: dict[str, AppliedScenario] = {}
        self.assessments: dict[str, SybilAssessmentRecord] = {}
        self._tasks: set[asyncio.Task] = set()
        self._executor: ProcessPoolExecutor | None = None
        self._worker_slot = asyncio.Semaphore(1)
        self._queue_limit = queue_limit

    def create(self, dataset: Dataset, edits: SybilScenarioCreate) -> AppliedScenario:
        scenario = apply(dataset.base, edits)
        self.scenarios.setdefault(scenario.revision.id, scenario)
        return self.scenarios[scenario.revision.id]

    def get(self, revision_id: str) -> AppliedScenario | None:
        return self.scenarios.get(revision_id)

    def view(self, dataset: Dataset, scenario: AppliedScenario, limit: int) -> SybilGraphView:
        base_count = len(dataset.nodes)
        required = list(scenario.anchors)
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

    async def _run(self, directory: str, scenario: AppliedScenario, assessment_id: str) -> None:
        async with self._worker_slot:
            self.assessments[assessment_id] = self.assessments[assessment_id].model_copy(
                update={"status": "running"}
            )
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

    def assessment(self, assessment_id: str) -> SybilAssessmentRecord | None:
        return self.assessments.get(assessment_id)

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
