import pytest
from pydantic import ValidationError

from aegis.schemas import SybilGenerate, SybilLink, SybilRecommendation, SybilScenarioCreate
from aegis.sybil import Graph, assess
from aegis.sybil_scenario import BaseGraph, apply, assess_scenario, generate


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


def edit(**kwargs):
    return SybilScenarioCreate(dataset_id="test", **kwargs)


def link(u, v):
    return SybilLink(source=u, target=v)


def test_canonical_order_duplicates_and_noops(base):
    a = apply(
        base,
        edit(
            injected_nodes=("sim:2", "sim:1"), added_links=(link("sim:1", "sim:2"), link("a", "c"))
        ),
    )
    b = apply(
        base,
        edit(
            injected_nodes=("sim:1", "sim:2", "sim:1"),
            added_links=(link("sim:1", "sim:2"), link("sim:1", "sim:2")),
        ),
    )
    assert a == b
    assert a.graph.original_outdegree == (2, 1, 0, 0, 1, 0)
    assert a.graph.transition()[0, 6] == 0.5  # Omitted source probability survives editing.
    assert a.revision.budget.internal_links == 1
    with pytest.raises(ValidationError):
        a.revision.id = "changed"


def test_cooperation_budget_and_refund(base):
    attack = edit(
        injected_nodes=("sim:1",),
        added_links=(link("c", "sim:1"),),
        cooperating_links=(link("c", "sim:1"),),
    )
    assert apply(base, attack).revision.budget.external_credits == 2
    clean = apply(base, edit(injected_nodes=("sim:1",)))
    assert clean.revision.budget.external_credits == 0
    assert apply(base, attack).revision.budget.external_credits == 2


def test_compromise_cost_and_relationship_cap(base):
    assert apply(base, edit(compromised=("a", "c", "c"))).revision.budget.external_credits == 20
    with pytest.raises(ValueError, match="budget"):
        apply(base, edit(compromised=("a", "b")))
    with pytest.raises(ValueError, match="100 changed"):
        apply(
            base,
            edit(
                compromised=("c",),
                injected_nodes=tuple(f"sim:{i}" for i in range(101)),
                added_links=tuple(link("c", f"sim:{i}") for i in range(101)),
            ),
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"added_links": (link("c", "d"),)},
        {"removed_links": (link("a", "c"),)},
        {"added_links": (link("c", "unknown"),)},
        {"recommendations": (SybilRecommendation(website="c", shop="B"),)},
        {"anchors": ("a", "c")},
        {"restart": 0.2},
        {"injected_nodes": ("a",)},
        {"removed_links": (link("c", "d"),)},
        {"cooperating_links": (link("c", "d"),)},
    ],
)
def test_forbidden_edits(base, kwargs):
    with pytest.raises(ValueError):
        apply(base, edit(**kwargs))


def test_compromise_intervention_changes_outdegree_not_sink_omission(base):
    scenario = apply(base, edit(compromised=("a",), removed_links=(link("a", "c"),)))
    assert scenario.graph.original_outdegree[0] == 1
    assert scenario.graph.transition()[0, 4] == 1
    assert base.graph.original_outdegree[0] == 2


def test_generated_disconnected_support_and_cooperative_bridge(base):
    attack = generate("test", SybilGenerate(count=100, pattern="hub", seed=7))
    assert attack == generate("test", SybilGenerate(count=100, pattern="hub", seed=7))
    scenario = apply(base, attack)
    result = assess(scenario.graph, scenario.anchors, dict(scenario.recommendations), base.tau)
    assert result.scores["B"].count == 100
    assert result.scores["B"].total == 0
    bridge = link("c", "sim:7-0")
    connected = apply(
        base,
        attack.model_copy(
            update={
                "added_links": (*attack.added_links, bridge),
                "cooperating_links": (bridge,),
            }
        ),
    )
    result = assess(connected.graph, connected.anchors, dict(connected.recommendations), base.tau)
    assert result.scores["B"].mass > 0
    assert connected.revision.id != scenario.revision.id
    assert connected.revision.budget.external_credits == 2


def test_research_background_edits_and_anchors_are_separate(base):
    research = apply(
        base, edit(mode="research", added_links=(link("c", "d"),), anchors=("c", "d"), restart=0.2)
    )
    assert research.anchors == (2, 3)
    assert research.revision.edits.mode == "research"
    assert research.revision.id != apply(base, edit()).revision.id


@pytest.mark.parametrize("pattern", ["dense", "clusters", "hub", "chain"])
def test_generation_is_reproducible_and_bounded(base, pattern):
    config = SybilGenerate(count=10, seed=123, pattern=pattern, density=1)
    scenario = apply(base, generate("test", config))
    assert scenario == apply(base, generate("test", config))
    assert scenario.revision.budget.injected_websites == 10
    assert scenario.revision.budget.external_credits == 0
    if pattern == "chain":
        assert scenario.revision.budget.internal_links == 9
    if pattern == "hub":
        assert scenario.revision.budget.internal_links == 18


def test_generation_rejects_over_budget_instead_of_clipping():
    with pytest.raises(ValueError, match="100,000"):
        generate("test", SybilGenerate(count=1000, density=1))


def test_research_settings_reach_engine_without_ownership(base):
    from aegis.schemas import SybilWeights

    scenario = apply(
        base,
        edit(
            mode="research",
            restart=0.2,
            weights=SybilWeights(base=1, breadth=0, withdrawal=0, connection=0),
        ),
    )
    score = assess_scenario(base, scenario).scores["A"]
    assert score.total == pytest.approx(100 * score.support)
    assert assess_scenario(base, scenario).scores["B"].total == 0


def test_generation_with_bridges(base):
    config = SybilGenerate(count=10, seed=1, pattern="dense", bridges=2)
    attack = generate("test", config, base)
    scenario = apply(base, attack)
    assert scenario.revision.budget.external_credits == 4
    assert len(scenario.revision.edits.cooperating_links) == 2


def test_bridges_raise_target_support(base):
    def support(bridges):
        config = SybilGenerate(count=10, seed=1, pattern="dense", bridges=bridges)
        return assess_scenario(base, apply(base, generate("test", config, base))).scores["B"].mass

    assert support(1) > support(0)
