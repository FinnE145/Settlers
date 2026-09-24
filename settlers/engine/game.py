"""Game state and rules.

A ``Game`` is driven entirely through ``act(player, action)``, where ``action`` is a
plain dict like ``{"type": "build_road", "edge": 12}``. Illegal actions raise
``RuleError`` with a message suitable for showing to the player. ``view_for`` gives
the state as one player may see it, and ``to_dict``/``from_dict`` round-trip the
whole state as JSON-compatible data.
"""

from __future__ import annotations

import random
from collections import Counter

from .board import Board
from .constants import (
    BOOT,
    CITY_LIMIT,
    COSTS,
    DEV_CARDS,
    DEV_NAMES,
    FISH_PRICES,
    FISH_TOKENS,
    GOLD,
    LAKE,
    LAKE_NUMBERS,
    LARGEST_ARMY_MIN,
    LONGEST_ROUTE_MIN,
    PLAYABLE_DEV,
    PLAYER_COLOURS,
    RESOURCES,
    SETTLEMENT_LIMIT,
    TERRAIN_RESOURCE,
    VP_TO_WIN,
)


class RuleError(Exception):
    """An action the rules don't allow. The message is shown to the player."""


def _empty_cards() -> dict:
    return {r: 0 for r in RESOURCES}


def _new_player() -> dict:
    return {
        "hand": _empty_cards(),
        "bank": _empty_cards(),
        "fish": [],  # token values (1-3); the boot is tracked separately
        "dev": [],  # unplayed cards: {"card": name, "turn": turn bought}
        "knights": 0,
    }


def _count(cards: dict) -> int:
    return sum(cards.values())


def _clean_cards(cards) -> dict:
    """Validate a {resource: count} dict from a client."""
    if not isinstance(cards, dict):
        raise RuleError("Invalid cards.")
    out = _empty_cards()
    for res, n in cards.items():
        if res not in RESOURCES or not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise RuleError("Invalid cards.")
        out[res] = n
    return out


class Game:
    def __init__(self, board: Board, first_player: int = 0, rng: random.Random | None = None,
                 _state: dict | None = None):
        self.rng = rng or random.SystemRandom()
        self.board = board
        self.topo = board.topology
        if _state is not None:
            self.__dict__.update(_state)
            return

        self.players = [_new_player() for _ in PLAYER_COLOURS]
        self.phase = "setup"  # setup | play | finished
        self.first_player = first_player
        self.current = first_player
        self.turn_number = 0  # 0 during setup, then 1, 2, ...
        second = 1 - first_player
        self.setup_order = [first_player, second, second, first_player]
        self.setup_step = 0
        self.setup_awaiting = "settlement"  # settlement | route
        self.setup_vertex = None  # settlement just placed, awaiting its road/ship
        self.rolled = False
        self.dice = None
        self.pending: list[dict] = []
        self.buildings: dict[int, dict] = {}  # vertex -> {"owner", "kind"}
        self.routes: dict[int, dict] = {}  # edge -> {"owner", "kind", "turn"}
        self.robber = None  # hex id, or None while off the board
        self.pirate = None
        self.dev_deck = [card for card, n in DEV_CARDS.items() for _ in range(n)]
        self.rng.shuffle(self.dev_deck)
        self.fish_bag = list(FISH_TOKENS) + [BOOT]
        self.rng.shuffle(self.fish_bag)
        self.fish_spent: list[int] = []
        self.boot_holder = None
        self.longest_route = None  # player index holding the title
        self.largest_army = None
        self.ship_moved = False
        self.dev_played = False
        self.trade = None
        self.winner = None
        self.log: list[dict] = []
        self._log(f"{self._name(first_player)} places first.")

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _name(p: int) -> str:
        return PLAYER_COLOURS[p].capitalize()

    def _log(self, text: str, private: dict | None = None) -> None:
        entry = {"n": len(self.log), "text": text}
        if private:
            entry["private"] = {str(k): v for k, v in private.items()}
        self.log.append(entry)

    def _require(self, cond: bool, message: str) -> None:
        if not cond:
            raise RuleError(message)

    def _require_turn(self, p: int) -> None:
        self._require(self.phase == "play", "The game isn't in progress.")
        self._require(p == self.current, "It's not your turn.")

    def _require_main_phase(self, p: int) -> None:
        """Your turn, dice rolled, nothing outstanding."""
        self._require_turn(p)
        self._require(not self.pending, "Something needs to be resolved first.")
        self._require(self.rolled, "Roll the dice first.")

    def _pending_for(self, kind: str, p: int) -> dict | None:
        for item in self.pending:
            if item["type"] == kind and item["player"] == p:
                return item
        return None

    def _pay(self, p: int, cost: dict) -> None:
        hand = self.players[p]["hand"]
        self._require(all(hand[r] >= n for r, n in cost.items()), "You can't afford that.")
        for r, n in cost.items():
            hand[r] -= n

    def _can_afford(self, p: int, cost: dict) -> bool:
        hand = self.players[p]["hand"]
        return all(hand[r] >= n for r, n in cost.items())

    def _describe(self, cards: dict) -> str:
        parts = [f"{n} {r}" for r, n in cards.items() if n]
        return ", ".join(parts) if parts else "nothing"

    # --------------------------------------------------------------- board queries

    def _vertex_touches_land(self, v: int) -> bool:
        return any(self.board.is_land(h) for h in self.topo.vertices[v].hexes)

    def _edge_touches_land(self, e: int) -> bool:
        return any(self.board.is_land(h) for h in self.topo.edges[e].hexes)

    def _edge_touches_sea(self, e: int) -> bool:
        return any(self.board.is_sea(h) for h in self.topo.edges[e].hexes)

    def _pirate_edges(self) -> set:
        if self.pirate is None:
            return set()
        return {e for e in self.topo.hexes[self.pirate].edges if e is not None}

    def _distance_ok(self, v: int) -> bool:
        return v not in self.buildings and not any(
            n in self.buildings for n in self.topo.vertices[v].neighbours
        )

    def _piece_counts(self, p: int) -> tuple[int, int]:
        s = sum(1 for b in self.buildings.values() if b["owner"] == p and b["kind"] == "settlement")
        c = sum(1 for b in self.buildings.values() if b["owner"] == p and b["kind"] == "city")
        return s, c

    def _limits_lifted(self, p: int) -> bool:
        s, c = self._piece_counts(p)
        return s >= SETTLEMENT_LIMIT and c >= CITY_LIMIT

    def _settlement_piece_available(self, p: int) -> bool:
        return self._limits_lifted(p) or self._piece_counts(p)[0] < SETTLEMENT_LIMIT

    def _city_piece_available(self, p: int) -> bool:
        return self._limits_lifted(p) or self._piece_counts(p)[1] < CITY_LIMIT

    def _route_connects(self, p: int, e: int, kind: str, ignore: int | None = None) -> bool:
        """A new road/ship at ``e`` must join your building, or your route of the same
        kind through a corner without an opponent's building."""
        for v in self.topo.edges[e].vertices:
            b = self.buildings.get(v)
            if b is not None:
                if b["owner"] == p:
                    return True
                continue
            for e2 in self.topo.vertices[v].edges:
                if e2 in (e, ignore):
                    continue
                r = self.routes.get(e2)
                if r is not None and r["owner"] == p and r["kind"] == kind:
                    return True
        return False

    def legal_settlements(self, p: int) -> list[int]:
        setup = self.phase == "setup"
        out = []
        for v in self.topo.vertices:
            if not self._vertex_touches_land(v.id) or not self._distance_ok(v.id):
                continue
            if setup or any(
                self.routes.get(e, {}).get("owner") == p for e in v.edges
            ):
                out.append(v.id)
        return out

    def legal_cities(self, p: int) -> list[int]:
        return [v for v, b in self.buildings.items() if b["owner"] == p and b["kind"] == "settlement"]

    def legal_roads(self, p: int) -> list[int]:
        if self.phase == "setup":
            return [e for e in self._setup_edges() if self._edge_touches_land(e)]
        return [
            e.id for e in self.topo.edges
            if e.id not in self.routes and self._edge_touches_land(e.id)
            and self._route_connects(p, e.id, "road")
        ]

    def legal_ships(self, p: int, ignore: int | None = None) -> list[int]:
        blocked = self._pirate_edges()
        if self.phase == "setup":
            return [e for e in self._setup_edges() if self._edge_touches_sea(e) and e not in blocked]
        return [
            e.id for e in self.topo.edges
            if e.id not in self.routes and e.id != ignore and e.id not in blocked
            and self._edge_touches_sea(e.id)
            and self._route_connects(p, e.id, "ship", ignore=ignore)
        ]

    def _setup_edges(self) -> list[int]:
        if self.setup_awaiting != "route" or self.setup_vertex is None:
            return []
        return [e for e in self.topo.vertices[self.setup_vertex].edges if e not in self.routes]

    # ------------------------------------------------------------------ scoring

    def route_length(self, p: int) -> int:
        """Longest chain of p's roads/ships. Roads and ships only join at p's own
        buildings, and an opponent's building breaks a chain."""
        own = {e: r["kind"] for e, r in self.routes.items() if r["owner"] == p}
        if not own:
            return 0
        at_vertex: dict[int, list] = {}
        for e in own:
            for v in self.topo.edges[e].vertices:
                at_vertex.setdefault(v, []).append(e)

        def extend(v, last, used):
            b = self.buildings.get(v)
            if b is not None and b["owner"] != p:
                return len(used)
            mixed_ok = b is not None and b["owner"] == p
            best = len(used)
            for e2 in at_vertex.get(v, ()):
                if e2 in used or (own[e2] != own[last] and not mixed_ok):
                    continue
                a, c = self.topo.edges[e2].vertices
                best = max(best, extend(c if a == v else a, e2, used | {e2}))
            return best

        best = 0
        for e in own:
            a, c = self.topo.edges[e].vertices
            best = max(best, extend(c, e, frozenset([e])), extend(a, e, frozenset([e])))
        return best

    def _update_longest_route(self) -> None:
        lengths = [self.route_length(p) for p in range(len(self.players))]
        holder = self.longest_route
        new = holder
        if holder is None:
            for p, n in enumerate(lengths):
                if n >= LONGEST_ROUTE_MIN and all(n > m for q, m in enumerate(lengths) if q != p):
                    new = p
        else:
            challengers = [p for p, n in enumerate(lengths) if p != holder and n > lengths[holder]]
            if challengers and lengths[challengers[0]] >= LONGEST_ROUTE_MIN:
                new = challengers[0]
            elif lengths[holder] < LONGEST_ROUTE_MIN:
                new = None
        if new != holder:
            self.longest_route = new
            if new is None:
                self._log("Nobody holds the longest trade route now.")
            else:
                self._log(f"{self._name(new)} takes the longest trade route ({lengths[new]}).")

    def public_vp(self, p: int) -> int:
        vp = 0
        for b in self.buildings.values():
            if b["owner"] == p:
                vp += 2 if b["kind"] == "city" else 1
        if self.longest_route == p:
            vp += 2
        if self.largest_army == p:
            vp += 2
        return vp

    def total_vp(self, p: int) -> int:
        hidden = sum(1 for d in self.players[p]["dev"] if d["card"] == "victory_point")
        return self.public_vp(p) + hidden

    def vp_needed(self, p: int) -> int:
        return VP_TO_WIN + (1 if self.boot_holder == p else 0)

    def _check_winner(self) -> None:
        if self.phase != "play":
            return
        p = self.current
        if self.total_vp(p) >= self.vp_needed(p):
            self.phase = "finished"
            self.winner = p
            self.pending = []
            self.trade = None
            self._log(f"{self._name(p)} wins with {self.total_vp(p)} VP!")

    # ------------------------------------------------------------------ fish

    def _take_fish_token(self) -> int:
        if not self.fish_bag:
            self.fish_bag = self.fish_spent
            self.fish_spent = []
            self.rng.shuffle(self.fish_bag)
        return self.fish_bag.pop()

    def _draw_fish(self, demand: list[int]) -> None:
        total = sum(demand)
        if total == 0:
            return
        if total > len(self.fish_bag) + len(self.fish_spent):
            self._log("Not enough fish tokens left; nobody gets fish this time.")
            return
        order = [self.current] + [p for p in range(len(self.players)) if p != self.current]
        for p in order:
            drawn = []
            for _ in range(demand[p]):
                token = self._take_fish_token()
                if token == BOOT:
                    self.boot_holder = p
                    self._log(f"{self._name(p)} fished up the old boot!")
                else:
                    self.players[p]["fish"].append(token)
                    drawn.append(token)
            if drawn:
                values = ", ".join(str(t) for t in drawn)
                self._log(
                    f"{self._name(p)} draws {len(drawn)} fish token{'s' if len(drawn) > 1 else ''}.",
                    private={p: f"You draw fish token{'s' if len(drawn) > 1 else ''}: {values}."},
                )

    # --------------------------------------------------------------- production

    def _building_yield(self, v: int) -> tuple[int, int] | None:
        b = self.buildings.get(v)
        if b is None:
            return None
        return b["owner"], 2 if b["kind"] == "city" else 1

    def _produce(self, roll: int) -> None:
        n_players = len(self.players)
        gains = [_empty_cards() for _ in range(n_players)]
        gold = [0] * n_players
        fish = [0] * n_players

        for h in self.topo.hexes:
            if self.board.numbers[h.id] != roll or self.robber == h.id:
                continue
            terrain = self.board.terrain[h.id]
            for v in h.corners:
                y = self._building_yield(v) if v is not None else None
                if y is None:
                    continue
                owner, amount = y
                if terrain == GOLD:
                    gold[owner] += amount
                else:
                    gains[owner][TERRAIN_RESOURCE[terrain]] += amount

        for f in self.board.fisheries:
            if f["number"] != roll:
                continue
            per = [0] * n_players
            for v in f["vertices"]:
                y = self._building_yield(v)
                if y is not None:
                    per[y[0]] += y[1]
            if self.pirate == f["hex"]:
                per = [n // 2 for n in per]
            fish = [a + b for a, b in zip(fish, per)]

        lake = self.board.lake_hex
        if roll in LAKE_NUMBERS and lake is not None and self.robber != lake:
            for v in self.topo.hexes[lake].corners:
                y = self._building_yield(v)
                if y is not None:
                    fish[y[0]] += y[1]

        for p in range(n_players):
            if _count(gains[p]):
                for r, n in gains[p].items():
                    self.players[p]["hand"][r] += n
                self._log(f"{self._name(p)} gets {self._describe(gains[p])}.")
            if gold[p]:
                self.pending.append({"type": "gold", "player": p, "count": gold[p]})
                self._log(f"{self._name(p)} picks {gold[p]} card{'s' if gold[p] > 1 else ''} from gold.")
        self._draw_fish(fish)

    def _starting_production(self) -> None:
        """At the end of setup every starting settlement gives a card per adjacent
        producing hex (gold is picked), plus a fish token per fishing ground or lake."""
        n_players = len(self.players)
        fish = [0] * n_players
        order = [self.first_player] + [q for q in range(n_players) if q != self.first_player]
        for p in order:
            gains = _empty_cards()
            gold = 0
            for v, b in self.buildings.items():
                if b["owner"] != p:
                    continue
                for h in self.topo.vertices[v].hexes:
                    terrain = self.board.terrain[h]
                    if terrain in TERRAIN_RESOURCE:
                        gains[TERRAIN_RESOURCE[terrain]] += 1
                    elif terrain == GOLD:
                        gold += 1
                    elif terrain == LAKE:
                        fish[p] += 1
                fish[p] += sum(1 for f in self.board.fisheries if v in f["vertices"])
            for r, n in gains.items():
                self.players[p]["hand"][r] += n
            self._log(f"{self._name(p)} starts with {self._describe(gains)}.")
            if gold:
                self.pending.append({"type": "gold", "player": p, "count": gold})
                self._log(f"{self._name(p)} picks {gold} card{'s' if gold > 1 else ''} from gold.")
        self._draw_fish(fish)

    # ------------------------------------------------------------------ actions

    ACTIONS = (
        "build_settlement", "build_city", "build_road", "build_ship",
        "roll", "end_turn", "choose_gold", "discard", "move_robber",
        "maritime", "offer_trade", "accept_trade", "decline_trade", "cancel_trade",
        "buy_dev", "play_dev", "skip_free_routes", "fish", "deposit", "pass_boot", "move_ship",
    )

    def act(self, p: int, action: dict) -> None:
        if self.phase == "finished":
            raise RuleError("The game is over.")
        if not isinstance(action, dict) or action.get("type") not in self.ACTIONS:
            raise RuleError("Unknown action.")
        if p not in range(len(self.players)):
            raise RuleError("Unknown player.")
        getattr(self, "_act_" + action["type"])(p, action)
        self._check_winner()

    @staticmethod
    def _int_arg(action: dict, key: str) -> int:
        value = action.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise RuleError(f"Missing {key}.")
        return value

    # --- setup and building

    def _act_build_settlement(self, p: int, a: dict) -> None:
        v = self._int_arg(a, "vertex")
        if self.phase == "setup":
            self._require(self.setup_order[self.setup_step] == p, "It's not your turn to place.")
            self._require(not self.pending, "Something needs to be resolved first.")
            self._require(self.setup_awaiting == "settlement", "Place your road or ship first.")
            self._require(v in self.legal_settlements(p), "You can't build a settlement there.")
            self.buildings[v] = {"owner": p, "kind": "settlement"}
            self.setup_vertex = v
            self.setup_awaiting = "route"
            self._log(f"{self._name(p)} places a settlement.")
            return

        self._require_main_phase(p)
        self._require(v in self.legal_settlements(p), "You can't build a settlement there.")
        self._require(self._settlement_piece_available(p),
                      "You need 5 settlements and 4 cities on the board before building more settlements.")
        self._pay(p, COSTS["settlement"])
        self.buildings[v] = {"owner": p, "kind": "settlement"}
        self._log(f"{self._name(p)} builds a settlement.")
        self._update_longest_route()

    def _act_build_city(self, p: int, a: dict) -> None:
        v = self._int_arg(a, "vertex")
        self._require_main_phase(p)
        self._require(v in self.legal_cities(p), "You need your own settlement there.")
        self._require(self._city_piece_available(p),
                      "You need 5 settlements and 4 cities on the board before building more cities.")
        self._pay(p, COSTS["city"])
        self.buildings[v] = {"owner": p, "kind": "city"}
        self._log(f"{self._name(p)} builds a city.")

    def _act_build_road(self, p: int, a: dict) -> None:
        self._build_route(p, self._int_arg(a, "edge"), "road")

    def _act_build_ship(self, p: int, a: dict) -> None:
        self._build_route(p, self._int_arg(a, "edge"), "ship")

    def _build_route(self, p: int, e: int, kind: str) -> None:
        legal = self.legal_roads if kind == "road" else self.legal_ships
        if self.phase == "setup":
            self._require(self.setup_order[self.setup_step] == p, "It's not your turn to place.")
            self._require(not self.pending, "Something needs to be resolved first.")
            self._require(self.setup_awaiting == "route", "Place your settlement first.")
            self._require(e in legal(p), f"You can't place a {kind} there.")
            self.routes[e] = {"owner": p, "kind": kind, "turn": 0}
            self._log(f"{self._name(p)} places a {kind}.")
            self._advance_setup()
            return

        self._require_turn(p)
        free = self._pending_for("free_routes", p)
        if free is None:
            self._require_main_phase(p)
        self._require(e in legal(p), f"You can't build a {kind} there.")
        if free is None:
            self._pay(p, COSTS[kind])
        else:
            free["count"] -= 1
            if free["count"] == 0:
                self.pending.remove(free)
        self.routes[e] = {"owner": p, "kind": kind, "turn": self.turn_number}
        self._log(f"{self._name(p)} builds a {kind}{' for free' if free else ''}.")
        self._update_longest_route()

    def _advance_setup(self) -> None:
        self.setup_step += 1
        self.setup_awaiting = "settlement"
        self.setup_vertex = None
        if self.setup_step < len(self.setup_order):
            self.current = self.setup_order[self.setup_step]
            return
        self.phase = "play"
        self.current = self.first_player
        self.turn_number = 1
        self._update_longest_route()
        self._log("Setup done.")
        self._starting_production()

    # --- turn flow

    def _act_roll(self, p: int, a: dict) -> None:
        self._require_turn(p)
        self._require(not self.rolled, "You already rolled.")
        self._require(not self.pending, "Something needs to be resolved first.")
        self.dice = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
        self.rolled = True
        total = sum(self.dice)
        self._log(f"{self._name(p)} rolls {total} ({self.dice[0]}+{self.dice[1]}).")
        if total == 7:
            for q, player in enumerate(self.players):
                n = _count(player["hand"])
                if n > 7:
                    self.pending.append({"type": "discard", "player": q, "count": n // 2})
                    self._log(f"{self._name(q)} must discard {n // 2}.")
            self.pending.append({"type": "robber", "player": p})
        else:
            self._produce(total)

    def _act_end_turn(self, p: int, a: dict) -> None:
        self._require_main_phase(p)
        self.trade = None
        self.current = 1 - self.current
        self.turn_number += 1
        self.rolled = False
        self.ship_moved = False
        self.dev_played = False
        self._log(f"{self._name(self.current)}'s turn.")

    def _act_choose_gold(self, p: int, a: dict) -> None:
        item = self._pending_for("gold", p)
        self._require(item is not None, "You have no gold to pick.")
        cards = _clean_cards(a.get("cards"))
        self._require(_count(cards) == item["count"], f"Pick exactly {item['count']}.")
        for r, n in cards.items():
            self.players[p]["hand"][r] += n
        self.pending.remove(item)
        self._log(f"{self._name(p)} takes {self._describe(cards)} from gold.")

    def _act_discard(self, p: int, a: dict) -> None:
        item = self._pending_for("discard", p)
        self._require(item is not None, "You don't need to discard.")
        cards = _clean_cards(a.get("cards"))
        self._require(_count(cards) == item["count"], f"Discard exactly {item['count']}.")
        hand = self.players[p]["hand"]
        self._require(all(hand[r] >= n for r, n in cards.items()), "You don't have those cards.")
        for r, n in cards.items():
            hand[r] -= n
        self.pending.remove(item)
        self._log(f"{self._name(p)} discards {self._describe(cards)}.")

    def robber_victim(self, piece: str, hex_id: int, p: int) -> int | None:
        """The opponent who could be robbed at ``hex_id``, if any."""
        o = 1 - p
        if piece == "robber":
            touching = any(
                self.buildings.get(v, {}).get("owner") == o
                for v in self.topo.hexes[hex_id].corners if v is not None
            )
        else:
            touching = any(
                self.routes.get(e, {}).get("owner") == o and self.routes[e]["kind"] == "ship"
                for e in self.topo.hexes[hex_id].edges if e is not None
            )
        return o if touching else None

    def legal_robber_hexes(self) -> list[int]:
        return [h.id for h in self.topo.hexes
                if not h.frame and self.board.is_land(h.id) and h.id != self.robber]

    def legal_pirate_hexes(self) -> list[int]:
        return [h.id for h in self.topo.hexes if self.board.is_sea(h.id) and h.id != self.pirate]

    def _act_move_robber(self, p: int, a: dict) -> None:
        item = self._pending_for("robber", p)
        self._require(item is not None, "You don't need to move the robber.")
        self._require(not any(i["type"] == "discard" for i in self.pending),
                      "Wait for discards first.")
        piece = a.get("piece")
        self._require(piece in ("robber", "pirate"), "Choose the robber or the pirate.")
        hex_id = self._int_arg(a, "hex")
        targets = self.legal_robber_hexes() if piece == "robber" else self.legal_pirate_hexes()
        self._require(hex_id in targets, f"The {piece} can't go there.")
        take = a.get("take")
        self._require(take == "steal" or take in RESOURCES, "Choose to steal or take a card.")

        victim = self.robber_victim(piece, hex_id, p)
        if take == "steal":
            self._require(victim is not None, "Nobody to steal from there.")
            victim_hand = self.players[victim]["hand"]
            self._require(_count(victim_hand) > 0, f"{self._name(victim)} has no cards in hand.")

        setattr(self, piece, hex_id)
        self.pending.remove(item)
        self._log(f"{self._name(p)} moves the {piece}.")
        if take == "steal":
            card = self._random_card(victim_hand)
            victim_hand[card] -= 1
            self.players[p]["hand"][card] += 1
            self._log(f"{self._name(p)} steals {card} from {self._name(victim)}.")
        else:
            self.players[p]["hand"][take] += 1
            self._log(f"{self._name(p)} takes {take} from the supply.")

    def _random_card(self, hand: dict) -> str:
        pool = [r for r, n in hand.items() for _ in range(n)]
        return self.rng.choice(pool)

    # --- trading with the bank and harbours

    def _harbour_holdings(self, p: int) -> tuple[bool, set, set]:
        """(on a 3:1 harbour, resources of 2:1 harbours p is on, those p is on with a city)"""
        generic, two, city = False, set(), set()
        for h in self.board.harbours:
            for v in self.topo.edges[h["edge"]].vertices:
                b = self.buildings.get(v)
                if b is None or b["owner"] != p:
                    continue
                if h["kind"] == "3:1":
                    generic = True
                else:
                    two.add(h["kind"])
                    if b["kind"] == "city":
                        city.add(h["kind"])
        return generic, two, city

    def trade_rates(self, p: int) -> dict:
        """How many of ``give`` it costs p to get one ``get`` from the supply."""
        generic, two, city = self._harbour_holdings(p)
        rates = {}
        for give in RESOURCES:
            rates[give] = {}
            for get in RESOURCES:
                if give == get:
                    continue
                rate = 3 if generic else 4
                if give in two or get in two:  # 2:1 harbours work both ways
                    rate = 2
                if give in city and get in city:  # cities on two 2:1 harbours: 1:1 between them
                    rate = 1
                rates[give][get] = rate
        return rates

    def _act_maritime(self, p: int, a: dict) -> None:
        self._require_main_phase(p)
        give, get = a.get("give"), a.get("get")
        self._require(give in RESOURCES and get in RESOURCES and give != get,
                      "Pick two different resources.")
        rate = self.trade_rates(p)[give][get]
        self._pay(p, {give: rate})
        self.players[p]["hand"][get] += 1
        self._log(f"{self._name(p)} trades {rate} {give} for 1 {get}.")

    # --- trading between players

    @staticmethod
    def _clean_fish(value) -> list[int]:
        if value is None:
            return []
        if not isinstance(value, list) or not all(
            isinstance(t, int) and not isinstance(t, bool) and t in (1, 2, 3) for t in value
        ):
            raise RuleError("Invalid fish tokens.")
        return sorted(value)

    def _has_fish(self, p: int, tokens: list[int]) -> bool:
        return not (Counter(tokens) - Counter(self.players[p]["fish"]))

    def _take_fish(self, p: int, tokens: list[int]) -> None:
        for t in tokens:
            self.players[p]["fish"].remove(t)

    def _has_cards(self, p: int, cards: dict) -> bool:
        hand = self.players[p]["hand"]
        return all(hand[r] >= n for r, n in cards.items())

    def _require_trade_window(self) -> None:
        self._require(self.phase == "play", "The game isn't in progress.")
        self._require(self.rolled and not self.pending, "Trading happens after the roll.")

    def _describe_side(self, cards: dict, fish: list[int]) -> str:
        parts = [self._describe(cards)] if _count(cards) else []
        if fish:
            parts.append("fish " + "+".join(str(t) for t in fish))
        return " and ".join(parts) if parts else "nothing"

    def _act_offer_trade(self, p: int, a: dict) -> None:
        self._require_trade_window()
        give, get = _clean_cards(a.get("give", {})), _clean_cards(a.get("get", {}))
        give_fish, get_fish = self._clean_fish(a.get("give_fish")), self._clean_fish(a.get("get_fish"))
        self._require((_count(give) or give_fish) and (_count(get) or get_fish),
                      "Both sides of a trade need something.")
        self._require(self._has_cards(p, give), "You don't have those cards.")
        self._require(self._has_fish(p, give_fish), "You don't have those fish tokens.")
        self.trade = {"from": p, "give": give, "get": get, "give_fish": give_fish, "get_fish": get_fish}
        self._log(f"{self._name(p)} offers {self._describe_side(give, give_fish)} "
                  f"for {self._describe_side(get, get_fish)}.")

    def _act_accept_trade(self, p: int, a: dict) -> None:
        t = self.trade
        self._require(t is not None and t["from"] != p, "There's no offer to accept.")
        self._require_trade_window()
        o = t["from"]
        self._require(self._has_cards(o, t["give"]) and self._has_fish(o, t["give_fish"]),
                      f"{self._name(o)} no longer has what they offered.")
        self._require(self._has_cards(p, t["get"]), "You don't have the cards they asked for.")
        self._require(self._has_fish(p, t["get_fish"]), "You don't have the fish tokens they asked for.")
        for r in RESOURCES:
            self.players[o]["hand"][r] += t["get"][r] - t["give"][r]
            self.players[p]["hand"][r] += t["give"][r] - t["get"][r]
        self._take_fish(o, t["give_fish"])
        self._take_fish(p, t["get_fish"])
        self.players[p]["fish"] += t["give_fish"]
        self.players[o]["fish"] += t["get_fish"]
        self.trade = None
        self._log(f"{self._name(p)} accepts the trade.")

    def _act_decline_trade(self, p: int, a: dict) -> None:
        self._require(self.trade is not None and self.trade["from"] != p, "There's no offer to decline.")
        self.trade = None
        self._log(f"{self._name(p)} declines the trade.")

    def _act_cancel_trade(self, p: int, a: dict) -> None:
        self._require(self.trade is not None and self.trade["from"] == p, "You have no open offer.")
        self.trade = None
        self._log(f"{self._name(p)} withdraws the offer.")

    # --- development cards

    def _draw_dev(self, p: int) -> None:
        card = self.dev_deck.pop()
        self.players[p]["dev"].append({"card": card, "turn": self.turn_number})
        self._log(f"{self._name(p)} gets a development card.",
                  private={p: f"You get a development card: {DEV_NAMES[card]}."})

    def _act_buy_dev(self, p: int, a: dict) -> None:
        self._require_main_phase(p)
        self._require(bool(self.dev_deck), "No development cards left.")
        self._pay(p, COSTS["dev_card"])
        self._draw_dev(p)

    def playable_dev(self, p: int) -> list[str]:
        if self.phase != "play" or p != self.current or self.pending or self.dev_played:
            return []
        return sorted({d["card"] for d in self.players[p]["dev"]
                       if d["card"] in PLAYABLE_DEV and d["turn"] < self.turn_number})

    def _act_play_dev(self, p: int, a: dict) -> None:
        self._require_turn(p)
        self._require(not self.pending, "Something needs to be resolved first.")
        self._require(not self.dev_played, "You've already played a development card this turn.")
        card = a.get("card")
        self._require(card in PLAYABLE_DEV, "That card can't be played.")
        dev = self.players[p]["dev"]
        entry = next((d for d in dev if d["card"] == card and d["turn"] < self.turn_number), None)
        self._require(entry is not None, "You don't have that card, or you got it this turn.")
        if card == "year_of_plenty":
            cards = _clean_cards(a.get("cards"))
            self._require(_count(cards) == 2, "Pick 2 cards.")
        if card == "monopoly":
            res = a.get("resource")
            self._require(res in RESOURCES, "Name a resource.")

        dev.remove(entry)
        self.dev_played = True
        if card == "knight":
            self.players[p]["knights"] += 1
            self._log(f"{self._name(p)} plays a knight.")
            self._update_largest_army()
            self.pending.append({"type": "robber", "player": p})
        elif card == "road_building":
            self._log(f"{self._name(p)} plays road building.")
            self._add_free_routes(p, 2)
        elif card == "year_of_plenty":
            for r, n in cards.items():
                self.players[p]["hand"][r] += n
            self._log(f"{self._name(p)} plays year of plenty: {self._describe(cards)}.")
        else:
            o = 1 - p
            n = self.players[o]["hand"][res]
            self.players[o]["hand"][res] = 0
            self.players[p]["hand"][res] += n
            self._log(f"{self._name(p)} plays monopoly on {res} and takes {n}.")

    def _update_largest_army(self) -> None:
        for q, pl in enumerate(self.players):
            holder = self.largest_army
            if q == holder or pl["knights"] < LARGEST_ARMY_MIN:
                continue
            if holder is None or pl["knights"] > self.players[holder]["knights"]:
                self.largest_army = q
                self._log(f"{self._name(q)} takes the largest army.")

    def _add_free_routes(self, p: int, n: int) -> None:
        item = self._pending_for("free_routes", p)
        if item is None:
            self.pending.append({"type": "free_routes", "player": p, "count": n})
        else:
            item["count"] += n

    def _act_skip_free_routes(self, p: int, a: dict) -> None:
        item = self._pending_for("free_routes", p)
        self._require(item is not None, "You have no free roads or ships.")
        self.pending.remove(item)
        self._log(f"{self._name(p)} skips {item['count']} free road/ship.")

    # --- fish

    def _act_fish(self, p: int, a: dict) -> None:
        self._require_main_phase(p)
        tokens = self._clean_fish(a.get("tokens"))
        self._require(bool(tokens), "Choose fish tokens to pay with.")
        self._require(self._has_fish(p, tokens), "You don't have those fish tokens.")
        items = a.get("items")
        self._require(isinstance(items, list) and items, "Choose something to buy.")
        kinds = Counter()
        wanted = _empty_cards()
        for item in items:
            self._require(isinstance(item, dict) and item.get("kind") in FISH_PRICES, "Unknown purchase.")
            kinds[item["kind"]] += 1
            if item["kind"] == "resource":
                self._require(item.get("resource") in RESOURCES, "Choose a resource.")
                wanted[item["resource"]] += 1
        cost = sum(FISH_PRICES[k] * n for k, n in kinds.items())
        paid = sum(tokens)
        self._require(paid >= cost, f"That costs {cost} fish.")
        self._require(paid - min(tokens) < cost, "You don't need all of those tokens.")
        o = 1 - p
        me, opp = self.players[p], self.players[o]
        self._require(kinds["bank"] <= 1 and (not kinds["bank"] or _count(me["bank"]) > 0),
                      "Your bank is empty.")
        self._require(kinds["remove_robber"] <= 1 and (not kinds["remove_robber"] or self.robber is not None),
                      "The robber isn't on the board.")
        self._require(kinds["remove_pirate"] <= 1 and (not kinds["remove_pirate"] or self.pirate is not None),
                      "The pirate isn't on the board.")
        self._require(kinds["steal"] <= _count(opp["hand"]),
                      f"{self._name(o)} doesn't have enough cards in hand.")
        self._require(kinds["dev_card"] <= len(self.dev_deck), "Not enough development cards left.")

        self._take_fish(p, tokens)
        self.fish_spent += tokens
        self._log(f"{self._name(p)} spends {paid} fish.")
        if kinds["bank"]:
            n = _count(me["bank"])
            for r in RESOURCES:
                me["hand"][r] += me["bank"][r]
                me["bank"][r] = 0
            self._log(f"{self._name(p)} takes {n} card{'s' if n > 1 else ''} out of the bank.")
        if kinds["remove_robber"]:
            self.robber = None
            self._log(f"{self._name(p)} removes the robber.")
        if kinds["remove_pirate"]:
            self.pirate = None
            self._log(f"{self._name(p)} removes the pirate.")
        for _ in range(kinds["steal"]):
            card = self._random_card(opp["hand"])
            opp["hand"][card] -= 1
            me["hand"][card] += 1
            self._log(f"{self._name(p)} steals {card} from {self._name(o)}.")
        if _count(wanted):
            for r, n in wanted.items():
                me["hand"][r] += n
            self._log(f"{self._name(p)} takes {self._describe(wanted)}.")
        for _ in range(kinds["dev_card"]):
            self._draw_dev(p)
        if kinds["route"]:
            self._add_free_routes(p, kinds["route"])

    # --- card bank

    def _act_deposit(self, p: int, a: dict) -> None:
        self._require(self.phase == "play", "The game isn't in progress.")
        self._require(not self.pending, "Wait until nothing is being resolved.")
        cards = _clean_cards(a.get("cards"))
        n = _count(cards)
        self._require(n > 0, "Choose cards to bank.")
        self._require(self._has_cards(p, cards), "You don't have those cards.")
        for r, k in cards.items():
            self.players[p]["hand"][r] -= k
            self.players[p]["bank"][r] += k
        self._log(f"{self._name(p)} banks {n} card{'s' if n > 1 else ''}.")

    # --- old boot

    def can_pass_boot(self, p: int) -> bool:
        return (self.phase == "play" and p == self.current and self.rolled and not self.pending
                and self.boot_holder == p and self.public_vp(1 - p) > self.public_vp(p))

    def _act_pass_boot(self, p: int, a: dict) -> None:
        self._require_main_phase(p)
        self._require(self.boot_holder == p, "You don't have the old boot.")
        self._require(self.public_vp(1 - p) > self.public_vp(p),
                      "You can only pass the boot to a player with more VP.")
        self.boot_holder = 1 - p
        self._log(f"{self._name(p)} passes the old boot to {self._name(1 - p)}.")

    # --- moving ships

    def _ship_has_open_end(self, p: int, e: int) -> bool:
        for v in self.topo.edges[e].vertices:
            b = self.buildings.get(v)
            if b is not None and b["owner"] == p:
                continue
            if not any(
                e2 != e and self.routes.get(e2, {}).get("owner") == p and self.routes[e2]["kind"] == "ship"
                for e2 in self.topo.vertices[v].edges
            ):
                return True
        return False

    def movable_ships(self, p: int) -> list[int]:
        if self.ship_moved:
            return []
        blocked = self._pirate_edges()
        return [
            e for e, r in self.routes.items()
            if r["owner"] == p and r["kind"] == "ship" and r["turn"] != self.turn_number
            and e not in blocked and self._ship_has_open_end(p, e)
        ]

    def _act_move_ship(self, p: int, a: dict) -> None:
        self._require_main_phase(p)
        src, dst = self._int_arg(a, "from"), self._int_arg(a, "to")
        self._require(not self.ship_moved, "You've already moved a ship this turn.")
        self._require(src in self.movable_ships(p), "That ship can't be moved.")
        self._require(dst in self.legal_ships(p, ignore=src), "The ship can't go there.")
        self.routes[dst] = self.routes.pop(src)
        self.ship_moved = True
        self._log(f"{self._name(p)} moves a ship.")
        self._update_longest_route()

    # ------------------------------------------------------------------ views

    def legal_for(self, p: int) -> dict:
        """Board spots where ``p`` could place things right now, for the client to highlight."""
        legal = {}
        if self.phase == "setup":
            if self.setup_order[self.setup_step] == p and not self.pending:
                if self.setup_awaiting == "settlement":
                    legal["settlement"] = self.legal_settlements(p)
                else:
                    legal["road"] = self.legal_roads(p)
                    legal["ship"] = self.legal_ships(p)
            return legal
        if self.phase != "play" or p != self.current:
            return legal
        if self._pending_for("robber", p) and not any(i["type"] == "discard" for i in self.pending):
            legal["robber"] = self.legal_robber_hexes()
            legal["pirate"] = self.legal_pirate_hexes()
        if self._pending_for("free_routes", p):
            legal["road"] = self.legal_roads(p)
            legal["ship"] = self.legal_ships(p)
        if not self.pending and self.rolled:
            if self._settlement_piece_available(p):
                legal["settlement"] = self.legal_settlements(p)
            if self._city_piece_available(p):
                legal["city"] = self.legal_cities(p)
            legal["road"] = self.legal_roads(p)
            legal["ship"] = self.legal_ships(p)
            movable = self.movable_ships(p)
            if movable:
                legal["move_ship"] = movable
                legal["ship_targets"] = {e: self.legal_ships(p, ignore=e) for e in movable}
        return legal

    def view_for(self, me: int | None) -> dict:
        players = []
        for i, pl in enumerate(self.players):
            s, c = self._piece_counts(i)
            info = {
                "colour": PLAYER_COLOURS[i],
                "vp": self.public_vp(i),
                "vp_needed": self.vp_needed(i),
                "hand_count": _count(pl["hand"]),
                "bank_count": _count(pl["bank"]),
                "fish_count": len(pl["fish"]),
                "dev_count": len(pl["dev"]),
                "knights": pl["knights"],
                "settlements": s,
                "cities": c,
                "route_length": self.route_length(i),
                "longest_route": self.longest_route == i,
                "largest_army": self.largest_army == i,
                "boot": self.boot_holder == i,
            }
            if i == me or self.phase == "finished":
                info.update({
                    "hand": dict(pl["hand"]),
                    "bank": dict(pl["bank"]),
                    "fish": sorted(pl["fish"]),
                    "dev": [dict(d, new=d["turn"] == self.turn_number) for d in pl["dev"]],
                    "total_vp": self.total_vp(i),
                })
            players.append(info)

        log = []
        for entry in self.log[-60:]:
            text = entry.get("private", {}).get(str(me), entry["text"])
            log.append({"n": entry["n"], "text": text})

        return {
            "me": me,
            "phase": self.phase,
            "current": self.current,
            "turn": self.turn_number,
            "setup": {
                "player": self.setup_order[self.setup_step] if self.phase == "setup" else None,
                "awaiting": self.setup_awaiting if self.phase == "setup" else None,
            },
            "rolled": self.rolled,
            "dice": self.dice,
            "pending": [dict(i) for i in self.pending],
            "players": players,
            "buildings": [{"vertex": v, **b} for v, b in self.buildings.items()],
            "routes": [{"edge": e, "owner": r["owner"], "kind": r["kind"]} for e, r in self.routes.items()],
            "robber": self.robber,
            "pirate": self.pirate,
            "dev_deck": len(self.dev_deck),
            "fish_bag": len(self.fish_bag) + len(self.fish_spent),
            "trade": self.trade,
            "winner": self.winner,
            "log": log,
            "legal": self.legal_for(me) if me is not None else {},
            "costs": COSTS,
            "fish_prices": FISH_PRICES,
            "rates": self.trade_rates(me) if me is not None else {},
            "playable_dev": self.playable_dev(me) if me is not None else [],
            "can_pass_boot": self.can_pass_boot(me) if me is not None else False,
            "ship_moved": self.ship_moved,
            "dev_played": self.dev_played,
        }

    # ------------------------------------------------------------ persistence

    _STATE_KEYS = (
        "players", "phase", "first_player", "current", "turn_number", "setup_order",
        "setup_step", "setup_awaiting", "setup_vertex", "rolled", "dice", "pending",
        "robber", "pirate", "dev_deck", "fish_bag", "fish_spent", "boot_holder",
        "longest_route", "largest_army", "ship_moved", "dev_played", "trade", "winner", "log",
    )

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in self._STATE_KEYS}
        d["buildings"] = [[v, b["owner"], b["kind"]] for v, b in self.buildings.items()]
        d["routes"] = [[e, r["owner"], r["kind"], r["turn"]] for e, r in self.routes.items()]
        d["board"] = self.board.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict, rng: random.Random | None = None) -> "Game":
        state = {k: d[k] for k in cls._STATE_KEYS}
        state["buildings"] = {v: {"owner": o, "kind": k} for v, o, k in d["buildings"]}
        state["routes"] = {e: {"owner": o, "kind": k, "turn": t} for e, o, k, t in d["routes"]}
        return cls(Board.from_dict(d["board"]), rng=rng, _state=state)
