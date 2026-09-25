"""The longest-route search against a brute-force reference on random networks."""

import random

import pytest

from .helpers import TOPO, hex_at, make_board, make_game


def brute_force_length(game, p):
    """Try every trail edge by edge (fine for small networks)."""
    own = {e: r["kind"] for e, r in game.routes.items() if r["owner"] == p}
    at_vertex = {}
    for e in own:
        for v in TOPO.edges[e].vertices:
            at_vertex.setdefault(v, []).append(e)

    def extend(v, last, used):
        b = game.buildings.get(v)
        if b is not None and b["owner"] != p:
            return len(used)
        mixed_ok = b is not None and b["owner"] == p
        best = len(used)
        for e2 in at_vertex.get(v, ()):
            if e2 in used or (own[e2] != own[last] and not mixed_ok):
                continue
            a, c = TOPO.edges[e2].vertices
            best = max(best, extend(c if a == v else a, e2, used | {e2}))
        return best

    best = 0
    for e in own:
        a, c = TOPO.edges[e].vertices
        best = max(best, extend(c, e, frozenset([e])), extend(a, e, frozenset([e])))
    return best


def random_network(seed):
    rng = random.Random(seed)
    game = make_game(make_board(default="pasture"))
    centre = hex_at(3, 3)
    area = {centre.id} | {n for n in centre.neighbours if n is not None}
    area |= {n for h in list(area) for n in TOPO.hexes[h].neighbours if n is not None}
    edges = sorted({e for h in area for e in TOPO.hexes[h].edges if e is not None})
    for e in rng.sample(edges, rng.randint(3, 16)):
        game.routes[e] = {"owner": 0 if rng.random() < 0.85 else 1,
                          "kind": "road" if rng.random() < 0.6 else "ship", "turn": 0}
    verts = sorted({v for e in game.routes for v in TOPO.edges[e].vertices})
    for v in rng.sample(verts, rng.randint(0, min(5, len(verts)))):
        game.buildings[v] = {"owner": 0 if rng.random() < 0.6 else 1, "kind": "settlement"}
    return game


@pytest.mark.parametrize("seed", range(300))
def test_matches_brute_force(seed):
    game = random_network(seed)
    for p in (0, 1):
        assert game.route_length(p) == brute_force_length(game, p)


def test_closed_loop():
    game = make_game()
    h = hex_at(3, 3)
    for e in h.edges:
        game.routes[e] = {"owner": 0, "kind": "road", "turn": 0}
    assert game.route_length(0) == 6


def test_big_mesh_is_fast():
    """A player covering a large area with roads still gets an answer quickly."""
    import time

    game = make_game()
    for h in TOPO.inner_hexes[:30]:
        for e in h.edges:
            game.routes[e] = {"owner": 0, "kind": "road", "turn": 0}
    start = time.time()
    length = game.route_length(0)
    assert length > 30
    assert time.time() - start < 5
