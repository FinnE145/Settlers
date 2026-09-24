"""Trading, development cards, fish, the card bank, the old boot and moving ships."""

import pytest

from settlers.engine.game import RuleError

from .helpers import TOPO, give, hex_at, make_board, make_game, path_edges, place

H = hex_at(3, 3)


def act(game, p, type_, **kw):
    game.act(p, {"type": type_, **kw})


def main_phase(game, p=0):
    game.current = p
    game.rolled = True
    return game


# ------------------------------------------------------------ harbours


def harbour_board():
    """Four harbours on far-apart edges: wood 2:1, brick 2:1, a 3:1 and ore 2:1."""
    spots = [hex_at(1, 1), hex_at(5, 1), hex_at(1, 5), hex_at(5, 5)]
    kinds = ["wood", "brick", "3:1", "ore"]
    harbours = [{"edge": h.edges[0], "kind": k} for h, k in zip(spots, kinds)]
    return make_board(harbours=harbours), [TOPO.edges[h.edges[0]].vertices[0] for h in spots]


def test_default_rate_is_four():
    game = main_phase(make_game())
    assert all(rate == 4 for row in game.trade_rates(0).values() for rate in row.values())


def test_harbour_rates_both_ways():
    board, spots = harbour_board()
    game = main_phase(make_game(board))
    place(game, 0, spots[0])  # wood 2:1
    place(game, 0, spots[2])  # 3:1
    rates = game.trade_rates(0)
    assert rates["wood"]["ore"] == 2  # 2 wood -> anything
    assert rates["sheep"]["wood"] == 2  # 2 of something else -> wood
    assert rates["sheep"]["ore"] == 3  # generic harbour
    assert rates["ore"]["brick"] == 3


def test_cities_on_two_harbours_trade_one_to_one():
    board, spots = harbour_board()
    game = main_phase(make_game(board))
    place(game, 0, spots[0], kind="city")
    place(game, 0, spots[1])  # only a settlement on brick
    assert game.trade_rates(0)["wood"]["brick"] == 2
    place(game, 0, spots[1], kind="city")
    rates = game.trade_rates(0)
    assert rates["wood"]["brick"] == 1 and rates["brick"]["wood"] == 1
    assert rates["wood"]["sheep"] == 2
    place(game, 0, spots[3], kind="city")
    assert game.trade_rates(0)["ore"]["wood"] == 1 and game.trade_rates(0)["brick"]["ore"] == 1


def test_maritime_trade():
    board, spots = harbour_board()
    game = make_game(board)
    place(game, 0, spots[0])
    give(game, 0, wood=2, sheep=1)
    with pytest.raises(RuleError):
        act(game, 0, "maritime", give="wood", get="ore")  # not rolled yet
    main_phase(game)
    act(game, 0, "maritime", give="wood", get="ore")
    assert game.players[0]["hand"]["wood"] == 0 and game.players[0]["hand"]["ore"] == 1
    with pytest.raises(RuleError):
        act(game, 0, "maritime", give="sheep", get="wood")  # needs 2 sheep
    with pytest.raises(RuleError):
        act(game, 0, "maritime", give="ore", get="ore")


# ---------------------------------------------------------- player trade


def test_player_trade_with_fish():
    game = main_phase(make_game())
    give(game, 0, wood=2)
    give(game, 1, ore=1)
    game.players[0]["fish"] = [3]
    game.players[1]["fish"] = [1, 2]
    with pytest.raises(RuleError):
        act(game, 0, "offer_trade", give={"wood": 1}, get={})  # no gifts
    with pytest.raises(RuleError):
        act(game, 0, "offer_trade", give={"wood": 3}, get={"ore": 1})
    act(game, 0, "offer_trade", give={"wood": 2}, give_fish=[3], get={"ore": 1}, get_fish=[2])
    with pytest.raises(RuleError):
        act(game, 0, "accept_trade")  # can't accept your own offer
    act(game, 1, "accept_trade")
    assert game.players[0]["hand"]["ore"] == 1 and game.players[1]["hand"]["wood"] == 2
    assert sorted(game.players[0]["fish"]) == [2]
    assert sorted(game.players[1]["fish"]) == [1, 3]
    assert game.trade is None


def test_trade_checks_the_other_side_on_accept():
    game = main_phase(make_game())
    give(game, 0, wood=1)
    act(game, 0, "offer_trade", give={"wood": 1}, get={"ore": 1})
    with pytest.raises(RuleError):
        act(game, 1, "accept_trade")
    act(game, 1, "decline_trade")
    assert game.trade is None


def test_counter_offer_and_cancel():
    game = main_phase(make_game())
    give(game, 0, wood=1)
    give(game, 1, ore=2)
    act(game, 0, "offer_trade", give={"wood": 1}, get={"ore": 2})
    act(game, 1, "offer_trade", give={"ore": 1}, get={"wood": 1})  # counter replaces it
    assert game.trade["from"] == 1
    with pytest.raises(RuleError):
        act(game, 0, "cancel_trade")
    act(game, 1, "cancel_trade")
    assert game.trade is None


def test_trading_needs_the_roll_and_ends_with_the_turn():
    game = make_game()
    give(game, 0, wood=1)
    with pytest.raises(RuleError):
        act(game, 0, "offer_trade", give={"wood": 1}, get={"ore": 1})
    main_phase(game)
    act(game, 0, "offer_trade", give={"wood": 1}, get={"ore": 1})
    act(game, 0, "end_turn")
    assert game.trade is None


# ------------------------------------------------------ development cards


def test_buy_and_play_rules():
    game = main_phase(make_game())
    game.dev_deck = ["knight", "knight"]
    give(game, 0, sheep=2, wheat=2, ore=2)
    act(game, 0, "buy_dev")
    assert game.players[0]["hand"] == {"wood": 0, "brick": 0, "sheep": 1, "wheat": 1, "ore": 1}
    with pytest.raises(RuleError):
        act(game, 0, "play_dev", card="knight")  # bought this turn
    act(game, 0, "end_turn")
    game.current, game.turn_number, game.rolled = 0, 3, False
    act(game, 0, "play_dev", card="knight")  # before rolling is fine
    assert game.players[0]["knights"] == 1
    assert game._pending_for("robber", 0)
    act(game, 0, "move_robber", piece="robber", hex=H.id, take="ore")
    game.players[0]["dev"].append({"card": "knight", "turn": 1})
    with pytest.raises(RuleError):
        act(game, 0, "play_dev", card="knight")  # one per turn


def test_largest_army():
    game = main_phase(make_game())
    game.turn_number = 5
    for p, n in ((0, 3), (1, 4)):
        game.players[p]["dev"] = [{"card": "knight", "turn": 1} for _ in range(n)]
    for i in range(3):
        game.dev_played = False
        game.pending = []
        act(game, 0, "play_dev", card="knight")
    assert game.largest_army == 0 and game.public_vp(0) == 2
    game.pending = []
    game.current = 1
    for i in range(3):
        game.dev_played = False
        game.pending = []
        act(game, 1, "play_dev", card="knight")
    assert game.largest_army == 0  # a tie doesn't take it
    game.dev_played = False
    game.pending = []
    act(game, 1, "play_dev", card="knight")
    assert game.largest_army == 1


def test_road_building_places_two_free_routes():
    game = main_phase(make_game())
    game.turn_number = 2
    game.players[0]["dev"] = [{"card": "road_building", "turn": 1}]
    edges, verts = path_edges(H.corners[0], 3)
    place(game, 0, H.corners[0])
    act(game, 0, "play_dev", card="road_building")
    with pytest.raises(RuleError):
        act(game, 0, "end_turn")
    act(game, 0, "build_road", edge=edges[0])
    act(game, 0, "build_road", edge=edges[1])
    assert not game.pending
    assert sum(game.players[0]["hand"].values()) == 0


def test_skip_free_routes():
    game = main_phase(make_game())
    game.pending.append({"type": "free_routes", "player": 0, "count": 2})
    act(game, 0, "skip_free_routes")
    assert not game.pending


def test_year_of_plenty_and_monopoly():
    game = main_phase(make_game())
    game.turn_number = 2
    game.players[0]["dev"] = [{"card": "year_of_plenty", "turn": 1}, {"card": "monopoly", "turn": 1}]
    with pytest.raises(RuleError):
        act(game, 0, "play_dev", card="year_of_plenty", cards={"ore": 3})
    act(game, 0, "play_dev", card="year_of_plenty", cards={"ore": 1, "wheat": 1})
    assert game.players[0]["hand"]["ore"] == 1
    game.dev_played = False
    give(game, 1, wood=3)
    game.players[1]["bank"]["wood"] = 2
    act(game, 0, "play_dev", card="monopoly", resource="wood")
    assert game.players[0]["hand"]["wood"] == 3
    assert game.players[1]["bank"]["wood"] == 2  # banked cards are safe


def test_victory_point_cards_count_but_cannot_be_played():
    game = main_phase(make_game())
    game.players[0]["dev"] = [{"card": "victory_point", "turn": 0}]
    assert game.total_vp(0) == game.public_vp(0) + 1
    with pytest.raises(RuleError):
        act(game, 0, "play_dev", card="victory_point")


# ------------------------------------------------------------------ fish


def test_one_token_can_pay_for_several_things():
    game = main_phase(make_game())
    game.players[0]["fish"] = [3]
    game.players[0]["bank"]["ore"] = 2
    game.robber = H.id
    act(game, 0, "fish", tokens=[3], items=[{"kind": "bank"}, {"kind": "remove_robber"}])
    assert game.players[0]["hand"]["ore"] == 2 and game.players[0]["bank"]["ore"] == 0
    assert game.robber is None
    assert game.players[0]["fish"] == [] and game.fish_spent[-1] == 3


def test_two_resources_for_three_three_two():
    game = main_phase(make_game())
    game.players[0]["fish"] = [3, 3, 2, 1]
    items = [{"kind": "resource", "resource": "ore"}, {"kind": "resource", "resource": "wheat"}]
    act(game, 0, "fish", tokens=[3, 3, 2], items=items)
    assert game.players[0]["hand"]["ore"] == 1 and game.players[0]["hand"]["wheat"] == 1
    assert game.players[0]["fish"] == [1]


def test_fish_payment_rules():
    game = main_phase(make_game())
    game.players[0]["fish"] = [1, 3, 3]
    with pytest.raises(RuleError):
        act(game, 0, "fish", tokens=[1], items=[{"kind": "resource", "resource": "ore"}])  # not enough
    with pytest.raises(RuleError):
        act(game, 0, "fish", tokens=[1, 3, 3], items=[{"kind": "resource", "resource": "ore"}])  # 1 is spare
    with pytest.raises(RuleError):
        act(game, 0, "fish", tokens=[3], items=[{"kind": "bank"}])  # bank is empty
    with pytest.raises(RuleError):
        act(game, 0, "fish", tokens=[3], items=[{"kind": "remove_robber"}])  # robber off the board
    with pytest.raises(RuleError):
        act(game, 0, "fish", tokens=[2], items=[{"kind": "remove_robber"}])  # no such token
    game.current = 1
    with pytest.raises(RuleError):
        act(game, 0, "fish", tokens=[3], items=[{"kind": "steal"}])  # not your turn


def test_fish_steal_dev_card_and_free_route():
    game = main_phase(make_game())
    game.players[0]["fish"] = [3, 3, 3, 3, 3]
    give(game, 1, ore=1)
    game.dev_deck = ["monopoly"]
    act(game, 0, "fish", tokens=[3], items=[{"kind": "steal"}])
    assert game.players[0]["hand"]["ore"] == 1
    act(game, 0, "fish", tokens=[3, 3, 3], items=[{"kind": "dev_card"}])
    assert game.players[0]["dev"][0]["card"] == "monopoly"
    game.players[0]["fish"] = [3, 2]
    act(game, 0, "fish", tokens=[3, 2], items=[{"kind": "route"}])
    assert game._pending_for("free_routes", 0)["count"] == 1


# -------------------------------------------------------------- card bank


def test_bank_protects_cards_and_can_be_used_anytime():
    game = main_phase(make_game())
    place(game, 1, H.corners[3])
    give(game, 1, ore=9)
    act(game, 1, "deposit", cards={"ore": 5})  # on red's turn
    assert game.players[1]["hand"]["ore"] == 4 and game.players[1]["bank"]["ore"] == 5
    game.rolled = False
    game.rng.roll(3, 4)
    act(game, 0, "roll")
    assert game._pending_for("discard", 1) is None  # only 4 in hand
    with pytest.raises(RuleError):
        act(game, 1, "deposit", cards={"ore": 1})  # not while the 7 resolves
    act(game, 0, "move_robber", piece="robber", hex=H.id, take="steal")
    assert game.players[1]["hand"]["ore"] == 3 and game.players[1]["bank"]["ore"] == 5


def test_deposit_checks_cards():
    game = main_phase(make_game())
    with pytest.raises(RuleError):
        act(game, 0, "deposit", cards={"ore": 1})
    with pytest.raises(RuleError):
        act(game, 0, "deposit", cards={})


# --------------------------------------------------------------- old boot


def test_boot_only_goes_to_a_player_with_more_vp():
    game = main_phase(make_game())
    game.boot_holder = 0
    place(game, 0, H.corners[0])
    place(game, 1, H.corners[3])
    assert not game.can_pass_boot(0)
    with pytest.raises(RuleError):
        act(game, 0, "pass_boot")  # tied
    place(game, 1, H.corners[3], kind="city")
    act(game, 0, "pass_boot")
    assert game.boot_holder == 1
    with pytest.raises(RuleError):
        act(game, 0, "pass_boot")


# ------------------------------------------------------------ moving ships


def ship_game():
    """Red settlement on the coast with a line of 3 ships into an all-sea area."""
    board = make_board(default="sea", terrain={H.id: "pasture"})
    game = main_phase(make_game(board))
    game.turn_number = 5
    start = H.corners[0]
    edges, verts = path_edges(start, 3, avoid=H.corners)
    place(game, 0, start, edges=edges, route="ship")
    return game, edges, verts


def test_only_the_open_end_ship_moves():
    game, edges, verts = ship_game()
    assert game.movable_ships(0) == [edges[2]]
    target = next(e for e in TOPO.vertices[verts[2]].edges if e != edges[2] and e not in edges)
    with pytest.raises(RuleError):
        act(game, 0, "move_ship", **{"from": edges[1], "to": target})
    act(game, 0, "move_ship", **{"from": edges[2], "to": target})
    assert target in game.routes and edges[2] not in game.routes
    other = next(e for e in TOPO.vertices[verts[1]].edges if e not in edges)
    with pytest.raises(RuleError):
        act(game, 0, "move_ship", **{"from": target, "to": other})  # once per turn


def test_ships_built_this_turn_or_linking_buildings_stay():
    game, edges, verts = ship_game()
    game.routes[edges[2]]["turn"] = game.turn_number
    assert game.movable_ships(0) == []
    game.routes[edges[2]]["turn"] = 0
    place(game, 0, verts[3])  # the line now joins two of red's buildings
    assert game.movable_ships(0) == []


def test_pirate_pins_ships():
    game, edges, verts = ship_game()
    pirate_hex = next(h for h in TOPO.edges[edges[2]].hexes if not TOPO.hexes[h].frame)
    game.pirate = pirate_hex
    assert edges[2] not in game.movable_ships(0)
