"""Undoing your own moves on your own turn, and what locks them in."""

import json

import pytest

from settlers.engine.game import Game, RuleError

from .helpers import TOPO, give, hex_at, make_board, make_game, path_edges, place

H = hex_at(3, 3)


def act(game, p, type_, **kw):
    game.act(p, {"type": type_, **kw})


def main_phase(game, p=0):
    game.current = p
    game.rolled = True
    return game


def with_road_start(game, p=0):
    """A settlement for p at H's first corner, and the free edges next to it."""
    v = H.corners[0]
    place(game, p, v)
    return [e for e in TOPO.vertices[v].edges if game._edge_touches_land(e)]


def test_undo_a_road():
    game = main_phase(make_game())
    edges = with_road_start(game)
    give(game, 0, wood=1, brick=1)
    act(game, 0, "build_road", edge=edges[0])
    assert game.can_undo(0) and not game.can_undo(1)
    act(game, 0, "undo")
    assert edges[0] not in game.routes
    assert game.players[0]["hand"]["wood"] == 1 and game.players[0]["hand"]["brick"] == 1
    assert not game.can_undo(0)
    log = game.view_for(1)["log"]
    assert log[-2] == {"n": log[-2]["n"], "text": "{0} builds a road.", "undone": True}
    assert log[-1]["text"] == "{0} undoes: builds a road."
    with pytest.raises(RuleError):
        act(game, 0, "undo")


def test_undo_steps_back_one_move_at_a_time():
    game = main_phase(make_game())
    edges = with_road_start(game)
    give(game, 0, wood=2, brick=2, sheep=4)
    act(game, 0, "build_road", edge=edges[0])
    act(game, 0, "maritime", give="sheep", get="wood")
    act(game, 0, "deposit", cards={"brick": 1})
    act(game, 0, "undo")
    assert game.players[0]["bank"]["brick"] == 0 and game.players[0]["hand"]["brick"] == 1
    act(game, 0, "undo")
    assert game.players[0]["hand"]["sheep"] == 4 and game.players[0]["hand"]["wood"] == 1
    assert edges[0] in game.routes
    act(game, 0, "undo")
    assert edges[0] not in game.routes
    assert game.players[0]["hand"] == {"wood": 2, "brick": 2, "sheep": 4, "wheat": 0, "ore": 0}


def test_the_roll_locks_in_what_came_before():
    game = make_game()
    edges = with_road_start(game)
    give(game, 0, wood=1, brick=1)
    act(game, 0, "deposit", cards={"wood": 1})
    assert game.can_undo(0)  # before rolling is still your turn
    game.rng.roll(1, 2)
    act(game, 0, "roll")
    assert not game.can_undo(0)
    with pytest.raises(RuleError):
        act(game, 0, "undo")
    assert game.players[0]["bank"]["wood"] == 1


BARRIERS = ["buy_dev", "offer_trade", "opponent_offer", "declined", "cancelled", "accepted",
            "opponent_deposit", "pass_boot", "end_turn"]


@pytest.mark.parametrize("barrier", BARRIERS)
def test_barriers(barrier):
    game = main_phase(make_game())
    edges = with_road_start(game)
    give(game, 0, wood=1, brick=1, sheep=1, wheat=1, ore=1)
    give(game, 1, ore=1)
    if barrier in ("declined", "cancelled", "accepted"):
        act(game, 0, "offer_trade", give={"sheep": 1}, get={"ore": 1})
    act(game, 0, "build_road", edge=edges[0])
    if barrier == "buy_dev":
        act(game, 0, "buy_dev")
    elif barrier == "offer_trade":
        act(game, 0, "offer_trade", give={"sheep": 1}, get={"ore": 1})
    elif barrier == "opponent_offer":
        act(game, 1, "offer_trade", give={"ore": 1}, get={"sheep": 1})
    elif barrier in ("declined", "cancelled", "accepted"):
        assert game.can_undo(0)  # the road came after the offer
        who, kind = {"declined": (1, "decline_trade"), "cancelled": (0, "cancel_trade"),
                     "accepted": (1, "accept_trade")}[barrier]
        act(game, who, kind)
    elif barrier == "opponent_deposit":
        act(game, 1, "deposit", cards={"ore": 1})
    elif barrier == "pass_boot":
        game.boot_holder = 0
        place(game, 1, hex_at(0, 0).corners[0], kind="city")
        act(game, 0, "pass_boot")
    else:
        act(game, 0, "end_turn")
    assert not game.can_undo(0)
    with pytest.raises(RuleError):
        act(game, 0, "undo")
    assert edges[0] in game.routes


def test_only_the_mover_can_undo():
    game = main_phase(make_game())
    edges = with_road_start(game)
    give(game, 0, wood=1, brick=1)
    act(game, 0, "build_road", edge=edges[0])
    with pytest.raises(RuleError):
        act(game, 1, "undo")
    assert game.view_for(1)["can_undo"] is False and game.view_for(0)["can_undo"] is True


def test_depositing_on_the_opponents_turn_is_not_undoable():
    game = main_phase(make_game(), p=1)
    give(game, 0, wood=1)
    act(game, 0, "deposit", cards={"wood": 1})
    assert not game.can_undo(0)


def test_fish_spending_undo_depends_on_the_purchase():
    game = main_phase(make_game())
    give(game, 1, ore=2)
    game.players[0]["fish"] = [3, 2, 2]
    act(game, 0, "fish", tokens=[2, 2], items=[{"kind": "resource", "resource": "ore"}])
    act(game, 0, "undo")
    assert sorted(game.players[0]["fish"]) == [2, 2, 3]
    assert game.fish_spent == [] and game.players[0]["hand"]["ore"] == 0
    act(game, 0, "fish", tokens=[3], items=[{"kind": "steal"}])
    assert not game.can_undo(0)


@pytest.mark.parametrize("take", ["wheat", "steal"])
def test_moving_the_robber_is_final(take):
    game = main_phase(make_game())
    place(game, 1, H.corners[3])
    give(game, 1, ore=1)
    game.turn_number = 3
    game.players[0]["dev"] = [{"card": "knight", "turn": 1}]
    act(game, 0, "play_dev", card="knight")
    assert game.can_undo(0)
    act(game, 0, "move_robber", piece="robber", hex=H.id, take=take)
    assert not game.can_undo(0)


def test_knight_and_year_of_plenty_undo_but_monopoly_does_not():
    game = main_phase(make_game())
    game.turn_number = 3
    game.players[0]["dev"] = [{"card": c, "turn": 1} for c in ("knight", "year_of_plenty", "monopoly")]
    act(game, 0, "play_dev", card="knight")
    act(game, 0, "undo")
    assert game.players[0]["knights"] == 0 and not game.dev_played and not game.pending
    act(game, 0, "play_dev", card="year_of_plenty", cards={"ore": 2})
    act(game, 0, "undo")
    assert game.players[0]["hand"]["ore"] == 0 and len(game.players[0]["dev"]) == 3
    give(game, 1, sheep=2)
    act(game, 0, "play_dev", card="monopoly", resource="sheep")
    assert not game.can_undo(0)


def test_undoing_a_road_takes_back_the_title():
    game = main_phase(make_game())
    start = H.corners[0]
    edges, _ = path_edges(start, 5)
    place(game, 0, start, edges=edges[:4])
    give(game, 0, wood=1, brick=1)
    act(game, 0, "build_road", edge=edges[4])
    assert game.longest_route == 0 and game.route_lengths[0] == 5
    act(game, 0, "undo")
    assert game.longest_route is None and game.route_lengths[0] == 4


def test_a_winning_move_is_final():
    game = main_phase(make_game())
    edges = with_road_start(game)
    game.players[0]["vp_cards"] = 12
    give(game, 0, wood=3, brick=3, sheep=1, wheat=1)
    target = next(v for v in TOPO.edges[edges[0]].vertices if v != H.corners[0])
    act(game, 0, "build_road", edge=edges[0])
    far = next(v for v in TOPO.vertices[target].neighbours if v != H.corners[0])
    far_edge = next(e for e in TOPO.vertices[target].edges if far in TOPO.edges[e].vertices)
    act(game, 0, "build_road", edge=far_edge)
    act(game, 0, "build_settlement", vertex=far)
    assert game.phase == "finished"
    with pytest.raises(RuleError):
        act(game, 0, "undo")


def test_undo_history_survives_a_save():
    game = main_phase(make_game())
    edges = with_road_start(game)
    give(game, 0, wood=1, brick=1)
    act(game, 0, "build_road", edge=edges[0])
    again = Game.from_dict(json.loads(json.dumps(game.to_dict())), rng=game.rng)
    act(again, 0, "undo")
    assert edges[0] not in again.routes and again.players[0]["hand"]["wood"] == 1


def test_saves_without_undo_history_still_load():
    game = main_phase(make_game())
    data = json.loads(json.dumps(game.to_dict()))
    del data["undo"]
    a, b = Game.from_dict(data), Game.from_dict(data)
    edges = with_road_start(a)
    give(a, 0, wood=1, brick=1)
    act(a, 0, "build_road", edge=edges[0])
    assert a.can_undo(0) and b.undo == []  # separate histories


# ------------------------------------------------------------------ setup


def setup_game():
    board = make_board()
    return Game(board, first_player=0, rng=make_game().rng)


def spot(game, p, avoid=()):
    return next(v for v in game.legal_settlements(p) if v not in avoid)


def placement(game, p):
    v = spot(game, p)
    act(game, p, "build_settlement", vertex=v)
    act(game, p, "build_road", edge=game.legal_for(p)["road"][0])
    return v


def test_setup_placement_waits_for_end_turn_and_can_be_undone():
    game = setup_game()
    v = placement(game, 0)
    assert game.setup_awaiting == "end" and game.current == 0
    assert game.legal_for(0) == {}
    with pytest.raises(RuleError):
        act(game, 1, "build_settlement", vertex=spot(game, 1))
    act(game, 0, "undo")
    assert game.setup_awaiting == "route" and game.legal_for(0)["road"]
    act(game, 0, "undo")
    assert game.setup_awaiting == "settlement" and v not in game.buildings and not game.routes
    placement(game, 0)
    act(game, 0, "end_turn")
    assert game.current == 1 and not game.can_undo(0)


def test_second_player_places_twice_then_ends_and_can_undo_both():
    game = setup_game()
    placement(game, 0)
    act(game, 0, "end_turn")
    placement(game, 1)
    assert game.setup_awaiting == "settlement" and game.setup_step == 2  # straight on
    with pytest.raises(RuleError):
        act(game, 1, "end_turn")
    placement(game, 1)
    assert game.setup_awaiting == "end"
    for _ in range(4):
        act(game, 1, "undo")
    assert game.setup_step == 1 and game.setup_awaiting == "settlement"
    assert sum(1 for b in game.buildings.values() if b["owner"] == 1) == 0


def test_last_end_turn_starts_the_game_and_is_final():
    game = setup_game()
    for p in (0, 1, 1, 0):
        placement(game, p)
        if game.setup_awaiting == "end":
            act(game, p, "end_turn")
    assert game.phase == "play" and game.current == 0 and game.turn_number == 1
    assert not game.can_undo(0)
