"""Read-only, hash-checked artifacts. No fallback graph is manufactured here."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import TypeAdapter
from scipy.sparse import load_npz

from aegis.schemas import SybilArtifactManifest, SybilArtifactNode
from aegis.sybil import Graph, assess, reference_scale
from aegis.sybil_scenario import BaseGraph

ANCHORS = (
    "wikipedia.org",
    "w3.org",
    "ietf.org",
    "acm.org",
    "ieee.org",
    "mit.edu",
    "stanford.edu",
    "commoncrawl.org",
)
ARTIFACTS = {"nodes.json", "adjacency.npz", "reverse.npz"}
BASELINE_VERSION = "baseline-v1"  # bump when the simulated honest recommenders change


@dataclass(frozen=True)
class Dataset:
    manifest: SybilArtifactManifest
    nodes: tuple[SybilArtifactNode, ...]
    base: BaseGraph


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dataset(directory: Path) -> Dataset:
    raw = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest = SybilArtifactManifest.model_validate(raw)
    content = dict(raw)
    del content["id"]
    if hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest() != manifest.id:
        raise ValueError("Dataset manifest identity mismatch")
    if set(manifest.artifacts) != ARTIFACTS:
        raise ValueError("Dataset requires exactly nodes, forward and reverse adjacency artifacts")
    for name, digest in manifest.artifacts.items():
        if file_hash(directory / name) != digest:
            raise ValueError(f"Dataset artifact hash mismatch: {name}")
    nodes = TypeAdapter(tuple[SybilArtifactNode, ...]).validate_json(
        (directory / "nodes.json").read_bytes()
    )
    ids = tuple(v.id for v in nodes)
    if len(ids) != manifest.nodes or len(set(ids)) != len(ids):
        raise ValueError("Dataset node count or IDs are invalid")
    if len({v.domain for v in nodes}) != len(nodes):
        raise ValueError("Dataset domain labels must be unique")
    if len(set(manifest.anchors)) != 8 or not set(manifest.anchors) <= set(ids):
        raise ValueError("Dataset anchors are missing or duplicated")
    anchor_domains = {v.domain for v in nodes if v.id in manifest.anchors}
    if anchor_domains != set(ANCHORS):
        raise ValueError("Dataset does not contain the declared curated anchor set")
    matrix = load_npz(directory / "adjacency.npz").tocsr()
    reverse = load_npz(directory / "reverse.npz").tocsr()
    if matrix.shape != (len(ids), len(ids)) or reverse.shape != matrix.shape:
        raise ValueError("Adjacency dimensions do not match domain count")
    if (
        matrix.nnz != manifest.edges
        or not matrix.has_canonical_format
        or not np.all(matrix.data == 1)
    ):
        raise ValueError("Adjacency must contain unique, unit-weight observed links")
    if (matrix.T != reverse).nnz:
        raise ValueError("Reverse adjacency does not match forward links")
    included = set(manifest.extraction.included)
    if not included <= set(ids) or included & set(manifest.anchors):
        raise ValueError("Included sites must be non-anchor dataset nodes")
    named = np.array([v.id in included for v in nodes])
    kept = np.diff(matrix.indptr)
    if any(
        v.retained_outdegree != kept[i]
        or v.original_outdegree < kept[i]
        or v.depth > manifest.extraction.maximum_depth + int(named[i])
        for i, v in enumerate(nodes)
    ):
        raise ValueError("Dataset degrees or extraction depths are inconsistent")
    links = matrix.tocoo()
    sample_edges = int(np.count_nonzero(~(named[links.row] | named[links.col])))
    if (
        manifest.nodes - len(included) > manifest.extraction.node_limit
        or sample_edges > manifest.extraction.edge_limit
    ):
        raise ValueError("Dataset exceeds extraction limits")
    coordinates = matrix.tocoo()
    graph = Graph(
        len(ids),
        tuple(zip(map(int, coordinates.row), map(int, coordinates.col), strict=True)),
        tuple(v.original_outdegree for v in nodes),
    )
    anchor_indices = tuple(ids.index(a) for a in manifest.anchors)
    tau = reference_scale(graph, anchor_indices)
    if not np.isclose(tau, manifest.tau, rtol=1e-10, atol=0):
        raise ValueError("Frozen normalization does not match the clean graph")
    recommendations = baseline_recommendations(graph, anchor_indices, manifest.tau, ids)
    # The baseline is part of the scored input, so it is part of the dataset identity: old
    # revisions (scored without it) no longer apply instead of silently changing meaning.
    content_hash = hashlib.sha256(
        json.dumps([manifest.id, BASELINE_VERSION, recommendations]).encode()
    ).hexdigest()
    base = BaseGraph(
        manifest.id, content_hash, ids, graph, manifest.anchors, manifest.tau, recommendations
    )
    # Build immutable lookup structures during artifact loading, outside the edit latency budget.
    _ = base.index, base.edge_set, base.ordered_edges
    return Dataset(
        manifest,
        nodes,
        base,
    )


def baseline_recommendations(
    graph: Graph, anchors: tuple[int, ...], tau: float, ids: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """Simulated honest recommenders, chosen only from clean-graph structure.

    Shop A: 12 well-supported real websites whose combined trust is spread across the anchors.
    Shop B: the single best-supported real website whose trust comes almost entirely from one
    anchor. Without these, both shops start at zero and the playground has nothing to compare.
    """
    per = assess(graph, anchors, {}, tau).anchor_trust[: len(ids)].copy()
    per[list(anchors)] = 0
    trust = per.mean(axis=1)
    order = [int(i) for i in np.argsort(-trust, kind="stable") if trust[i] >= tau]

    def spread(total: np.ndarray) -> float:
        shares = total / total.sum()
        return float(1 / np.sum(shares**2))

    shop_a: list[int] = []
    total = np.zeros(len(anchors))
    pool = order[:3000]
    # Greedy: each pick maximizes how evenly the combined trust spans the anchors.
    for _ in range(min(12, len(pool))):
        pick = max((i for i in pool if i not in shop_a), key=lambda i: spread(total + per[i]))
        shop_a.append(pick)
        total += per[pick]
    narrow = (per.max(axis=1) / np.maximum(per.sum(axis=1), 1e-300)) >= 0.9
    shop_b = [i for i in order if i not in shop_a and narrow[i]][:1]  # small graphs may have none
    return tuple(sorted([(ids[i], "A") for i in shop_a] + [(ids[i], "B") for i in shop_b]))
