"""Benchmark validated real-data Sybil scoring and publish raw timings."""

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from aegis.sybil import assess
from aegis.sybil_dataset import load_dataset


def percentile(values: list[float], value: float) -> float:
    return float(np.percentile(values, value))


def benchmark(directory: Path, repeats: int) -> dict:
    if repeats < 1:
        raise ValueError("At least one benchmark repeat is required")
    started = perf_counter()
    dataset = load_dataset(directory)
    load_ms = (perf_counter() - started) * 1000
    base = dataset.base
    index = {node: i for i, node in enumerate(base.ids)}
    anchors = tuple(index[node] for node in base.anchors)

    propagation_times = []
    baseline = None
    for _ in range(repeats):
        result = assess(base.graph, anchors, {}, base.tau)
        if not result.propagation.converged or result.scores is None:
            raise RuntimeError("Clean real-data propagation did not converge")
        propagation_times.append(result.elapsed_ms)
        baseline = result
    assert baseline is not None

    anchor_set = set(anchors)
    has_incoming = {v for _, v in base.graph.edges}
    supporters = sorted(
        (
            i
            for i, mass in enumerate(baseline.trust)
            if i not in anchor_set and i in has_incoming and mass > 0
        ),
        key=lambda i: (-baseline.trust[i], i),
    )[:100]
    if not supporters:
        raise RuntimeError("Real-data benchmark has no positive non-anchor supporters")
    recommendations = {i: ("A",) for i in supporters}
    full_times = []
    score = None
    for _ in range(repeats):
        result = assess(
            base.graph,
            anchors,
            recommendations,
            base.tau,
            candidate_shops=("A", "B"),
        )
        if not result.propagation.converged or result.scores is None:
            raise RuntimeError("Full real-data assessment did not converge")
        full_times.append(result.elapsed_ms)
        score = result.scores["A"]
    assert score is not None and len(score.tested_edges) <= 5

    propagation_p95 = percentile(propagation_times, 95)
    full_p95 = percentile(full_times, 95)
    return {
        "kind": "sybil-real-data-performance-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "id": dataset.manifest.id,
            "release": dataset.manifest.release,
            "nodes": dataset.manifest.nodes,
            "edges": dataset.manifest.edges,
            "tau": dataset.manifest.tau,
            "extraction": dataset.manifest.extraction.model_dump(mode="json"),
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "repeats": repeats,
        "artifact_load_ms": load_ms,
        "propagation_only_ms": propagation_times,
        "full_assessment_ms": full_times,
        "summary": {
            "propagation_p50_ms": percentile(propagation_times, 50),
            "propagation_p95_ms": propagation_p95,
            "full_p50_ms": percentile(full_times, 50),
            "full_p95_ms": full_p95,
            "propagation_p95_target_ms": 1000,
            "full_p95_target_ms": 5000,
            "propagation_target_passed": propagation_p95 < 1000,
            "full_target_passed": full_p95 < 5000,
        },
        "workload": {
            "supporters": len(supporters),
            "tested_edges": len(score.tested_edges),
            "score": score.total,
            "converged": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--enforce-targets", action="store_true")
    args = parser.parse_args()
    report = benchmark(args.directory.resolve(), args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if args.enforce_targets and not all(
        (
            report["summary"]["propagation_target_passed"],
            report["summary"]["full_target_passed"],
        )
    ):
        raise SystemExit("Sybil real-data performance tier failed")


if __name__ == "__main__":
    main()
