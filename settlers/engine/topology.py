"""Hex grid topology for a rectangular board of pointy-top hexes.

Rows use an "odd-r" offset layout (odd rows are shifted half a hex to the right),
which gives a rectangle-like board. The playable ``cols x rows`` area is surrounded
by a ring of frame hexes, which always count as sea.

Geometry is done in integer units so that corners shared by neighbouring hexes
compare exactly: one X unit is half a hex width and one Y unit is half the hex
radius. A hex centre is at (2*col + (row & 1), 3*row), and its corners are at
the offsets in ``CORNER_OFFSETS``, clockwise from the top.

Everything (hexes, vertices, edges) gets a stable integer id, and the game state
refers to board locations purely by those ids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

# Clockwise from the top corner. Corner i and corner i+1 bound edge i.
CORNER_OFFSETS = ((0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1))


@dataclass
class Hex:
    id: int
    col: int
    row: int
    x: int
    y: int
    frame: bool
    corners: list = field(default_factory=list)  # 6 vertex ids (None if off-board)
    edges: list = field(default_factory=list)  # 6 edge ids (None if off-board)
    neighbours: list = field(default_factory=list)  # hex ids across each edge


@dataclass
class Vertex:
    id: int
    x: int
    y: int
    hexes: list = field(default_factory=list)  # 2-3 hex ids
    edges: list = field(default_factory=list)  # edge ids touching this vertex
    neighbours: list = field(default_factory=list)  # vertex ids one edge away


@dataclass
class Edge:
    id: int
    vertices: tuple  # (vertex id, vertex id)
    hexes: tuple  # 1-2 hex ids


class Topology:
    def __init__(self, cols: int, rows: int):
        self.cols = cols
        self.rows = rows
        self.hexes: list[Hex] = []
        self.vertices: list[Vertex] = []
        self.edges: list[Edge] = []
        self._build()

    def is_inner(self, col: int, row: int) -> bool:
        return 0 <= col < self.cols and 0 <= row < self.rows

    def _build(self) -> None:
        positions = [
            (c, r) for r in range(-1, self.rows + 1) for c in range(-1, self.cols + 1)
        ]

        def centre(c, r):
            return 2 * c + (r & 1), 3 * r

        def corners(c, r):
            cx, cy = centre(c, r)
            return [(cx + dx, cy + dy) for dx, dy in CORNER_OFFSETS]

        # Points that touch at least one playable hex are board vertices.
        point_hexes: dict[tuple, list] = {}
        for c, r in positions:
            for p in corners(c, r):
                point_hexes.setdefault(p, []).append((c, r))
        kept_points = sorted(
            (p for p, hs in point_hexes.items() if any(self.is_inner(*h) for h in hs)),
            key=lambda p: (p[1], p[0]),
        )
        # Frame hexes are only kept where they touch the playable area.
        kept_positions = sorted(
            {h for p in kept_points for h in point_hexes[p]}, key=lambda h: (h[1], h[0])
        )

        hex_id = {}
        for i, (c, r) in enumerate(kept_positions):
            x, y = centre(c, r)
            hex_id[(c, r)] = i
            self.hexes.append(Hex(i, c, r, x, y, frame=not self.is_inner(c, r)))

        vertex_id = {}
        for i, p in enumerate(kept_points):
            vertex_id[p] = i
            self.vertices.append(
                Vertex(i, p[0], p[1], hexes=sorted(hex_id[h] for h in point_hexes[p]))
            )

        # Edges: consecutive corner pairs touching at least one playable hex.
        edge_hexes: dict[frozenset, list] = {}
        for c, r in kept_positions:
            cs = corners(c, r)
            for k in range(6):
                key = frozenset((cs[k], cs[(k + 1) % 6]))
                edge_hexes.setdefault(key, []).append((c, r))
        kept_edges = [
            (key, hs)
            for key, hs in edge_hexes.items()
            if any(self.is_inner(*h) for h in hs) and all(p in vertex_id for p in key)
        ]

        def edge_sort_key(item):
            a, b = sorted(item[0], key=lambda p: (p[1], p[0]))
            return (a[1] + b[1], a[0] + b[0])

        kept_edges.sort(key=edge_sort_key)
        edge_id = {}
        for i, (key, hs) in enumerate(kept_edges):
            a, b = sorted((vertex_id[p] for p in key))
            edge_id[key] = i
            self.edges.append(Edge(i, (a, b), tuple(sorted(hex_id[h] for h in hs))))
            self.vertices[a].edges.append(i)
            self.vertices[b].edges.append(i)
            self.vertices[a].neighbours.append(b)
            self.vertices[b].neighbours.append(a)

        for h in self.hexes:
            cs = corners(h.col, h.row)
            h.corners = [vertex_id.get(p) for p in cs]
            h.edges = [edge_id.get(frozenset((cs[k], cs[(k + 1) % 6]))) for k in range(6)]
            h.neighbours = []
            for k in range(6):
                key = frozenset((cs[k], cs[(k + 1) % 6]))
                others = [hex_id[o] for o in edge_hexes[key] if o != (h.col, h.row)]
                h.neighbours.append(others[0] if others else None)

    @property
    def inner_hexes(self) -> list[Hex]:
        return [h for h in self.hexes if not h.frame]

    def to_dict(self) -> dict:
        """Geometry the client needs to draw the board."""
        return {
            "cols": self.cols,
            "rows": self.rows,
            "hexes": [
                {"id": h.id, "x": h.x, "y": h.y, "frame": h.frame,
                 "corners": h.corners, "edges": h.edges}
                for h in self.hexes
            ],
            "vertices": [{"id": v.id, "x": v.x, "y": v.y} for v in self.vertices],
            "edges": [{"id": e.id, "v": list(e.vertices)} for e in self.edges],
        }


@lru_cache(maxsize=8)
def get_topology(cols: int, rows: int) -> Topology:
    return Topology(cols, rows)
