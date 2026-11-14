"""Extract a pinned source using Common Crawl WebGraph and create a scoring artifact.

Run from the repository root with the server environment. Requires downloaded and hashed
sources, a JDK >=11, and the official cc-webgraph jar built from a recorded Git commit.
"""

import argparse
import gzip
import hashlib
import json
import struct
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.sparse import csr_array, save_npz
from sybil_extract import extract
from sybil_import import FILES, RELEASE, sha256, storage_check

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from aegis.sybil import Graph, reference_scale

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


def labels(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                raise ValueError("Malformed domain label row")
            yield int(fields[0]), ".".join(reversed(fields[1].split(".")))


class Adjacency:
    def __init__(self, java: str, jar: Path, basename: Path):
        self.process = subprocess.Popen(
            [
                java,
                "-Xmx4g",
                "--class-path",
                str(jar),
                str(Path(__file__).with_name("WebGraphBridge.java")),
                str(basename),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        try:
            self.nodes = struct.unpack(">i", self.read(4))[0]
        except BaseException:
            self.close()
            raise

    def read(self, size):
        chunks = bytearray()
        while len(chunks) < size:
            part = self.process.stdout.read(size - len(chunks))
            if not part:
                raise RuntimeError(
                    "WebGraph adjacency process ended before completing a response"
                )
            chunks.extend(part)
        return bytes(chunks)

    def neighbors(self, node, direction=0):
        self.process.stdin.write(struct.pack(">Bi", direction, node))
        self.process.stdin.flush()
        count = struct.unpack(">i", self.read(4))[0]
        if count < 0 or count > self.nodes:
            raise ValueError("Invalid WebGraph outdegree")
        return np.frombuffer(self.read(count * 4), dtype=">i4")

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()


def prepare(args):
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError(
            "Output already exists; choose a new immutable artifact directory"
        )
    hashes = json.loads((source / "sha256.json").read_text(encoding="utf-8"))
    for name in FILES:
        if name not in hashes or sha256(source / name) != hashes[name]:
            raise ValueError(f"Missing or mismatched source SHA-256: {name}")
    preflight = json.loads((source / "preflight.json").read_text(encoding="utf-8"))
    # Recheck allowance before offsets and extraction; the reserved allowance includes both.
    plan = storage_check(preflight["files"], source, 60 * 1024**3, 20 * 1024**3)
    if not plan["can_download"]:
        raise ValueError(f"Insufficient extraction storage: {plan}")
    basename = source / f"{RELEASE}-domain"
    for graph in (str(basename), str(basename) + "-t"):
        if not Path(graph + ".offsets").exists():
            subprocess.run(
                [
                    args.java,
                    "-Xmx4g",
                    "-cp",
                    str(args.jar.resolve()),
                    "it.unimi.dsi.webgraph.BVGraph",
                    "--offsets",
                    "--list",
                    graph,
                ],
                check=True,
            )
    label_file = source / f"{RELEASE}-domain-vertices.txt.gz"
    print("Finding curated anchors in source domain labels", flush=True)
    anchors = {name: node for node, name in labels(label_file) if name in ANCHORS}
    if set(anchors) != set(ANCHORS):
        raise ValueError(f"Curated anchors missing: {set(ANCHORS) - set(anchors)}")
    adjacency = Adjacency(args.java, args.jar.resolve(), basename)
    try:
        expected = preflight["release"]["stats"]["domain"]["nodes"]
        if adjacency.nodes != expected:
            raise ValueError("Source graph node count differs from pinned release")
        result = extract(
            adjacency.neighbors,
            lambda v: adjacency.neighbors(v, 1),
            tuple(anchors[name] for name in ANCHORS),
            node_limit=args.nodes,
            edge_limit=args.edges,
            fanout=args.fanout,
            maximum_depth=args.depth,
            seed=args.seed,
        )
    finally:
        adjacency.close()
    retained = set(result.ids)
    domains = {node: name for node, name in labels(label_file) if node in retained}
    if len(domains) != len(retained):
        raise ValueError("Missing labels in extraction")
    index = {node: i for i, node in enumerate(result.ids)}
    edges = tuple((index[u], index[v]) for u, v in result.edges)
    graph = Graph(len(result.ids), edges, result.original_outdegree)
    anchor_indices = tuple(index[anchors[name]] for name in ANCHORS)
    tau = reference_scale(graph, anchor_indices)
    output.mkdir(parents=True)
    u, v = zip(*edges, strict=True) if edges else ((), ())
    adjacency_matrix = csr_array(
        (np.ones(len(edges)), (u, v)), shape=(len(index), len(index))
    )
    save_npz(output / "adjacency.npz", adjacency_matrix)
    save_npz(output / "reverse.npz", adjacency_matrix.T.tocsr())
    nodes = [
        {
            "id": str(node),
            "domain": domains[node],
            "original_outdegree": original,
            "retained_outdegree": kept,
            "depth": depth,
            "x": float(np.cos(i * 2.399963229728653) * np.sqrt(i + 1)),
            "y": float(np.sin(i * 2.399963229728653) * np.sqrt(i + 1)),
        }
        for i, (node, original, kept, depth) in enumerate(
            zip(
                result.ids,
                result.original_outdegree,
                result.retained_outdegree,
                result.depth,
                strict=True,
            )
        )
    ]
    (output / "nodes.json").write_text(
        json.dumps(nodes, separators=(",", ":")), encoding="utf-8"
    )
    extraction = asdict(result)
    for key in ("ids", "edges", "original_outdegree", "retained_outdegree", "depth"):
        del extraction[key]
    manifest = {
        "release": RELEASE,
        "source_counts": preflight["release"]["stats"]["domain"],
        "source_sha256": hashes,
        "extraction": extraction,
        "nodes": len(nodes),
        "edges": len(edges),
        "anchors": [str(anchors[a]) for a in ANCHORS],
        "tau": tau,
        "webgraph_commit": args.webgraph_commit,
        "webgraph_jar_sha256": sha256(args.jar),
        "created_at": datetime.now(UTC).isoformat(),
        "observation_crawls": preflight["release"]["crawls"],
        "terms": preflight["terms"],
        "source_url": preflight["source"],
        "artifacts": {
            name: sha256(output / name)
            for name in ("nodes.json", "adjacency.npz", "reverse.npz")
        },
        "limitations": "Sampled website hyperlinks, including asset links; missing incoming links. "
        "Curated anchors are assumptions. No observed shop endorsements.",
    }
    manifest["id"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    # Written last: a partial output is never a loadable dataset.
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        f"Prepared {len(nodes):,} nodes, {len(edges):,} edges; tau={tau:.12g}",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--java", default="java")
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--webgraph-commit", required=True)
    parser.add_argument("--nodes", type=int, default=50000)
    parser.add_argument("--edges", type=int, default=1000000)
    parser.add_argument("--fanout", type=int, default=128)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1)
    prepare(parser.parse_args())
