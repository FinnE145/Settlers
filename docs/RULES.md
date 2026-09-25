# Settlers — rules as implemented

This is the working spec the engine enforces. It is the standard base game plus the
Seafarers ship rules and the Fishermen fish rules, with the house rules below.

## Players and winning

- 2 players, red and blue. The starting player is chosen at random.
- The first player to have **14 VP during their own turn** wins (15 while holding the old boot).
- VP: settlement 1, city 2, longest trade route 2, largest army 2, each victory point card
  played 1.

## Board

- An 8×8 rectangle of pointy-top hexes (odd rows offset), surrounded by a sea frame.
- Tiles: 35 sea, 5 each of forest, hills, pasture, fields and mountains, 3 gold fields
  and 1 lake. There are no deserts.
- Placement is fully random. The only constraint is that the lake touches at least
  3 land hexes (any non-sea hex counts as land).
- Number tokens on the 28 producing hexes: 2×2, 3× each of 3, 4, 5, 6, 8, 9, 10, 11 and 2×12.
  The lake produces on 2, 3, 11 and 12.
- 10 harbours on random land/sea edges: five 3:1 and one 2:1 per resource. No two harbours
  share a corner.
- 6 fishing grounds (4, 5, 6, 8, 9, 10). Each sits in a sea or frame hex, pointing at a corner
  whose two edges both face land, and touches that corner plus the two beside it.
- Each sea hex holds at most one harbour or fishing ground.
- The game creator sees the board first and can regenerate it as often as they like.

## Supply and pieces

- Resource cards are unlimited.
- Development deck: 14 knight, 5 victory point, 2 road building, 2 year of plenty, 2 monopoly.
- Roads and ships are unlimited.
- Settlements and cities: while a player has at least 5 settlements **and** at least 4 cities
  on the board, they may build either freely. Otherwise the normal limits apply: a new
  settlement needs fewer than 5 on the board, a new city needs fewer than 4.
  Example: at 5 settlements / 4 cities you may build a city, leaving 4 / 5. Now no more
  cities until you are back to 5 settlements, which turns the limits off again.

Costs: road = wood + brick, ship = wood + sheep, settlement = wood + brick + sheep + wheat,
city = 2 wheat + 3 ore, development card = sheep + wheat + ore.

## Setup

- Snake order (A, B, B, A). Each placement is a settlement plus a road, or a ship if the
  settlement is on the coast. Starting settlements may go anywhere legal.
- When all placements are done, each starting settlement (first and second) gives one card
  from every adjacent producing hex (gold: your choice), plus one fish token for each fishing
  ground or lake it touches. Gold picks are made then, before the first roll.
- The robber and the pirate start off the board.

## Turn

1. Roll the dice (a knight may be played before rolling).
2. Production: every settlement gets 1 card and every city 2 from each adjacent hex showing
   the number, unless the robber is on it. Gold fields give cards of the owner's choice.
   Fish are produced as described below.
3. On a 7: see *Robber*.
4. Actions in any order: trade, build, buy or play a development card, move one ship,
   spend fish, pass the old boot.
5. End the turn.

## Building

- Distance rule: no settlement may be adjacent to another settlement or city.
- New settlements must touch one of your roads or ships.
- Roads go on edges touching land. They must connect to your road or building, and can't
  pass through an opponent's building.
- Ships go on edges touching sea (including the frame). They must connect to your ship or
  building (not to a road directly), and can't pass through an opponent's building.
- A coastal edge holds a road or a ship, never both.
- **Moving a ship:** once per turn you may move one ship that you didn't build this turn,
  that has an open end (no ship or building of yours there), and that isn't part of a line
  of ships joining two of your buildings. It goes to any legal new ship position.
- Road building card: any 2 of roads and ships.

## Longest trade route and largest army

- Longest trade route: the longest continuous chain of your roads and ships, at least 5.
  Roads and ships only chain through one of your own buildings; an opponent's building
  breaks a chain. The title moves only when someone strictly exceeds the holder.
- Largest army: at least 3 knights played, strictly more than the opponent.

## Robber (7 or knight)

- On a 7, any player with more than 7 cards **in hand** discards half, rounded down.
  Banked cards and fish don't count.
- The mover then moves either the robber or the pirate to a different hex, and chooses one of:
  - steal a random card from the hand of an opponent next to it (robber: a building on
    that hex; pirate: a ship on one of its edges), or
  - take any one resource card of their choice from the supply.
- The robber goes on a land hex. That hex produces nothing, including the lake's fish.
- The pirate goes on a sea hex (frame included). While it's there:
  - no ship may be built on, moved onto or moved off any edge of that hex;
  - a fishing ground in that hex gives each player half the tokens they would normally
    draw from it, rounded down (settlement 1 → 0, city 2 → 1, city + settlement 3 → 1,
    two cities 4 → 2).
- Both start off the board and enter on the first 7 or knight.

## Development cards

- You can't play a card on the turn you got it, and at most one is played per turn, at any
  point in your turn, including before rolling.
- Victory point cards are the exception: they stay hidden and count only once played, and
  you can play any number of them at any point in your own turn, including the turn you
  got them. (Keeping them hidden keeps your public VP low for the old boot.)
- Knight: move the robber or pirate as on a 7 (no discards). Road building: 2 free roads
  and/or ships. Year of plenty: take any 2 resource cards. Monopoly: the opponent gives you
  every card of the named resource from their hand (banked cards are safe).
- Free roads/ships must be placed before doing anything else; you may give up the rest if
  you can't or don't want to place them.

## Trading

- After the active player rolls, either player can propose a trade; the other accepts or
  declines, and a new proposal replaces the open one. Resources and fish tokens can be
  traded (fish by token value). Both sides must include something.
- Bank rates: 4:1 by default, 3:1 at a generic harbour.
- 2:1 harbours work both ways: at a wood harbour, 2 wood → 1 of anything, or
  2 of the same other resource → 1 wood.
- With cities on two or more 2:1 harbours, those harbours' resources trade 1:1 with each
  other (e.g. cities on the wood and brick harbours: wood ↔ brick 1:1).

## Fish

- 29 tokens (eleven 1-fish, ten 2-fish, eight 3-fish) and the old boot, drawn face down.
- When a fishing ground's number is rolled, each adjacent settlement draws 1 token and each
  city 2 (halved with the pirate, see above). The lake does the same on 2, 3, 11 and 12,
  unless the robber is on it.
- If the bag can't cover everyone's draws for that roll, nobody draws. Spent tokens are
  reshuffled into the bag when it runs out.
- There is no limit on tokens held. Fish aren't resource cards: they can't be stolen,
  aren't taken by monopoly, and don't count for the 7 rule.
- The opponent sees how many tokens you have, not their values.
- **Spending (your own turn, after rolling):** hand in any tokens and buy any combination of
  the items below whose total cost fits. There is no change; excess fish are lost, but every
  token handed in must be needed to cover the cost.
  - 1 fish: take everything out of your card bank.
  - 2 fish: remove the robber or the pirate from the board.
  - 3 fish: steal a random resource card from the opponent's hand.
  - 4 fish: take one resource card of your choice.
  - 5 fish: build a road or ship for free.
  - 7 fish: draw a development card.

## Old boot

- Whoever draws it reveals it and keeps it. It gives no fish.
- While holding it you need 1 more VP to win.
- On your turn, after rolling, you may pass it to a player with strictly more VP than you.
  Only public VP count (hidden victory point cards are ignored).

## Card bank

- At any time, on either player's turn, you may move resource cards from your hand into your
  own face-down bank. The opponent sees only how many cards are in it.
- Banked cards can't be used, stolen or taken by monopoly, and don't count for the 7 rule.
- Effects like a 7, monopoly or a steal resolve immediately. Cards must already be banked to
  be protected.
- Emptying the bank costs 1 fish (as part of a fish purchase on your own turn). All cards
  return to your hand; you may immediately bank some again.
