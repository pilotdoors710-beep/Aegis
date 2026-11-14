import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sybil_extract", Path(__file__).with_name("sybil_extract.py")
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_sampling_preserves_direction_original_degrees_and_depth():
    edges = {0: (2, 3, 4, 5), 1: (2, 6), 2: (7,), 3: (0,), 8: (1,)}
    reverse = {i: tuple(u for u, row in edges.items() if i in row) for i in range(9)}
    result = module.extract(
        lambda u: iter(edges.get(u, ())),
        lambda v: iter(reverse[v]),
        (0, 1),
        node_limit=9,
        edge_limit=3,
        fanout=10,
        maximum_depth=3,
    )
    assert len(result.ids) == 9
    assert len(result.edges) == 3
    assert all(v in edges.get(u, ()) for u, v in result.edges)
    assert result.original_outdegree[result.ids.index(0)] == 4
    assert sum(result.retained_outdegree) == 3
    assert result.depth[result.ids.index(8)] == 1  # Incoming neighborhood is included.
    assert result.depth[result.ids.index(7)] == 2


def test_selection_is_independent_of_adjacency_iteration_order():
    edges = {0: tuple(range(2, 200)), 1: tuple(range(100, 300))}
    a = module.extract(
        lambda u: iter(edges.get(u, ())),
        lambda v: iter(()),
        (0, 1),
        node_limit=40,
        edge_limit=20,
        fanout=30,
        seed=123,
    )
    b = module.extract(
        lambda u: reversed(edges.get(u, ())),
        lambda v: iter(()),
        (1, 0),
        node_limit=40,
        edge_limit=20,
        fanout=30,
        seed=123,
    )
    assert a == b
    assert len(a.ids) == 40
    assert len(a.edges) == 20
    assert a.original_outdegree[:2] == (198, 200)


def test_disconnected_or_small_source_is_not_padded():
    result = module.extract(lambda u: (), lambda u: (), (1, 2), node_limit=50000)
    assert result.ids == (1, 2)
    assert result.edges == ()
    assert result.original_outdegree == (0, 0)
