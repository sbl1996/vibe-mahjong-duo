from mahjong_duo.rules_core import (
    tile_to_str,
    build_wall,
    sort_hand,
    counts_from_tiles,
    TILE_TYPES,
    COPIES_PER_TILE,
    TOTAL_TILES,
    Meld,
    PlayerState,
    GameState,
)

TEST_SEED = 12345


def test_tile_to_str():
    assert tile_to_str(0) == "1万"
    assert tile_to_str(8) == "9万"
    assert tile_to_str(9) == "1条"
    assert tile_to_str(17) == "9条"
    assert tile_to_str(18) == "1筒"
    assert tile_to_str(26) == "9筒"


def test_constants():
    assert TILE_TYPES == 27
    assert COPIES_PER_TILE == 4
    assert TOTAL_TILES == 108


def test_build_wall_length_and_counts():
    wall = build_wall(TEST_SEED)
    assert len(wall) == 108

    counts = [0] * TILE_TYPES
    for tile in wall:
        counts[tile] += 1

    assert all(count == 4 for count in counts)


def test_build_wall_reproducibility():
    wall = build_wall(TEST_SEED)
    wall_same_seed = build_wall(TEST_SEED)
    wall_other_seed = build_wall(TEST_SEED + 1)

    assert wall == wall_same_seed
    assert wall != wall_other_seed


def test_sort_hand():
    hand = [5, 2, 8, 1, 3]
    assert sort_hand(hand) == [1, 2, 3, 5, 8]


def test_counts_from_tiles():
    tiles = (0, 0, 1, 1, 1, 5, 5, 5, 5)
    counts = counts_from_tiles(tiles)

    expected = [0] * TILE_TYPES
    expected[0] = 2
    expected[1] = 3
    expected[5] = 4

    assert counts == tuple(expected)


def test_meld_creation():
    pong = Meld("pong", (1, 1, 1))
    assert pong.kind == "pong"
    assert pong.tiles == (1, 1, 1)

    kong = Meld("kong_exposed", (2, 2, 2, 2))
    assert kong.kind == "kong_exposed"
    assert kong.tiles == (2, 2, 2, 2)


def test_player_state_creation():
    hand = (1, 2, 3, 4, 5)
    melds = (Meld("pong", (6, 6, 6)),)
    discards = (7, 8, 9)

    player = PlayerState(hand, melds, discards)
    assert player.hand == hand
    assert player.melds == melds
    assert player.discards == discards


def test_game_state_creation_defaults():
    wall = tuple(range(20))
    players = (
        PlayerState((1, 2, 3), (), ()),
        PlayerState((4, 5, 6), (), ()),
    )

    game = GameState(seed=12345, wall=wall, players=players, turn=0)

    assert game.seed == 12345
    assert game.wall == wall
    assert game.players == players
    assert game.turn == 0
    assert not game.started
    assert not game.ended
