import json
import random

import pytest

from settlers.engine.board import generate_board
from settlers.engine.constants import BOOT
from settlers.engine.game import Game, RuleError

from .helpers import (
    TOPO,
    Dice,
    edge_between,
    give,
    hex_at,
    make_board,
    make_game,
    path_edges,
    place,
)

H = hex_at(3, 3)  # a hex in the middle of the board


def act(game, p, type_, **kw):
    game.act(p, {"type": type_, **kw})


# ---------------------------------------------------------------- setup


def run_setup(game):
    for step in range(4):
        p = game.setup_order[step]
        assert game.current == p
        v = game.legal_settlements(p)[0]
        act(game, p, "build_settlement", vertex=v)
        legal = game.legal_for(p)
        if legal.get("road"):
            act(game, p, "build_road", edge=legal["road"][0])
        else:
            act(game, p, "build_ship", edge=legal["ship"][0])
    for item in list(game.pending):
        act(game, item["player"], "choose_gold", cards={"ore": item["count"]})


def test_setup_snake_order_and_start_of_play():
    game = Game(generate_board(random.Random(3)), first_player=1, rng=Dice())
    assert game.setup_order == [1, 0, 0, 1]
    run_setup(game)
    assert game.phase == "play"
    assert game.current == 1
    assert game.turn_number == 1
    assert sum(1 for b in game.buildings.values() if b["owner"] == 0) == 2
    assert len(game.routes) == 4


def test_setup_rules_enforced():
    game = make_game(play=False)
    v = H.corners[0]
    with pytest.raises(RuleError):
        act(game, 1, "build_settlement", vertex=v)  # not blue's placement
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=H.edges[0])  # settlement first
    act(game, 0, "build_settlement", vertex=v)
    far = next(e.id for e in TOPO.edges if v not in e.vertices)
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=far)  # must touch the new settlement
    act(game, 0, "build_road", edge=H.edges[0])
    with pytest.raises(RuleError):
        act(game, 1, "build_settlement", vertex=H.corners[1])  # distance rule


def land_edge(game, v):
    return next(e for e in TOPO.vertices[v].edges if game._edge_touches_land(e))


def place_setup(game, vertices):
    """Place the four starting settlements (in setup order) with a road each."""
    for step, v in enumerate(vertices):
        p = game.setup_order[step]
        act(game, p, "build_settlement", vertex=v)
        act(game, p, "build_road", edge=land_edge(game, v))


def test_starting_cards_and_fish_arrive_after_setup():
    v1 = H.corners[0]  # shared by H and the two hexes above it
    others = [h for h in TOPO.vertices[v1].hexes if h != H.id]
    sea = hex_at(5, 6)
    fishery = {"hex": sea.id, "corner": 0, "number": 4,
               "vertices": [sea.corners[5], sea.corners[0], sea.corners[1]]}
    board = make_board(terrain={H.id: "forest", others[0]: "hills", others[1]: "lake", sea.id: "sea"},
                       numbers={H.id: 5, others[0]: 6}, fisheries=[fishery])
    game = make_game(board, play=False)
    game.fish_bag = [1] * 20
    blue = [hex_at(0, 7).corners[3], hex_at(7, 0).corners[0]]
    act(game, 0, "build_settlement", vertex=v1)
    assert sum(game.players[0]["hand"].values()) == 0  # nothing until setup ends
    act(game, 0, "build_road", edge=land_edge(game, v1))
    for v in blue:
        act(game, 1, "build_settlement", vertex=v)
        act(game, 1, "build_road", edge=land_edge(game, v))
    act(game, 0, "build_settlement", vertex=sea.corners[0])
    assert game.players[0]["fish"] == []
    act(game, 0, "build_road", edge=land_edge(game, sea.corners[0]))

    assert game.phase == "play"
    assert game.players[0]["hand"] == {"wood": 1, "brick": 1, "sheep": 2, "wheat": 0, "ore": 0}
    assert game.players[0]["fish"] == [1, 1]  # lake + fishing ground
    assert game.players[1]["hand"]["sheep"] == 2


def test_starting_gold_is_picked_before_the_first_roll():
    board = make_board(terrain={H.id: "gold"}, numbers={H.id: 8})
    game = make_game(board, play=False)
    place_setup(game, [H.corners[0], hex_at(0, 7).corners[3], hex_at(7, 0).corners[0],
                       hex_at(0, 0).corners[0]])
    assert game._pending_for("gold", 0)["count"] == 1
    with pytest.raises(RuleError):
        act(game, 0, "roll")
    with pytest.raises(RuleError):
        act(game, 0, "choose_gold", cards={"ore": 2})
    act(game, 0, "choose_gold", cards={"ore": 1})
    assert game.players[0]["hand"]["ore"] == 1
    game.rng.roll(1, 2)
    act(game, 0, "roll")


# ------------------------------------------------------------ production


def test_production_and_robber_block():
    board = make_board(terrain={H.id: "fields"}, numbers={H.id: 6})
    game = make_game(board)
    place(game, 0, H.corners[0])
    place(game, 1, H.corners[3], kind="city")
    game.rng.roll(3, 3)
    act(game, 0, "roll")
    assert game.players[0]["hand"]["wheat"] == 1
    assert game.players[1]["hand"]["wheat"] == 2

    game.robber = H.id
    game.rolled = False
    game.rng.roll(2, 4)
    act(game, 0, "roll")
    assert game.players[0]["hand"]["wheat"] == 1


def test_gold_production_is_chosen():
    board = make_board(terrain={H.id: "gold"}, numbers={H.id: 9})
    game = make_game(board)
    place(game, 0, H.corners[0], kind="city")
    game.rng.roll(4, 5)
    act(game, 0, "roll")
    assert game._pending_for("gold", 0)["count"] == 2
    with pytest.raises(RuleError):
        act(game, 0, "end_turn")
    act(game, 0, "choose_gold", cards={"brick": 1, "wood": 1})
    assert game.players[0]["hand"]["brick"] == 1 and game.players[0]["hand"]["wood"] == 1
    act(game, 0, "end_turn")


def fishery_game(pirate=False):
    sea = H
    fishery = {"hex": sea.id, "corner": 0, "number": 4,
               "vertices": [sea.corners[5], sea.corners[0], sea.corners[1]]}
    game = make_game(make_board(terrain={sea.id: "sea"}, fisheries=[fishery]))
    game.fish_bag = [1] * 29
    if pirate:
        game.pirate = sea.id
    return game, fishery["vertices"]


@pytest.mark.parametrize("pieces, normal, halved", [
    ([("settlement", 1)], 1, 0),
    ([("city", 1)], 2, 1),
    ([("city", 0), ("settlement", 2)], 3, 1),
    ([("city", 0), ("city", 2)], 4, 2),
])
def test_fishery_production_and_pirate_halving(pieces, normal, halved):
    for pirate, expected in ((False, normal), (True, halved)):
        game, verts = fishery_game(pirate)
        for kind, idx in pieces:
            place(game, 0, verts[idx], kind=kind)
        game.rng.roll(1, 3)
        act(game, 0, "roll")
        assert len(game.players[0]["fish"]) == expected


def test_lake_production_and_robber():
    board = make_board(terrain={H.id: "lake"})
    game = make_game(board)
    game.fish_bag = [2] * 29
    place(game, 1, H.corners[2], kind="city")
    game.rng.roll(1, 1)
    act(game, 0, "roll")
    assert game.players[1]["fish"] == [2, 2]

    game.robber = H.id
    game.rolled = False
    game.rng.roll(6, 6)
    act(game, 0, "roll")
    assert game.players[1]["fish"] == [2, 2]


def test_fish_shortage_and_reshuffle():
    game, verts = fishery_game()
    place(game, 0, verts[0], kind="city")
    game.fish_bag, game.fish_spent = [3], []
    game.rng.roll(2, 2)
    act(game, 0, "roll")
    assert game.players[0]["fish"] == []  # needed 2, only 1 left: nobody gets any

    game.rolled = False
    game.fish_bag, game.fish_spent = [], [1, 1]
    game.rng.roll(2, 2)
    act(game, 0, "roll")
    assert game.players[0]["fish"] == [1, 1]


def test_old_boot():
    game, verts = fishery_game()
    place(game, 0, verts[0])
    game.fish_bag = [BOOT]
    game.rng.roll(2, 2)
    act(game, 0, "roll")
    assert game.boot_holder == 0
    assert game.players[0]["fish"] == []
    assert game.vp_needed(0) == 15 and game.vp_needed(1) == 14


# --------------------------------------------------------------- the 7


def seven_game():
    game = make_game(make_board(terrain={hex_at(3, 2).id: "sea"}))
    place(game, 1, H.corners[3])
    give(game, 0, wood=5, ore=4)  # 9 cards
    give(game, 1, sheep=8)  # 8 cards
    game.rng.roll(3, 4)
    act(game, 0, "roll")
    return game


def test_seven_discards_then_robber():
    game = seven_game()
    assert game._pending_for("discard", 0)["count"] == 4
    assert game._pending_for("discard", 1)["count"] == 4
    with pytest.raises(RuleError):
        act(game, 0, "move_robber", piece="robber", hex=H.id, take="steal")
    with pytest.raises(RuleError):
        act(game, 0, "discard", cards={"wood": 3})
    with pytest.raises(RuleError):
        act(game, 0, "discard", cards={"brick": 4})
    act(game, 0, "discard", cards={"wood": 4})
    act(game, 1, "discard", cards={"sheep": 4})
    act(game, 0, "move_robber", piece="robber", hex=H.id, take="steal")
    assert game.robber == H.id
    assert game.players[0]["hand"]["sheep"] == 1
    assert game.players[1]["hand"]["sheep"] == 3


def test_robber_can_take_from_supply_instead():
    game = seven_game()
    act(game, 0, "discard", cards={"wood": 4})
    act(game, 1, "discard", cards={"sheep": 4})
    act(game, 0, "move_robber", piece="robber", hex=H.id, take="brick")
    assert game.players[0]["hand"]["brick"] == 1
    assert game.players[1]["hand"]["sheep"] == 4


def test_robber_rules():
    game = seven_game()
    act(game, 0, "discard", cards={"wood": 4})
    act(game, 1, "discard", cards={"sheep": 4})
    far = hex_at(0, 0).id
    with pytest.raises(RuleError):
        act(game, 0, "move_robber", piece="robber", hex=far, take="steal")  # nobody there
    with pytest.raises(RuleError):
        act(game, 0, "move_robber", piece="robber", hex=hex_at(3, 2).id, take="ore")  # sea
    with pytest.raises(RuleError):
        act(game, 0, "move_robber", piece="pirate", hex=H.id, take="ore")  # land
    act(game, 0, "move_robber", piece="robber", hex=far, take="ore")
    game.pending.append({"type": "robber", "player": 0})
    with pytest.raises(RuleError):
        act(game, 0, "move_robber", piece="robber", hex=far, take="ore")  # must move


def test_pirate_steals_from_ship_owner_and_blocks_ships():
    sea = hex_at(3, 2)
    game = make_game(make_board(terrain={sea.id: "sea"}))
    place(game, 1, sea.corners[3], edges=[sea.edges[3]], route="ship")
    give(game, 1, ore=2)
    game.pending.append({"type": "robber", "player": 0})
    game.rolled = True
    act(game, 0, "move_robber", piece="pirate", hex=sea.id, take="steal")
    assert game.pirate == sea.id
    assert game.players[0]["hand"]["ore"] == 1
    # No new ships on the pirate's edges.
    place(game, 0, sea.corners[0])
    give(game, 0, wood=1, sheep=1)
    with pytest.raises(RuleError):
        act(game, 0, "build_ship", edge=sea.edges[0])


# ------------------------------------------------------------- building


def test_build_costs_and_connections():
    game = make_game()
    v = H.corners[0]
    place(game, 0, v)
    game.rolled = True
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=H.edges[0])  # can't afford
    give(game, 0, wood=3, brick=3, sheep=1, wheat=1)
    act(game, 0, "build_road", edge=H.edges[0])
    assert game.players[0]["hand"]["wood"] == 2
    far = next(e.id for e in TOPO.edges
               if not set(e.vertices) & {v, H.corners[1]})
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=far)
    with pytest.raises(RuleError):
        act(game, 0, "build_settlement", vertex=H.corners[1])  # distance rule
    act(game, 0, "build_road", edge=H.edges[1])
    act(game, 0, "build_settlement", vertex=H.corners[2])
    assert game.buildings[H.corners[2]]["owner"] == 0


def test_must_roll_before_building():
    game = make_game()
    place(game, 0, H.corners[0])
    give(game, 0, wood=1, brick=1)
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=H.edges[0])


def test_opponent_building_blocks_routes():
    game = make_game()
    game.rolled = True
    place(game, 0, H.corners[0], edges=[H.edges[0]])
    place(game, 1, H.corners[1])
    give(game, 0, wood=1, brick=1)
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=H.edges[1])


def test_ships_join_roads_only_at_buildings():
    sea = hex_at(3, 2)
    game = make_game(make_board(terrain={sea.id: "sea"}))
    game.rolled = True
    # Red road reaching corner 3 of the sea hex (a coastal corner) with no building there.
    v = sea.corners[3]
    land_edge = next(e for e in TOPO.vertices[v].edges if all(
        game.board.is_land(h) for h in TOPO.edges[e].hexes))
    place(game, 0, edges=[land_edge])
    give(game, 0, wood=2, sheep=2)
    with pytest.raises(RuleError):
        act(game, 0, "build_ship", edge=sea.edges[3])
    place(game, 0, v)
    act(game, 0, "build_ship", edge=sea.edges[3])
    with pytest.raises(RuleError):
        act(game, 0, "build_road", edge=sea.edges[3])  # edge already taken


def test_city_upgrade():
    game = make_game()
    game.rolled = True
    place(game, 0, H.corners[0])
    give(game, 0, wheat=2, ore=3)
    with pytest.raises(RuleError):
        act(game, 0, "build_city", vertex=H.corners[3])
    act(game, 0, "build_city", vertex=H.corners[0])
    assert game.buildings[H.corners[0]]["kind"] == "city"
    assert game.public_vp(0) == 2


def spread_vertices(n):
    chosen = []
    for v in TOPO.vertices:
        if all(v.id != c and v.id not in TOPO.vertices[c].neighbours for c in chosen):
            if all(n2 not in chosen for n2 in v.neighbours):
                chosen.append(v.id)
        if len(chosen) == n:
            return chosen
    raise AssertionError


def test_piece_limits_switch_on_and_off():
    game = make_game()
    game.rolled = True
    game.vp_needed = lambda p: 99  # keep the game going past 14 VP
    spots = spread_vertices(12)
    for v in spots[:5]:
        place(game, 0, v)
    for v in spots[5:9]:
        place(game, 0, v, kind="city")
    give(game, 0, wheat=10, ore=15, wood=5, brick=5, sheep=5)
    # 5 settlements + 4 cities: limits are off, so a 5th city is fine.
    act(game, 0, "build_city", vertex=spots[0])
    # Now 4 settlements / 5 cities: no more cities until back to 5 settlements.
    with pytest.raises(RuleError):
        act(game, 0, "build_city", vertex=spots[1])
    new = spots[9]
    place(game, 0, edges=[TOPO.vertices[new].edges[0]])
    act(game, 0, "build_settlement", vertex=new)
    act(game, 0, "build_city", vertex=spots[1])


def test_settlement_limit_before_cities():
    game = make_game()
    game.rolled = True
    spots = spread_vertices(7)
    for v in spots[:5]:
        place(game, 0, v)
    place(game, 0, edges=[TOPO.vertices[spots[5]].edges[0]])
    give(game, 0, wood=1, brick=1, sheep=1, wheat=1)
    with pytest.raises(RuleError):
        act(game, 0, "build_settlement", vertex=spots[5])


# ------------------------------------------------------- scoring and end


def test_longest_route_title_and_break():
    game = make_game()
    game.rolled = True
    start = H.corners[0]
    edges, verts = path_edges(start, 5)
    place(game, 0, start, edges=edges[:4])
    give(game, 0, wood=1, brick=1)
    act(game, 0, "build_road", edge=edges[4])
    assert game.route_length(0) == 5
    assert game.longest_route == 0
    assert game.public_vp(0) == 2  # settlement + longest route (1 VP)
    # Blue settles in the middle of the chain: 2 + 3, nobody has 5.
    place(game, 1, verts[2])
    game._update_longest_route()
    assert game.route_length(0) == 3
    assert game.longest_route is None


def test_roads_and_ships_chain_only_through_own_building():
    game = make_game()
    edges, verts = path_edges(H.corners[0], 6)
    place(game, 0, edges=edges[:3])
    place(game, 0, edges=edges[3:], route="ship")
    assert game.route_length(0) == 3
    place(game, 0, verts[3])
    assert game.route_length(0) == 6


def test_winning_on_your_turn():
    game = make_game()
    game.rolled = True
    spots = spread_vertices(10)
    for v in spots[:6]:
        place(game, 0, v, kind="city")
    place(game, 0, spots[6])  # 13 VP
    place(game, 0, edges=[TOPO.vertices[spots[7]].edges[0]])
    give(game, 0, wood=1, brick=1, sheep=1, wheat=1)
    act(game, 0, "build_settlement", vertex=spots[7])
    assert game.phase == "finished" and game.winner == 0
    with pytest.raises(RuleError):
        act(game, 1, "roll")


def test_boot_raises_the_target():
    game = make_game()
    game.rolled = True
    game.boot_holder = 0
    spots = spread_vertices(10)
    for v in spots[:6]:
        place(game, 0, v, kind="city")
    place(game, 0, spots[6])
    place(game, 0, edges=[TOPO.vertices[spots[7]].edges[0]])
    give(game, 0, wood=1, brick=1, sheep=1, wheat=1)
    act(game, 0, "build_settlement", vertex=spots[7])
    assert game.phase == "play"


def test_end_turn():
    game = make_game()
    with pytest.raises(RuleError):
        act(game, 0, "end_turn")
    with pytest.raises(RuleError):
        act(game, 1, "roll")
    game.rng.roll(2, 3)
    act(game, 0, "roll")
    act(game, 0, "end_turn")
    assert game.current == 1 and not game.rolled and game.turn_number == 2


def test_state_roundtrip_through_json():
    game = Game(generate_board(random.Random(5)), first_player=0, rng=Dice())
    run_setup(game)
    game.rng.roll(2, 3)
    act(game, 0, "roll")
    data = json.loads(json.dumps(game.to_dict()))
    again = Game.from_dict(data, rng=Dice())
    for p in (0, 1, None):
        assert again.view_for(p) == game.view_for(p)


def test_views_hide_opponent_details():
    game = make_game()
    give(game, 1, ore=3)
    game.players[1]["fish"] = [3, 1]
    view = game.view_for(0)
    blue = view["players"][1]
    assert blue["hand_count"] == 3 and blue["fish_count"] == 2
    assert "hand" not in blue and "fish" not in blue
    assert view["players"][0]["hand"]["ore"] == 0


def test_unknown_or_malformed_actions():
    game = make_game()
    for bad in ({"type": "nope"}, {"type": "build_road"}, {"type": "build_road", "edge": "3"},
                {"type": "choose_gold", "cards": {"gold": 1}}, "roll", None):
        with pytest.raises(RuleError):
            game.act(0, bad)


# ------------------------------------------------------------------ names


def test_names_are_cleaned():
    from settlers.engine.game import clean_names

    assert clean_names(None) == ["Red", "Blue"]
    assert clean_names(["  Finn  ", ""]) == ["Finn", "Blue"]
    assert clean_names(["A{0}b", "x" * 50]) == ["A0b", "x" * 20]
    assert clean_names(["Sam\u0007  Lee", "Jo"]) == ["Sam Lee", "Jo"]
    for bad in (["Sam", "sam"], ["Sam"], "Sam", [1, 2]):
        with pytest.raises(RuleError):
            clean_names(bad)


def test_log_refers_to_players_by_placeholder():
    game = Game(make_board(), first_player=1, rng=Dice(), names=["Ann", "Bo"])
    assert game.log[0]["text"] == "{1} places first."
    view = game.view_for(0)
    assert view["names"] == ["Ann", "Bo"]


def test_error_messages_use_real_names():
    game = make_game(Game(make_board(), rng=Dice(), names=["Ann", "Bo"]).board)
    game.names = ["Ann", "Bo"]
    game.rolled = True
    place(game, 1, H.corners[3])
    game.pending.append({"type": "robber", "player": 0})
    with pytest.raises(RuleError, match="Bo has no cards"):
        act(game, 0, "move_robber", piece="robber", hex=H.id, take="steal")
