import pytest

from mahjong_duo.rules_core import init_game, build_wall


@pytest.fixture
def seed():
    return 12345


def test_init_game_basic(seed):
    game = init_game(seed)

    assert game.seed == seed
    assert game.started
    assert not game.ended
    assert game.turn == 0
    assert len(game.players) == 2
    assert len(game.wall) == 82  # 108 tiles total - 26 dealt
    assert len(game.players[0].hand) == 13
    assert len(game.players[1].hand) == 13
    assert len(game.players[0].melds) == 0
    assert len(game.players[1].melds) == 0
    assert len(game.players[0].discards) == 0
    assert len(game.players[1].discards) == 0


def test_init_game_first_turn_override(seed):
    game = init_game(seed, first_turn=1)
    assert game.turn == 1


def test_init_game_invalid_first_turn(seed):
    with pytest.raises(ValueError):
        init_game(seed, first_turn=2)

    with pytest.raises(ValueError):
        init_game(seed, first_turn=-1)


def test_init_game_hands_are_sorted(seed):
    game = init_game(seed)
    assert game.players[0].hand == tuple(sorted(game.players[0].hand))
    assert game.players[1].hand == tuple(sorted(game.players[1].hand))


def test_init_game_reproducible(seed):
    game1 = init_game(seed)
    game2 = init_game(seed)

    assert game1.wall == game2.wall
    assert game1.players[0].hand == game2.players[0].hand
    assert game1.players[1].hand == game2.players[1].hand


def test_init_game_different_seeds():
    game1 = init_game(12345)
    game2 = init_game(54321)

    different = (
        game1.wall != game2.wall
        or game1.players[0].hand != game2.players[0].hand
        or game1.players[1].hand != game2.players[1].hand
    )
    assert different


def test_init_game_wall_dealing(seed):
    wall_before = build_wall(seed)
    game = init_game(seed)

    dealt_tiles = list(game.players[0].hand) + list(game.players[1].hand)
    expected_dealt = wall_before[:26]

    assert sorted(dealt_tiles) == sorted(expected_dealt)
    assert game.wall == tuple(wall_before[26:])
