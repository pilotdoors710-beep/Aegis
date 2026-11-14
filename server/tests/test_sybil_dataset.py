import hashlib
import json

import numpy as np
import pytest
from scipy.sparse import csr_array, save_npz

from aegis.sybil import Graph, reference_scale
from aegis.sybil_dataset import ANCHORS, file_hash, load_dataset


def sign(path, manifest):
    manifest.pop("id", None)
    manifest["id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def artifact(tmp_path):
    # Analytical fixture only. It never enters the deployed dataset catalog.
    graph = Graph(9, tuple((i, 8) for i in range(8)), (1,) * 8 + (0,))
    matrix = csr_array((np.ones(8), (range(8), [8] * 8)), shape=(9, 9))
    save_npz(tmp_path / "adjacency.npz", matrix)
    save_npz(tmp_path / "reverse.npz", matrix.T.tocsr())
    nodes = [
        {
            "id": str(i),
            "domain": domain,
            "original_outdegree": int(i < 8),
            "retained_outdegree": int(i < 8),
            "depth": int(i == 8),
            "x": i,
            "y": 0,
        }
        for i, domain in enumerate((*ANCHORS, "fixture.invalid"))
    ]
    (tmp_path / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    manifest = {
        "release": "cc-main-2026-aug-sep-oct",
        "source_counts": {"nodes": 134979706, "arcs": 1817202146},
        "source_sha256": {},
        "extraction": {
            "seed": 1,
            "fanout": 128,
            "maximum_depth": 4,
            "node_limit": 50000,
            "edge_limit": 1000000,
            "version": "seeded-neighborhood-v1",
        },
        "nodes": 9,
        "edges": 8,
        "anchors": list(map(str, range(8))),
        "tau": reference_scale(graph, tuple(range(8))),
        "webgraph_commit": "0" * 40,
        "webgraph_jar_sha256": "0" * 64,
        "created_at": "2026-11-15T00:00:00Z",
        "observation_crawls": ["CC-MAIN-2026-34", "CC-MAIN-2026-39", "CC-MAIN-2026-43"],
        "terms": "https://commoncrawl.org/terms-of-use",
        "source_url": "https://index.commoncrawl.org/graphinfo.json",
        "artifacts": {
            name: file_hash(tmp_path / name)
            for name in ("nodes.json", "adjacency.npz", "reverse.npz")
        },
        "limitations": "Analytical test fixture, never a real dataset.",
    }
    sign(tmp_path, manifest)
    return tmp_path, manifest


def test_valid_artifact_retains_real_ids_degrees_and_anchors(artifact):
    path, manifest = artifact
    dataset = load_dataset(path)
    assert dataset.base.dataset_id == manifest["id"]
    assert dataset.base.graph.edges == tuple((i, 8) for i in range(8))
    assert dataset.base.anchors == tuple(map(str, range(8)))
    assert dataset.base.recommendations == ()


def test_missing_manifest_is_not_a_ready_dataset(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path)


def test_artifact_hash_mismatch_is_rejected(artifact):
    path, _ = artifact
    (path / "nodes.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset(path)


def test_manifest_identity_is_checked(artifact):
    path, manifest = artifact
    manifest["tau"] = 10
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        load_dataset(path)


def test_normalization_is_recomputed_before_readiness(artifact):
    path, manifest = artifact
    manifest["tau"] *= 2
    sign(path, manifest)
    with pytest.raises(ValueError, match="normalization"):
        load_dataset(path)


def test_reverse_graph_must_match(artifact):
    path, manifest = artifact
    save_npz(path / "reverse.npz", csr_array((9, 9)))
    manifest["artifacts"]["reverse.npz"] = file_hash(path / "reverse.npz")
    sign(path, manifest)
    with pytest.raises(ValueError, match="Reverse adjacency"):
        load_dataset(path)


def test_anchor_identity_is_checked(artifact):
    path, manifest = artifact
    nodes = json.loads((path / "nodes.json").read_text(encoding="utf-8"))
    nodes[0]["domain"] = "wrong.invalid"
    (path / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    manifest["artifacts"]["nodes.json"] = file_hash(path / "nodes.json")
    sign(path, manifest)
    with pytest.raises(ValueError, match="curated anchor"):
        load_dataset(path)
