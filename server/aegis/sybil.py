"""Pure structural support and sensitivity calculations (brief Â§14).

Indices have no semantics. Evaluator labels and domain names never enter this module.
The final matrix row is the absorbing outside-sample sink.
"""

from dataclasses import dataclass
from functools import cached_property
from time import perf_counter

import numpy as np
from scipy.sparse import csr_array

FORMULA_VERSION = "sybil-v1"


@dataclass(frozen=True)
class Graph:
    node_count: int
    edges: tuple[tuple[int, int], ...]
    original_outdegree: tuple[int, ...]

    @cached_property
    def canonical_edges(self) -> np.ndarray:
        links = np.asarray(self.edges, dtype=np.int64).reshape((-1, 2))
        unique = np.unique(links, axis=0)
        unique.setflags(write=False)
        return unique

    @cached_property
    def transition_matrix(self) -> csr_array:
        if self.node_count < 1 or len(self.original_outdegree) != self.node_count:
            raise ValueError("One original outdegree is required per website")
        links = self.canonical_edges
        if links.size and (links.min() < 0 or links.max() >= self.node_count):
            raise ValueError("Edge endpoint outside website graph")
        sources = links[:, 0] if links.size else np.empty(0, dtype=np.int64)
        targets = links[:, 1] if links.size else np.empty(0, dtype=np.int64)
        degree = np.bincount(sources, minlength=self.node_count)
        original = np.asarray(self.original_outdegree, dtype=np.int64)
        if np.any(original < degree) or np.any(original < 0):
            raise ValueError("Original outdegree cannot be less than retained outdegree")
        dangling = np.flatnonzero(original == 0)
        omitted = np.flatnonzero(original > degree)
        rows = np.concatenate((sources, dangling, omitted, [self.node_count]))
        cols = np.concatenate(
            (
                targets,
                dangling,
                np.full(omitted.size, self.node_count),
                [self.node_count],
            )
        )
        weights = np.concatenate(
            (
                1.0 / original[sources],
                np.ones(dangling.size),
                (original[omitted] - degree[omitted]) / original[omitted],
                [1.0],
            )
        )
        return csr_array((weights, (rows, cols)), shape=(self.node_count + 1,) * 2)

    def transition(self) -> csr_array:
        return self.transition_matrix.copy()

    def without(self, edge: tuple[int, int]) -> "Graph":
        links = set(self.edges)
        links.remove(edge)
        degree = list(self.original_outdegree)
        degree[edge[0]] -= 1  # Removed link is not an omitted observed link.
        return Graph(self.node_count, tuple(sorted(links)), tuple(degree))


@dataclass(frozen=True)
class Config:
    restart: float = 0.15
    tolerance: float = 1e-10
    max_iterations: int = 300
    weights: tuple[float, float, float, float] = (0.4, 0.2, 0.2, 0.2)

    def __post_init__(self):
        if not 0 < self.restart < 1 or not 0 < self.tolerance < 1:
            raise ValueError("Restart and tolerance must lie strictly between zero and one")
        if not 1 <= self.max_iterations <= 300:
            raise ValueError("Iteration cap must be between 1 and 300")
        if (
            len(self.weights) != 4
            or any(not np.isfinite(w) or w < 0 for w in self.weights)
            or abs(sum(self.weights) - 1) > 1e-12
        ):
            raise ValueError("Four finite nonnegative score weights must sum to one")


@dataclass(frozen=True)
class Propagation:
    mass: np.ndarray
    converged: bool
    residual: float
    iterations: int


DEFAULT_CONFIG = Config()


def _without_edge_transition(matrix: csr_array, graph: Graph, edge: tuple[int, int]) -> csr_array:
    """Remove one observed edge and renormalize only its source row."""
    source, target = edge
    original = graph.original_outdegree[source]
    if original < 1:
        raise ValueError("Cannot remove an edge from a dangling website")
    updated = matrix.copy()
    start, end = updated.indptr[source : source + 2]
    columns = updated.indices[start:end]
    target_positions = np.flatnonzero(columns == target)
    if target_positions.size != 1:
        raise ValueError("Removed edge is absent or duplicated")
    remaining_degree = original - 1
    if remaining_degree == 0:
        mutable = updated.tolil()
        mutable.rows[source] = [source]
        mutable.data[source] = [1.0]
        return mutable.tocsr()
    retained = columns != graph.node_count
    omitted = original - int(np.count_nonzero(retained))
    row = updated.data[start:end]
    row[retained] = 1.0 / remaining_degree
    row[target_positions[0]] = 0
    sink = columns == graph.node_count
    if np.any(sink):
        row[sink] = omitted / remaining_degree
    updated.eliminate_zeros()
    return updated


def propagate(matrix: csr_array, restart: np.ndarray, config: Config) -> Propagation:
    """Solve one or several restart columns using the same fixed dangling policy."""
    current = restart.copy()
    transpose = matrix.T.tocsr()
    for iteration in range(1, config.max_iterations + 1):
        updated = config.restart * restart + (1 - config.restart) * (transpose @ current)
        residual = float(np.max(np.sum(np.abs(updated - current), axis=0)))
        if not np.all(np.isfinite(updated)):
            raise ArithmeticError("Nonfinite trust propagation")
        current = updated
        if residual < config.tolerance:
            return Propagation(current, True, residual, iteration)
    return Propagation(current, False, residual, config.max_iterations)


def reference_scale(
    graph: Graph, anchors: tuple[int, ...], config: Config = DEFAULT_CONFIG
) -> float:
    result = assess(graph, anchors, {}, 1.0, config)
    if not result.propagation.converged:
        raise ValueError("Clean background did not converge")
    scores = result.trust.copy()
    scores[list(anchors)] = 0
    positive = scores[scores > 0]
    if not positive.size:
        raise ValueError("Dataset has no positive non-anchor support")
    return float(np.percentile(positive, 95))


@dataclass(frozen=True)
class ShopScore:
    count: int
    mass: float
    support: float
    effective_anchors: float
    breadth: float
    withdrawal: float
    connection: float
    total: float
    anchor_mass: tuple[float, ...]
    tested_edges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Assessment:
    trust: np.ndarray
    anchor_trust: np.ndarray
    propagation: Propagation
    scores: dict[str, ShopScore] | None
    elapsed_ms: float


def assess(
    graph: Graph,
    anchors: tuple[int, ...],
    recommendations: dict[int, tuple[str, ...]],
    tau: float,
    config: Config = DEFAULT_CONFIG,
    *,
    candidate_shops: tuple[str, ...] = (),
) -> Assessment:
    started = perf_counter()
    if len(set(anchors)) != len(anchors) or len(anchors) < 2:
        raise ValueError("At least two distinct anchors required")
    if any(not 0 <= a < graph.node_count for a in anchors):
        raise ValueError("Anchor outside website graph")
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError("Frozen normalization must be positive and finite")
    if any(not 0 <= v < graph.node_count for v in recommendations):
        raise ValueError("Recommender outside website graph")
    matrix = graph.transition()
    seeds = np.zeros((graph.node_count + 1, len(anchors)), dtype=np.float64)
    seeds[list(anchors), np.arange(len(anchors))] = 1
    result = propagate(matrix, seeds, config)
    trust = result.mass.mean(axis=1)
    scores: dict[str, ShopScore] = {}
    if not result.converged:
        return Assessment(
            trust[:-1], result.mass[:-1], result, None, (perf_counter() - started) * 1000
        )
    unique = {v: set(shops) for v, shops in recommendations.items()}
    for shop in sorted(set(candidate_shops) | {m for shops in unique.values() for m in shops}):
        supporters = sorted(v for v, shops in unique.items() if shop in shops)
        allocation = np.array([1 / len(unique[v]) for v in supporters])
        per_anchor = allocation @ result.mass[supporters]
        mass = float(np.mean(per_anchor))
        if mass <= 0:
            scores[shop] = ShopScore(
                len(supporters), 0, 0, 0, 0, 0, 0, 0, tuple(float(a) for a in per_anchor), ()
            )
            continue
        support = mass / (mass + tau)
        shares = per_anchor / per_anchor.sum()
        effective = float(1 / np.sum(shares**2))
        breadth = float(np.clip((effective - 1) / (len(anchors) - 1), 0, 1))
        withdrawn = (per_anchor.sum() - per_anchor) / (len(anchors) - 1)
        withdrawal = float(np.clip(withdrawn.min() / mass, 0, 1))
        links = graph.canonical_edges
        entering = links[np.isin(links[:, 1], supporters)]
        if entering.size:
            original = np.asarray(graph.original_outdegree)
            flows = (1 - config.restart) * trust[entering[:, 0]] / original[entering[:, 0]]
            order = np.lexsort((entering[:, 1], entering[:, 0], -flows))[:5]
            candidates = [tuple(map(int, entering[i])) for i in order]
        else:
            candidates = []
        ratios = []
        for edge in candidates:
            removed = propagate(
                _without_edge_transition(matrix, graph, edge), seeds.mean(axis=1), config
            )
            if not removed.converged:
                return Assessment(
                    trust[:-1], result.mass[:-1], removed, None, (perf_counter() - started) * 1000
                )
            ratios.append(float(allocation @ removed.mass[supporters]) / mass)
        connection = float(np.clip(min(ratios), 0, 1)) if ratios else 0.0
        w_base, w_breadth, w_withdrawal, w_connection = config.weights
        total = (
            100
            * support
            * (w_base + w_breadth * breadth + w_withdrawal * withdrawal + w_connection * connection)
        )
        scores[shop] = ShopScore(
            len(supporters),
            mass,
            support,
            effective,
            breadth,
            withdrawal,
            connection,
            total,
            tuple(float(a) for a in per_anchor),
            tuple(candidates),
        )
    return Assessment(
        trust[:-1], result.mass[:-1], result, scores, (perf_counter() - started) * 1000
    )
