import pytest

from aegis import sybil_benchmark
from aegis.sybil_benchmark import run_structural_benchmark


@pytest.fixture(scope="module")
def summary(sybil_toy):
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sybil_benchmark, "SIZES", (10, 12, 15))  # the toy graph has 21 eligible sites
        return run_structural_benchmark(sybil_toy, sample_only=True)


def test_sample_matrix_shape(summary):
    assert summary.attacks_tested == 36  # 6 families * 3 sizes * 2 credit levels * 1 seed
    assert summary.controls_tested == 6
    assert summary.total_scenarios == 42
    assert summary.unavailable == 0
    assert len({row.family for row in summary.rows}) == 6
    assert {row.family for row in summary.controls} == {"control"}


def test_families_are_distinct_attacks(summary):
    # "star" used to be generated exactly like "hub", duplicating 30 rows.
    cells = {}
    for row in summary.rows:
        key = (row.size, row.credits, row.seed)
        value = (row.recommendation_count, round(row.ordinary_pagerank, 12))
        cells.setdefault(key, set()).add(value)
    assert all(len(values) > 1 for values in cells.values())


def test_credits_used_fit_each_level(summary):
    for row in summary.rows:
        assert row.credits_used <= row.credits <= 25
        if row.family == "takeover":
            assert row.credits_used == 5 + 2 * ((row.credits - 5) // 2)


def test_rates_match_rows(summary):
    rows = summary.rows
    assert summary.count_beats_a_rate == round(sum(r.count_beats_a for r in rows) / 36, 4)
    assert summary.pagerank_beats_a_rate == round(sum(r.pagerank_beats_a for r in rows) / 36, 4)
    assert summary.policy_pass_rate == round(sum(r.passed_policy for r in rows) / 36, 4)
    assert set(summary.ablation_policy_pass_rates) == {
        "support_only",
        "no_breadth",
        "no_withdrawal",
        "no_connection",
        "no_withdrawal_floor",
    }


def test_controls_are_not_one_repeated_measurement(summary):
    # Controls used to be 30 copies of the same unattacked Shop A score.
    assert len({round(row.trust_weighted_support, 15) for row in summary.controls}) > 1
