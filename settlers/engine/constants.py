"""Game constants: component counts, costs and names."""

RESOURCES = ("wood", "brick", "sheep", "wheat", "ore")

# Terrain that produces a fixed resource.
TERRAIN_RESOURCE = {
    "forest": "wood",
    "hills": "brick",
    "pasture": "sheep",
    "fields": "wheat",
    "mountains": "ore",
}
SEA = "sea"
GOLD = "gold"
DESERT = "desert"
LAKE = "lake"

BOARD_COLS = 7
BOARD_ROWS = 7

# Seafarers + base game tile set, with the lake replacing one of the three deserts.
TILE_COUNTS = {
    SEA: 19,
    "forest": 5,
    "hills": 5,
    "pasture": 5,
    "fields": 5,
    "mountains": 5,
    GOLD: 2,
    DESERT: 2,
    LAKE: 1,
}

# One number token per producing land hex (5 of each resource + 2 gold = 27).
NUMBER_TOKENS = (
    [2] * 2 + [3] * 3 + [4] * 3 + [5] * 3 + [6] * 3
    + [8] * 3 + [9] * 3 + [10] * 3 + [11] * 3 + [12] * 1
)
LAKE_NUMBERS = (2, 3, 11, 12)
LAKE_MIN_LAND_NEIGHBOURS = 3

# 5 generic 3:1 harbours and one 2:1 harbour per resource.
HARBOURS = ["3:1"] * 5 + list(RESOURCES)

FISHERY_NUMBERS = (4, 5, 6, 8, 9, 10)

# Fish tokens: 11 x one fish, 10 x two fish, 8 x three fish, plus the old boot (0).
FISH_TOKENS = [1] * 11 + [2] * 10 + [3] * 8
BOOT = 0

DEV_CARDS = {
    "knight": 14,
    "victory_point": 5,
    "road_building": 2,
    "year_of_plenty": 2,
    "monopoly": 2,
}

COSTS = {
    "road": {"wood": 1, "brick": 1},
    "ship": {"wood": 1, "sheep": 1},
    "settlement": {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1},
    "city": {"wheat": 2, "ore": 3},
    "dev_card": {"sheep": 1, "wheat": 1, "ore": 1},
}

# Normal piece limits, lifted once a player has all of them on the board at once.
SETTLEMENT_LIMIT = 5
CITY_LIMIT = 4

VP_TO_WIN = 14
LONGEST_ROUTE_MIN = 5
LARGEST_ARMY_MIN = 3

PLAYER_COLOURS = ("red", "blue")
