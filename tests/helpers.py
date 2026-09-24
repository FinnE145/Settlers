"""Builders for hand-made boards and games in known states."""

import random

from settlers.engine.board import Board
from settlers.engine.constants import RESOURCES, SEA
from settlers.engine.game import Game
from settlers.engine.topology import get_topology

TOPO = get_topology(7, 7)


class Dice(random.Random):
    """A Random whose randint() returns queued values (for dice), everything else seeded."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.queue = []

    def roll(self, a, b):
        self.queue += [a, b]

    def randint(self, lo, hi):
        if self.queue:
            return self.queue.pop(0)
        return super().randint(lo, hi)


def hex_at(col, row):
    return next(h for h in TOPO.hexes if h.col == col and h.row == row)


def make_board(default="pasture", terrain=None, numbers=None, fisheries=None, harbours=None):
    """Every playable hex is ``default`` unless overridden by ``terrain`` {hex id: kind}."""
    t = [SEA if h.frame else default for h in TOPO.hexes]
    for hid, kind in (terrain or {}).items():
        t[hid] = kind
    n = [None] * len(TOPO.hexes)
    for hid, num in (numbers or {}).items():
        n[hid] = num
    return Board(7, 7, t, n, harbours or [], fisheries or [])


def make_game(board=None, rng=None, play=True):
    game = Game(board or make_board(), first_player=0, rng=rng or Dice())
    if play:
        game.phase = "play"
        game.current = 0
        game.turn_number = 1
    return game


def give(game, p, **cards):
    for r, n in cards.items():
        assert r in RESOURCES
        game.players[p]["hand"][r] += n


def place(game, p, vertex=None, kind="settlement", edges=(), route="road"):
    if vertex is not None:
        game.buildings[vertex] = {"owner": p, "kind": kind}
    for e in edges:
        game.routes[e] = {"owner": p, "kind": route, "turn": 0}


def edge_between(a, b):
    return next(e.id for e in TOPO.edges if set(e.vertices) == {a, b})


def path_edges(start, length, avoid=()):
    """A simple path of ``length`` edges starting at vertex ``start``."""
    edges, verts, v = [], [start], start
    for _ in range(length):
        nxt = next(n for n in TOPO.vertices[v].neighbours if n not in verts and n not in avoid)
        edges.append(edge_between(v, nxt))
        verts.append(nxt)
        v = nxt
    return edges, verts
