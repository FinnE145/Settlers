import random
from collections import Counter

import pytest

from settlers.engine.board import Board, generate_board
from settlers.engine.constants import (
    FISHERY_NUMBERS,
    HARBOURS,
    LAKE,
    NUMBER_TOKENS,
    SEA,
    TILE_COUNTS,
)
from settlers.engine.topology import get_topology


@pytest.fixture(scope="module")
def topo():
    return get_topology(7, 7)


def test_topology_shape(topo):
    assert len(topo.inner_hexes) == 49
    for h in topo.inner_hexes:
        assert None not in h.corners
        assert None not in h.edges
        assert None not in h.neighbours
    # Every board vertex is shared by three hex positions (playable or frame).
    assert all(len(v.hexes) == 3 for v in topo.vertices)
    assert all(len(e.hexes) == 2 for e in topo.edges)


def test_topology_consistency(topo):
    for e in topo.edges:
        a, b = e.vertices
        assert b in topo.vertices[a].neighbours
        assert a in topo.vertices[b].neighbours
        # Both hexes beside an edge contain both of its corners.
        for h in e.hexes:
            assert a in topo.hexes[h].corners and b in topo.hexes[h].corners
    for v in topo.vertices:
        assert 2 <= len(v.edges) <= 3
        for h in v.hexes:
            assert v.id in topo.hexes[h].corners
    for h in topo.hexes:
        for k, n in enumerate(h.neighbours):
            if n is not None:
                # Neighbour relation is symmetric and shares edge k.
                assert h.id in topo.hexes[n].neighbours
                assert h.edges[k] in topo.hexes[n].edges


@pytest.mark.parametrize("seed", range(40))
def test_generated_board_is_valid(seed, topo):
    board = generate_board(random.Random(seed))
    inner = [h.id for h in topo.inner_hexes]
    frame = [h.id for h in topo.hexes if h.frame]

    assert Counter(board.terrain[h] for h in inner) == Counter(TILE_COUNTS)
    assert all(board.terrain[h] == SEA for h in frame)

    numbers = [n for n in board.numbers if n is not None]
    assert sorted(numbers) == sorted(NUMBER_TOKENS)
    for h, n in enumerate(board.numbers):
        if n is not None:
            assert board.terrain[h] not in (SEA, LAKE, "desert")

    lake = board.lake_hex
    land = [n for n in topo.hexes[lake].neighbours if board.terrain[n] != SEA]
    assert len(land) >= 3

    assert sorted(h["kind"] for h in board.harbours) == sorted(HARBOURS)
    harbour_vertices = [v for h in board.harbours for v in topo.edges[h["edge"]].vertices]
    assert len(harbour_vertices) == len(set(harbour_vertices))
    for h in board.harbours:
        assert board.terrain[h["land"]] != SEA
        assert board.terrain[h["sea"]] == SEA
        assert set(topo.edges[h["edge"]].hexes) == {h["land"], h["sea"]}

    sea_hosts = [h["sea"] for h in board.harbours] + [f["hex"] for f in board.fisheries]
    assert len(sea_hosts) == len(set(sea_hosts))

    assert sorted(f["number"] for f in board.fisheries) == sorted(FISHERY_NUMBERS)
    fishery_vertices = [v for f in board.fisheries for v in f["vertices"]]
    assert len(fishery_vertices) == len(set(fishery_vertices))
    for f in board.fisheries:
        assert board.terrain[f["hex"]] == SEA
        for v in f["vertices"]:
            assert v in topo.hexes[f["hex"]].corners
            assert any(board.terrain[h] != SEA for h in topo.vertices[v].hexes)


def test_board_roundtrip():
    board = generate_board(random.Random(7))
    again = Board.from_dict(board.to_dict())
    assert again.to_dict() == board.to_dict()


def test_boards_differ():
    a = generate_board(random.Random(1))
    b = generate_board(random.Random(2))
    assert a.terrain != b.terrain
