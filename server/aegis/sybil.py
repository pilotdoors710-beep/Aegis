"""Pure structural support and sensitivity calculations (brief §8).

Indices have no semantics. Evaluator labels and domain names never enter this module.
The final matrix row is the absorbing outside-sample sink.
"""

from dataclasses import dataclass
from functools import cached_property
from time import perf_counter

import numpy as np
from scipy.sparse import csr_array

FORMULA_VERSION = "sybil-v2"


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
    # Outside websites cut together for E: the most a 25-credit Challenge can enlist at 2 each.
    cut_sources: int = 12

    def __post_init__(self):
        if not 0 < self.restart < 1 or not 0 < self.tolerance < 1:
            raise ValueError("Restart and tolerance must lie strictly between zero and one")
        if not 1 <= self.max_iterations <= 300:
            raise ValueError("Iteration cap must be between 1 and 300")
        if self.cut_sources < 1:
            raise ValueError("Connection test must cut at least one source")
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


def _connection_cut(
    graph: Graph, trust: np.ndarray, supporters: list[int], config: Config
) -> tuple[tuple[int, ...], list[tuple[int, int]]]:
    """E's intervention: the outside websites sending the most flow into the supporters.

    Every link from them into the supporters is cut together, so links among supporters
    and extra links bought from one website cannot pad the test. Returns the cut sources
    (highest flow first) and the links to remove.
    """
    links = graph.canonical_edges
    entering = links[np.isin(links[:, 1], supporters) & ~np.isin(links[:, 0], supporters)]
    if not entering.size:
        return (), []
    original = np.asarray(graph.original_outdegree)
    flows = (1 - config.restart) * trust[entering[:, 0]] / original[entering[:, 0]]
    sources, inverse = np.unique(entering[:, 0], return_inverse=True)
    source_flow = np.bincount(inverse, weights=flows)
    cut = sources[np.lexsort((sources, -source_flow))[: config.cut_sources]]
    edges = entering[np.isin(entering[:, 0], cut)]
    return tuple(cut.tolist()), [(u, v) for u, v in edges.tolist()]


def _without_edges_transition(
    matrix: csr_array, graph: Graph, edges: list[tuple[int, int]]
) -> csr_array:
    """Remove observed edges and renormalize only their source rows."""
    by_source: dict[int, set[int]] = {}
    for source, target in edges:
        by_source.setdefault(source, set()).add(target)
    updated = matrix.copy()
    emptied = []
    for source, targets in by_source.items():
        original = graph.original_outdegree[source]
        if original < len(targets):
            raise ValueError("Cannot remove more edges than a website has")
        start, end = updated.indptr[source : source + 2]
        columns = updated.indices[start:end]
        removed = np.isin(columns, list(targets))
        if np.count_nonzero(removed) != len(targets):
            raise ValueError("Removed edge is absent or duplicated")
        remaining_degree = original - len(targets)
        if remaining_degree == 0:
            emptied.append(source)
            continue
        sink = columns == graph.node_count
        retained = ~sink
        omitted = original - int(np.count_nonzero(retained))
        row = updated.data[start:end]
        row[retained] = 1.0 / remaining_degree
        row[removed] = 0
        row[sink] = omitted / remaining_degree
    updated.eliminate_zeros()
    if emptied:
        mutable = updated.tolil()
        for source in emptied:  # Websites left without links become dangling self-loops.
            mutable.rows[source] = [source]
            mutable.data[source] = [1.0]
        updated = mutable.tocsr()
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
    cut_sources: tuple[int, ...]  # outside websites E cut together, highest flow first


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
        cut_sources, cut_edges = _connection_cut(graph, trust, supporters, config)
        connection = 0.0
        if cut_sources:
            removed = propagate(
                _without_edges_transition(matrix, graph, cut_edges), seeds.mean(axis=1), config
            )
            if not removed.converged:
                return Assessment(
                    trust[:-1], result.mass[:-1], removed, None, (perf_counter() - started) * 1000
                )
            connection = float(np.clip(allocation @ removed.mass[supporters] / mass, 0, 1))
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
            cut_sources,
        )
    return Assessment(
        trust[:-1], result.mass[:-1], result, scores, (perf_counter() - started) * 1000
    )
