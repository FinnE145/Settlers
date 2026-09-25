"""Random-play simulation: bots play whole games through ``Game.act`` while every
invariant we can think of is checked after each action.

    python -m tests.simulate [games] [first seed]
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter

from settlers.engine.board import generate_board
from settlers.engine.constants import BOOT, DEV_CARDS, FISH_PRICES, FISH_TOKENS, RESOURCES
from settlers.engine.game import Game, RuleError

MAX_ACTIONS = 6000


class Stuck(Exception):
    pass


def random_cards(rng, n, available=None):
    cards = {r: 0 for r in RESOURCES}
    pool = [r for r in RESOURCES for _ in range(available[r])] if available else None
    for _ in range(n):
        if pool is not None:
            if not pool:
                break
            r = pool.pop(rng.randrange(len(pool)))
        else:
            r = rng.choice(RESOURCES)
        cards[r] += 1
    return cards


def covering_tokens(tokens, cost):
    """Largest tokens first until the cost is covered: never includes a spare token."""
    chosen = []
    for t in sorted(tokens, reverse=True):
        if sum(chosen) >= cost:
            break
        chosen.append(t)
    return chosen if sum(chosen) >= cost else None


def candidates(game: Game, p: int, rng: random.Random) -> list[tuple[float, dict]]:
    """Weighted actions p might take now. Not all have to be legal."""
    out: list[tuple[float, dict]] = []
    add = lambda w, a: out.append((w, a))  # noqa: E731
    me = game.players[p]
    hand = me["hand"]
    n_hand = sum(hand.values())
    legal = game.legal_for(p)

    pend = {i["type"]: i for i in game.pending if i["player"] == p}
    if "gold" in pend:
        add(10, {"type": "choose_gold", "cards": random_cards(rng, pend["gold"]["count"])})
    if "discard" in pend:
        add(10, {"type": "discard", "cards": random_cards(rng, pend["discard"]["count"], hand)})

    if game.phase == "setup":
        for v in legal.get("settlement", []):
            add(1, {"type": "build_settlement", "vertex": v})
        for kind in ("road", "ship"):
            for e in legal.get(kind, []):
                add(1, {"type": f"build_{kind}", "edge": e})
        return out

    if "robber" in pend:
        for piece in ("robber", "pirate"):
            hexes = legal.get(piece, [])
            for h in rng.sample(hexes, min(3, len(hexes))):
                victim = game.robber_victim(piece, h, p)
                take = "steal" if victim is not None and sum(game.players[victim]["hand"].values()) \
                    and rng.random() < 0.7 else rng.choice(RESOURCES)
                add(5, {"type": "move_robber", "piece": piece, "hex": h, "take": take})
    if "free_routes" in pend:
        for kind in ("road", "ship"):
            for e in legal.get(kind, [])[:4]:
                add(3, {"type": f"build_{kind}", "edge": e})
        add(0.3, {"type": "skip_free_routes"})

    if not game.pending and n_hand:
        add(0.2, {"type": "deposit", "cards": random_cards(rng, rng.randint(1, n_hand), hand)})

    window = game.rolled and not game.pending
    if game.trade and game.trade["from"] != p and window:
        add(2, {"type": "accept_trade"})
        add(1, {"type": "decline_trade"})
    if game.trade and game.trade["from"] == p:
        add(0.3, {"type": "cancel_trade"})
    if window and n_hand and rng.random() < 0.3:
        offer = {"type": "offer_trade", "give": random_cards(rng, rng.randint(1, 2), hand),
                 "get": random_cards(rng, rng.randint(1, 2))}
        if me["fish"] and rng.random() < 0.3:
            offer["give_fish"] = [rng.choice(me["fish"])]
        if rng.random() < 0.2:
            offer["get_fish"] = [rng.randint(1, 3)]
        add(0.5, offer)

    if p != game.current:
        return out

    if not game.rolled and not game.pending:
        add(5, {"type": "roll"})
        if "knight" in game.playable_dev(p):
            add(1, {"type": "play_dev", "card": "knight"})
    if not window:
        return out

    costs = game.view_for(p)["costs"]
    affordable = lambda what: all(hand[r] >= n for r, n in costs[what].items())  # noqa: E731
    # Keep networks realistic: stop adding roads/ships past a generous size.
    route_weight = 1.5 if sum(1 for r in game.routes.values() if r["owner"] == p) < 40 else 0
    for kind, key, weight in (("settlement", "vertex", 10), ("city", "vertex", 10),
                              ("road", "edge", route_weight), ("ship", "edge", route_weight)):
        if not weight:
            continue
        if affordable(kind):
            spots = legal.get(kind, [])
            for x in rng.sample(spots, min(4, len(spots))):
                add(weight, {"type": f"build_{kind}", key: x})
    if affordable("dev_card"):
        add(2, {"type": "buy_dev"})
    for card in game.playable_dev(p):
        if card == "year_of_plenty":
            add(2, {"type": "play_dev", "card": card, "cards": random_cards(rng, 2)})
        elif card == "monopoly":
            add(2, {"type": "play_dev", "card": card, "resource": rng.choice(RESOURCES)})
        else:
            add(2, {"type": "play_dev", "card": card})
    rates = game.trade_rates(p)
    for give in RESOURCES:
        for get in RESOURCES:
            if give != get and hand[give] >= rates[give][get]:
                add(1.5, {"type": "maritime", "give": give, "get": get})
    if me["fish"]:
        kind = rng.choice(list(FISH_PRICES))
        item = {"kind": kind}
        if kind == "resource":
            item["resource"] = rng.choice(RESOURCES)
        tokens = covering_tokens(me["fish"], FISH_PRICES[kind])
        if tokens:
            add(2, {"type": "fish", "tokens": tokens, "items": [item]})
    if game.can_pass_boot(p):
        add(3, {"type": "pass_boot"})
    for e in legal.get("move_ship", [])[:2]:
        targets = legal["ship_targets"][e]
        if targets:
            add(0.5, {"type": "move_ship", "from": e, "to": rng.choice(targets)})
    add(1, {"type": "end_turn"})
    return out


def check_invariants(game: Game) -> None:
    for pl in game.players:
        assert all(n >= 0 for n in pl["hand"].values()), pl["hand"]
        assert all(n >= 0 for n in pl["bank"].values()), pl["bank"]
        assert all(t in (1, 2, 3) for t in pl["fish"])
    held = sum(len(pl["fish"]) for pl in game.players)
    in_play = len(game.fish_bag) + len(game.fish_spent) + held
    expected = len(FISH_TOKENS) + (0 if game.boot_holder is not None else 1)
    assert in_play == expected, (in_play, expected)
    assert Counter(t for t in game.fish_bag + game.fish_spent if t != BOOT) + Counter(
        t for pl in game.players for t in pl["fish"]) == Counter(FISH_TOKENS)
    assert len(game.dev_deck) + sum(len(pl["dev"]) for pl in game.players) <= sum(DEV_CARDS.values())
    for v in game.buildings:
        assert not any(n in game.buildings for n in game.topo.vertices[v].neighbours), "distance rule"
    for e, r in game.routes.items():
        if r["kind"] == "road":
            assert game._edge_touches_land(e)
        else:
            assert game._edge_touches_sea(e)
    for p in range(2):
        s, c = game._piece_counts(p)
        assert s + c >= 2 or game.phase == "setup"
    if game.phase == "finished":
        assert game.public_vp(game.winner) >= game.vp_needed(game.winner)


def acting_players(game: Game) -> list[int]:
    if game.phase == "setup":
        if game.pending:
            return sorted({i["player"] for i in game.pending})
        return [game.setup_order[game.setup_step]]
    blocking = [i["player"] for i in game.pending if i["type"] in ("discard", "gold")]
    if blocking:
        return sorted(set(blocking))
    if game.pending:
        return [game.pending[0]["player"]]
    return [game.current, 1 - game.current] if game.trade else [game.current]


def play_random_game(seed: int, max_actions: int = MAX_ACTIONS) -> dict:
    rng = random.Random(seed)
    game = Game(generate_board(random.Random(seed)), first_player=seed % 2, rng=random.Random(seed + 1))
    actions = Counter()
    for n in range(max_actions):
        if game.phase == "finished":
            break
        done = False
        for p in rng.sample(acting_players(game), len(acting_players(game))):
            cands = candidates(game, p, rng)
            while cands and not done:
                weights = [w for w, _ in cands]
                i = rng.choices(range(len(cands)), weights=weights)[0]
                _, action = cands.pop(i)
                try:
                    game.act(p, action)
                except RuleError:
                    continue
                actions[action["type"]] += 1
                done = True
            if done:
                break
        if not done:
            raise Stuck(f"seed {seed}: nobody could act at action {n} (phase {game.phase}, "
                        f"pending {game.pending}, current {game.current}, rolled {game.rolled})")
        check_invariants(game)
        if n % 50 == 0:
            for p in (0, 1, None):
                json.dumps(game.view_for(p))
            again = Game.from_dict(json.loads(json.dumps(game.to_dict())))
            assert again.to_dict() == json.loads(json.dumps(game.to_dict()))
            assert again.view_for(0) == game.view_for(0)
    return {
        "seed": seed,
        "finished": game.phase == "finished",
        "winner": game.winner,
        "turns": game.turn_number,
        "actions": sum(actions.values()),
        "counts": actions,
        "vp": [game.public_vp(0), game.public_vp(1)],
    }


def main(argv: list[str]) -> None:
    games = int(argv[0]) if argv else 200
    first = int(argv[1]) if len(argv) > 1 else 0
    totals = Counter()
    finished = 0
    turns = []
    for seed in range(first, first + games):
        start = time.time()
        result = play_random_game(seed)
        totals.update(result["counts"])
        finished += result["finished"]
        turns.append(result["turns"])
        print(f"seed {seed}: {time.time() - start:.1f}s, {result['turns']} turns, "
              f"{result['actions']} actions, finished={result['finished']}, vp={result['vp']}", flush=True)
    print(f"{games} games, {finished} finished, turns: min {min(turns)} "
          f"avg {sum(turns) / len(turns):.0f} max {max(turns)}")
    print("actions taken:", dict(sorted(totals.items())))


if __name__ == "__main__":
    main(sys.argv[1:])
