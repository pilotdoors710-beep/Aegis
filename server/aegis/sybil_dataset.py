"""Read-only, hash-checked artifacts. No fallback graph is manufactured here."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import TypeAdapter
from scipy.sparse import load_npz

from aegis.schemas import SybilArtifactManifest, SybilArtifactNode
from aegis.sybil import Graph, reference_scale
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
    kept = np.diff(matrix.indptr)
    if any(
        v.retained_outdegree != kept[i]
        or v.original_outdegree < kept[i]
        or v.depth > manifest.extraction.maximum_depth
        for i, v in enumerate(nodes)
    ):
        raise ValueError("Dataset degrees or extraction depths are inconsistent")
    if (
        manifest.nodes > manifest.extraction.node_limit
        or manifest.edges > manifest.extraction.edge_limit
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
    base = BaseGraph(manifest.id, manifest.id, ids, graph, manifest.anchors, manifest.tau)
    # Build immutable lookup structures during artifact loading, outside the edit latency budget.
    _ = base.index, base.edge_set, base.ordered_edges
    return Dataset(
        manifest,
        nodes,
        base,
    )
