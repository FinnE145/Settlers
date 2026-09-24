"""Board layout (terrain, numbers, harbours, fisheries) and random generation."""

from __future__ import annotations

import random

from .constants import (
    BOARD_COLS,
    BOARD_ROWS,
    FISHERY_NUMBERS,
    GOLD,
    HARBOURS,
    LAKE,
    LAKE_MIN_LAND_NEIGHBOURS,
    LAKE_NUMBERS,
    NUMBER_TOKENS,
    SEA,
    TERRAIN_RESOURCE,
    TILE_COUNTS,
)
from .topology import Topology, get_topology


class Board:
    """A generated board. Frame hexes always have terrain ``sea``.

    harbours:  [{"edge", "kind", "land", "sea"}]  kind is "3:1" or a resource name
    fisheries: [{"hex", "corner", "number", "vertices"}]  a chevron in a sea hex
               pointing at ``corner``, touching that corner and the two beside it
    """

    def __init__(self, cols, rows, terrain, numbers, harbours, fisheries):
        self.cols = cols
        self.rows = rows
        self.terrain: list[str] = terrain
        self.numbers: list[int | None] = numbers
        self.harbours: list[dict] = harbours
        self.fisheries: list[dict] = fisheries

    @property
    def topology(self) -> Topology:
        return get_topology(self.cols, self.rows)

    def is_sea(self, hex_id: int) -> bool:
        return self.terrain[hex_id] == SEA

    def is_land(self, hex_id: int) -> bool:
        return self.terrain[hex_id] != SEA

    @property
    def lake_hex(self) -> int | None:
        return self.terrain.index(LAKE) if LAKE in self.terrain else None

    def to_dict(self) -> dict:
        return {
            "cols": self.cols,
            "rows": self.rows,
            "terrain": self.terrain,
            "numbers": self.numbers,
            "harbours": self.harbours,
            "fisheries": self.fisheries,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Board":
        return cls(d["cols"], d["rows"], d["terrain"], d["numbers"], d["harbours"], d["fisheries"])

    def client_view(self) -> dict:
        """Everything the client needs to draw the board."""
        view = self.topology.to_dict()
        view.update(self.to_dict())
        view["lake_numbers"] = list(LAKE_NUMBERS)
        return view


class BoardGenerationError(RuntimeError):
    pass


def generate_board(rng: random.Random | None = None, cols: int = BOARD_COLS,
                   rows: int = BOARD_ROWS) -> Board:
    """Shuffle the full tile set into the rectangle.

    The layout is otherwise unconstrained (players can regenerate a board they
    don't like); the only hard rule is that the lake touches enough land.
    """
    rng = rng or random.SystemRandom()
    topo = get_topology(cols, rows)
    inner = [h.id for h in topo.inner_hexes]
    tiles = [kind for kind, n in TILE_COUNTS.items() for _ in range(n)]
    if len(tiles) != len(inner):
        raise BoardGenerationError(
            f"{len(tiles)} tiles do not fit a {cols}x{rows} board ({len(inner)} hexes)"
        )

    for _ in range(500):
        rng.shuffle(tiles)
        terrain = [SEA] * len(topo.hexes)
        for hex_id, kind in zip(inner, tiles):
            terrain[hex_id] = kind

        lake = terrain.index(LAKE)
        land_around_lake = sum(
            1 for n in topo.hexes[lake].neighbours if n is not None and terrain[n] != SEA
        )
        if land_around_lake < LAKE_MIN_LAND_NEIGHBOURS:
            continue

        numbers: list[int | None] = [None] * len(topo.hexes)
        producing = [h for h in inner if terrain[h] in TERRAIN_RESOURCE or terrain[h] == GOLD]
        tokens = list(NUMBER_TOKENS)
        rng.shuffle(tokens)
        for hex_id, number in zip(producing, tokens):
            numbers[hex_id] = number

        # Each sea hex holds at most one harbour or fishery, so their markers never overlap.
        used_sea: set[int] = set()
        fisheries = _place_fisheries(topo, terrain, rng, used_sea)
        harbours = _place_harbours(topo, terrain, rng, used_sea)
        if harbours is None or fisheries is None:
            continue
        return Board(cols, rows, terrain, numbers, harbours, fisheries)

    raise BoardGenerationError("could not generate a valid board")


def _place_harbours(topo: Topology, terrain: list[str], rng: random.Random, used_sea: set[int]):
    """Harbours go on land/sea edges, never sharing a corner with another harbour."""
    candidates = []
    for edge in topo.edges:
        if len(edge.hexes) != 2:
            continue
        a, b = edge.hexes
        if (terrain[a] == SEA) != (terrain[b] == SEA):
            land, sea = (b, a) if terrain[a] == SEA else (a, b)
            candidates.append((edge, land, sea))
    rng.shuffle(candidates)

    kinds = list(HARBOURS)
    rng.shuffle(kinds)
    used_vertices: set[int] = set()
    harbours = []
    for edge, land, sea in candidates:
        if len(harbours) == len(kinds):
            break
        if sea in used_sea or used_vertices.intersection(edge.vertices):
            continue
        used_sea.add(sea)
        used_vertices.update(edge.vertices)
        harbours.append(
            {"edge": edge.id, "kind": kinds[len(harbours)], "land": land, "sea": sea}
        )
    return harbours if len(harbours) == len(kinds) else None


def _place_fisheries(topo: Topology, terrain: list[str], rng: random.Random, used_sea: set[int]):
    """Each fishery sits in a sea hex (or the frame) pointing at a corner whose two
    adjoining edges both face land, so all three corners it touches are coastal."""
    candidates = []
    for h in topo.hexes:
        if terrain[h.id] != SEA:
            continue
        for corner in range(6):
            before, after = h.neighbours[(corner - 1) % 6], h.neighbours[corner]
            if before is None or after is None:
                continue
            if terrain[before] == SEA or terrain[after] == SEA:
                continue
            verts = [h.corners[(corner - 1) % 6], h.corners[corner], h.corners[(corner + 1) % 6]]
            if None in verts:
                continue
            candidates.append((h.id, corner, verts))
    rng.shuffle(candidates)

    numbers = list(FISHERY_NUMBERS)
    rng.shuffle(numbers)
    used_vertices: set[int] = set()
    fisheries = []
    for hex_id, corner, verts in candidates:
        if len(fisheries) == len(numbers):
            break
        if hex_id in used_sea or used_vertices.intersection(verts):
            continue
        used_sea.add(hex_id)
        used_vertices.update(verts)
        fisheries.append(
            {"hex": hex_id, "corner": corner, "number": numbers[len(fisheries)], "vertices": verts}
        )
    return fisheries if len(fisheries) == len(numbers) else None
