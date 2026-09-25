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
        act(game, 0, "offer_trade", give={}, get={})  # nothing at all
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
    assert game.largest_army == 0 and game.public_vp(0) == 1
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


def test_victory_point_cards_count_once_played():
    game = main_phase(make_game())
    game.turn_number = 4
    game.players[0]["dev"] = [{"card": "victory_point", "turn": 4}, {"card": "victory_point", "turn": 4},
                              {"card": "knight", "turn": 1}]
    assert game.public_vp(0) == 0  # hidden cards don't count
    act(game, 0, "play_dev", card="knight")
    act(game, 0, "move_robber", piece="robber", hex=H.id, take="ore")
    # Same turn they were drawn, and not limited by the one-card-per-turn rule.
    act(game, 0, "play_dev", card="victory_point")
    act(game, 0, "play_dev", card="victory_point")
    assert game.public_vp(0) == 2
    assert game.view_for(1)["players"][0]["vp"] == 2
    with pytest.raises(RuleError):
        act(game, 0, "play_dev", card="victory_point")  # none left
    game.players[1]["dev"] = [{"card": "victory_point", "turn": 1}]
    with pytest.raises(RuleError):
        act(game, 1, "play_dev", card="victory_point")  # only on your own turn (it's red's)


def test_playing_a_victory_point_card_can_win():
    game = main_phase(make_game())
    game.vp_needed = lambda p: 1
    game.players[0]["dev"] = [{"card": "victory_point", "turn": 1}]
    act(game, 0, "play_dev", card="victory_point")
    assert game.phase == "finished" and game.winner == 0


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


# ----------------------------------------------------------- new titles


def many_harbours_board():
    spots = [hex_at(c, r) for r in (0, 2, 4, 6) for c in (0, 2, 4, 6)]
    harbours = [{"edge": h.edges[0], "kind": "3:1"} for h in spots]
    return make_board(harbours=harbours), [TOPO.edges[h.edges[0]].vertices[0] for h in spots]


def test_harbourmaster_needs_three_and_moves_on_more():
    board, spots = many_harbours_board()
    game = main_phase(make_game(board))
    for v in spots[:2]:
        place(game, 0, v)
    game._update_building_titles()
    assert game.harbourmaster is None
    place(game, 0, spots[2], kind="city")  # a city counts as one harbour, like a settlement
    game._update_building_titles()
    assert game.harbour_count(0) == 3 and game.harbourmaster == 0
    assert game.public_vp(0) == 2 + 2 + 1  # two settlements, a city, the title
    for v in spots[3:6]:
        place(game, 1, v)
    game._update_building_titles()
    assert game.harbourmaster == 0  # a tie doesn't take it
    place(game, 1, spots[6])
    game._update_building_titles()
    assert game.harbourmaster == 1


def test_master_fisherman_counts_buildings_on_fish():
    sea, lake = hex_at(2, 2), hex_at(5, 5)
    fishery = {"hex": sea.id, "corner": 0, "number": 4,
               "vertices": [sea.corners[5], sea.corners[0], sea.corners[1]]}
    game = main_phase(make_game(make_board(terrain={sea.id: "sea", lake.id: "lake"}, fisheries=[fishery])))
    place(game, 0, sea.corners[5])
    place(game, 0, sea.corners[1], kind="city")
    game._update_building_titles()
    assert game.fish_building_count(0) == 2 and game.master_fisherman is None
    place(game, 0, lake.corners[3])
    place(game, 0, hex_at(0, 7).corners[3])  # not on fish
    game._update_building_titles()
    assert game.fish_building_count(0) == 3 and game.master_fisherman == 0
    for i in (0, 1, 2):
        place(game, 1, lake.corners[i] if i != 1 else lake.corners[5])
    place(game, 1, sea.corners[0])
    game._update_building_titles()
    assert game.fish_building_count(1) == 4 and game.master_fisherman == 1


def test_building_a_settlement_updates_the_titles():
    board, spots = many_harbours_board()
    game = main_phase(make_game(board))
    for v in spots[:2]:
        place(game, 0, v)
    target = spots[2]
    place(game, 0, edges=[TOPO.vertices[target].edges[0]])
    give(game, 0, wood=1, brick=1, sheep=1, wheat=1)
    act(game, 0, "build_settlement", vertex=target)
    assert game.harbourmaster == 0
    view = game.view_for(1)["players"][0]
    assert view["harbourmaster"] and view["harbours"] == 3


def test_titles_are_worth_one_vp_each():
    game = main_phase(make_game())
    game.longest_route = game.largest_army = game.harbourmaster = game.master_fisherman = 0
    assert game.public_vp(0) == 4


def test_saves_from_before_the_new_titles_still_load():
    import json

    from settlers.engine.game import Game

    game = main_phase(make_game())
    data = json.loads(json.dumps(game.to_dict()))
    del data["harbourmaster"], data["master_fisherman"]
    again = Game.from_dict(data)
    assert again.harbourmaster is None and again.master_fisherman is None


def test_old_saves_get_the_new_titles_on_load():
    import json

    from settlers.engine.game import Game

    board, spots = many_harbours_board()
    game = main_phase(make_game(board))
    for v in spots[:3]:
        place(game, 1, v)
    data = json.loads(json.dumps(game.to_dict()))
    del data["harbourmaster"], data["master_fisherman"], data["names"]
    again = Game.from_dict(data)
    assert again.harbourmaster == 1 and again.names == ["Red", "Blue"]


# ------------------------------------------------- using someone's harbour


def harbour_rental_game():
    board, spots = harbour_board()  # spots: wood 2:1, brick 2:1, 3:1, ore 2:1
    game = main_phase(make_game(board), p=1)  # blue's turn: red trades on the other turn
    place(game, 1, spots[0])  # blue has the wood 2:1 harbour
    give(game, 0, wood=4, sheep=1)
    return game


def test_put_cards_through_the_other_players_harbour():
    game = harbour_rental_game()
    offer = {"give": {"sheep": 1}, "get": {},
             "harbour": {"user": 0, "conversions": [{"give": "wood", "get": "ore"}, {"give": "wood", "get": "ore"}]}}
    act(game, 0, "offer_trade", **offer)
    assert [c["rate"] for c in game.trade["harbour"]["conversions"]] == [2, 2]
    act(game, 1, "accept_trade")
    assert game.players[0]["hand"] == {"wood": 0, "brick": 0, "sheep": 0, "wheat": 0, "ore": 2}
    assert game.players[1]["hand"]["sheep"] == 1
    assert "harbours" in game.log[-1]["text"]


def test_harbour_use_needs_the_cards():
    game = harbour_rental_game()
    too_much = {"user": 0, "conversions": [{"give": "wood", "get": "ore"}] * 3}  # needs 6 wood
    with pytest.raises(RuleError):
        act(game, 0, "offer_trade", give={"sheep": 1}, get={}, harbour=too_much)
    with pytest.raises(RuleError):
        act(game, 0, "offer_trade", give={"sheep": 1}, get={},
            harbour={"user": 0, "conversions": [{"give": "wood", "get": "wood"}]})
    # The fee counts against the same hand as the harbour cards.
    with pytest.raises(RuleError):
        act(game, 0, "offer_trade", give={"wood": 1}, get={},
            harbour={"user": 0, "conversions": [{"give": "wood", "get": "ore"}] * 2})


def test_owner_can_counter_on_the_fee():
    game = harbour_rental_game()
    use = {"user": 0, "conversions": [{"give": "wood", "get": "ore"}]}
    act(game, 0, "offer_trade", give={"sheep": 1}, get={}, harbour=use)
    # Blue counters: same harbour use by red, but wants 2 wood as the fee instead.
    act(game, 1, "offer_trade", give={}, get={"wood": 2}, harbour=use)
    assert game.trade["from"] == 1 and game.trade["harbour"]["user"] == 0
    act(game, 0, "accept_trade")
    assert game.players[0]["hand"]["wood"] == 0 and game.players[0]["hand"]["ore"] == 1
    assert game.players[1]["hand"]["wood"] == 2


def test_accept_checks_the_users_harbour_cards():
    game = harbour_rental_game()
    use = {"user": 0, "conversions": [{"give": "wood", "get": "ore"}]}
    act(game, 1, "offer_trade", give={}, get={"sheep": 1}, harbour=use)
    game.players[0]["hand"]["wood"] = 1  # red spent wood meanwhile
    with pytest.raises(RuleError):
        act(game, 0, "accept_trade")


def test_gifts_and_free_harbour_use():
    game = harbour_rental_game()
    act(game, 0, "offer_trade", give={"sheep": 1}, get={})
    assert game.log[-1]["text"] == "{0} offers {1} 1 sheep as a gift."
    act(game, 1, "accept_trade")
    assert game.players[1]["hand"]["sheep"] == 1
    act(game, 0, "offer_trade", give={}, get={"sheep": 1})  # asking for something for nothing
    act(game, 1, "accept_trade")
    assert game.players[0]["hand"]["sheep"] == 1
    use = {"user": 0, "conversions": [{"give": "wood", "get": "ore"}]}
    act(game, 0, "offer_trade", give={}, get={}, harbour=use)  # free use of their harbour
    act(game, 1, "accept_trade")
    assert game.players[0]["hand"]["ore"] == 1
