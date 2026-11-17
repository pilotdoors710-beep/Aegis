from types import SimpleNamespace

import httpx
import pytest

from aegis.config import settings
from aegis.sybil import Graph, reference_scale
from aegis.sybil_real import evaluate_real_domain
from aegis.sybil_resolver import candidates, parse_host, shared_platform
from aegis.sybil_scenario import BaseGraph
from api.main import app

DOMAINS = (
    "wikipedia.org",  # 0 anchor
    "w3.org",  # 1 anchor
    "techcrunch.com",  # 2 linked by both anchors
    "smallshop.com",  # 3 linked only by techcrunch
    "lonely.com",  # 4 no incoming links
    "myshopify.com",  # 5 platform root, linked by an anchor
)
EDGES = ((0, 2), (0, 5), (1, 2), (2, 3))
OUTDEGREE = (2, 1, 1, 0, 0, 0)


@pytest.fixture
def dataset():
    graph = Graph(len(DOMAINS), EDGES, OUTDEGREE)
    anchors = (0, 1)
    ids = tuple(str(i) for i in range(len(DOMAINS)))
    base = BaseGraph("test", "real-v1", ids, graph, ("0", "1"), reference_scale(graph, anchors))
    nodes = tuple(
        SimpleNamespace(domain=d, original_outdegree=OUTDEGREE[i], depth=min(i, 2))
        for i, d in enumerate(DOMAINS)
    )
    return SimpleNamespace(manifest=SimpleNamespace(id="d" * 64), nodes=nodes, base=base)


# --- resolver --------------------------------------------------------------------------------


def test_parse_host_normalizes_urls_and_bare_domains():
    assert parse_host("https://WWW.Example.com/a/b?q=1") == ("www.example.com", ("a", "b"))
    assert parse_host("  example.com.  ")[0] == "example.com"
    assert parse_host("bücher.de")[0] == "xn--bcher-kva.de"


@pytest.mark.parametrize("bad", ["", "localhost", "http://127.0.0.1/", "[::1]", "a..b", "-x.com"])
def test_parse_host_rejects_non_domains(bad):
    with pytest.raises(ValueError):
        parse_host(bad)


def test_candidates_walk_up_to_two_labels():
    assert candidates("shop.example.co.uk") == ("shop.example.co.uk", "example.co.uk", "co.uk")


def test_shared_platform_sellers_do_not_inherit_the_platform():
    assert shared_platform("gadgets.myshopify.com", (), "myshopify.com") == "myshopify.com"
    assert shared_platform("gadgets.myshopify.com", (), None) == "myshopify.com"
    assert shared_platform("etsy.com", ("shop", "toys"), "etsy.com") == "etsy.com"
    # The platform itself, and a seller subdomain that is its own node, are not sellers.
    assert shared_platform("www.myshopify.com", (), "myshopify.com") is None
    assert shared_platform("etsy.com", ("about",), "etsy.com") is None
    assert shared_platform("gadgets.myshopify.com", (), "gadgets.myshopify.com") is None


# --- evaluator -------------------------------------------------------------------------------


def test_scores_the_sites_own_trust_with_sybil_v2(dataset):
    result = evaluate_real_domain(dataset, "https://smallshop.com/lamp")
    assert result.status == "scored" and result.domain == "smallshop.com"
    assert result.links_in == 1 and result.top_linkers == ("techcrunch.com",)
    # Same quantity tau was frozen on: the node's own clean trust.
    assert result.scores.trust_weighted_support == pytest.approx(float(dataset.base.trust[3]))
    assert result.policy == "needs R>=60, S>=0.5, L>=0.5"
    assert {p.anchor for p in result.anchor_paths} == {"wikipedia.org", "w3.org"}
    for path in result.anchor_paths:
        assert path.hops == (path.anchor, "techcrunch.com", "smallshop.com")


def test_subdomain_matches_its_registrable_domain(dataset):
    assert evaluate_real_domain(dataset, "store.smallshop.com").domain == "smallshop.com"


def test_site_without_links_fails_without_error(dataset):
    result = evaluate_real_domain(dataset, "lonely.com")
    assert result.status == "scored"
    assert result.scores.structural_support == 0 and result.policy_passed is False
    assert result.anchor_paths == ()


def test_missing_site_is_no_evidence_not_zero(dataset):
    result = evaluate_real_domain(dataset, "not-sampled.example")
    assert result.status == "not_in_sample" and result.scores is None
    assert result.policy_passed is False and "no link evidence" in result.reason


def test_platform_seller_is_not_given_platform_trust(dataset):
    result = evaluate_real_domain(dataset, "https://gadgets.myshopify.com/")
    assert result.status == "shared_platform" and result.scores is None
    assert result.policy_passed is False


def test_anchor_is_reported_as_declared(dataset):
    result = evaluate_real_domain(dataset, "wikipedia.org")
    assert result.status == "anchor" and result.policy_passed is True
    assert result.anchor_paths[0].hops == ("wikipedia.org",)


# --- API -------------------------------------------------------------------------------------


async def test_api_evaluates_and_rejects_bad_input(monkeypatch, dataset):
    monkeypatch.setattr(settings, "sybil_enabled", True)
    monkeypatch.setattr("api.main._load_sybil_dataset", lambda _: dataset)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        ok = await client.post("/sybil/real/evaluate", json={"query": "smallshop.com"})
        bad = await client.post("/sybil/real/evaluate", json={"query": "127.0.0.1"})
    assert ok.status_code == 200 and ok.json()["domain"] == "smallshop.com"
    assert bad.status_code == 422


def test_anchor_paths_never_pass_through_another_anchor():
    # wikipedia -> w3 -> shop: w3 is the shop's anchor; wikipedia is not reported through it.
    graph = Graph(3, ((0, 1), (1, 2)), (1, 1, 0))
    base = BaseGraph("t", "real-v2", ("0", "1", "2"), graph, ("0", "1"), 1.0)
    nodes = tuple(
        SimpleNamespace(domain=d, original_outdegree=1, depth=0)
        for d in ("wikipedia.org", "w3.org", "shop.com")
    )
    data = SimpleNamespace(manifest=SimpleNamespace(id="e" * 64), nodes=nodes, base=base)
    paths = evaluate_real_domain(data, "shop.com").anchor_paths
    assert [p.hops for p in paths] == [("w3.org", "shop.com")]
