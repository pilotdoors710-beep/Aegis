import pytest

from aegis.sybil import Graph
from aegis.sybil_benchmark import run_structural_benchmark
from aegis.sybil_scenario import BaseGraph


@pytest.fixture
def base():
    return BaseGraph(
        "test",
        "hash-v1",
        ("a", "b", "c", "d"),
        Graph(4, ((0, 2), (1, 2)), (2, 1, 0, 0)),
        ("a", "b"),
        0.1,
        (("c", "A"),),
    )


def test_structural_benchmark_sample(base):
    summary = run_structural_benchmark(base, sample_only=True)
    assert summary.attacks_tested == 36  # 6 families * 3 sizes * 2 credit levels * 1 seed
    assert summary.controls_tested == 6
    assert summary.total_scenarios == 42
    assert len(summary.rows) == 36
    assert 0 <= summary.naive_pass_rate <= 1.0
    assert 0 <= summary.aegis_pass_rate <= 1.0
    assert summary.elapsed_s >= 0
