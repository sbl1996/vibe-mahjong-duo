import pytest

from mahjong_duo.rules_core import (
    init_game,
    PlayerState,
    Meld,
    legal_choices,
    draw,
    discard,
    can_hu_four_plus_one,
    replace,
)

SEED = 12345


@pytest.fixture
def game():
    return init_game(SEED)


def test_draw_choice_normal(game):
    choices = legal_choices(game, 0)
    assert len(choices) == 1
    assert choices[0]["type"] == "draw"


def test_draw_choice_after_discard(game):
    game_after_draw, tile = draw(game, 0)
    game_after_discard = discard(game_after_draw, 0, tile)

    choices = legal_choices(game_after_discard, 1)
    assert len(choices) == 1 and choices[0]["type"] == "pass"

    game_after_discard = replace(game_after_discard, last_discard=None)

    choices = legal_choices(game_after_discard, 1)
    assert len(choices) == 1 and choices[0]["type"] == "draw"


def test_self_draw_choices(game):
    game_after_draw, _ = draw(game, 0)
    choices = legal_choices(game_after_draw, 0)

    discard_choices = [c for c in choices if c["type"] == "discard"]
    assert discard_choices
    discard_tiles = [c["tile"] for c in discard_choices]
    assert len(discard_tiles) == len(set(discard_tiles))
    assert all(tile in game_after_draw.players[0].hand for tile in discard_tiles)


def test_self_hu_choice(game):
    winning_hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    prepared_game = replace(game,
        players=(
            PlayerState(winning_hand, (), ()),
            game.players[1],
        )
    )

    choices = legal_choices(prepared_game, 0)
    hu_choice = next(c for c in choices if c["type"] == "hu")
    assert hu_choice["style"] == "self"


def test_concealed_kong_choice(game):
    hand = tuple([0] * 4 + [1, 2, 3, 4, 5, 6, 7, 8, 9])
    prepared_game = replace(game,
        players=(
            PlayerState(hand, (), ()),
            game.players[1],
        )
    )

    game_after_draw, _ = draw(prepared_game, 0)
    choices = legal_choices(game_after_draw, 0)

    assert any(c["type"] == "kong" and c["style"] == "concealed" for c in choices)


def test_added_kong_choice(game):
    tile = 1
    melds = (Meld("pong", (tile, tile, tile)),)
    idx = game.wall.index(tile)
    wall = game.wall[:idx] + game.wall[idx+1:]
    hand = (tile, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
    prepared_game = replace(game,
        wall=wall,
        players=(
            PlayerState(hand, melds, ()),
            game.players[1],
        )
    )

    choices = legal_choices(prepared_game, 0)
    assert any([c["type"] == "kong" and c["style"] == "added" for c in choices])


def test_response_to_discard(game):
    game_after_draw, tile = draw(game, 0)
    game_after_discard = discard(game_after_draw, 0, tile)

    choices = legal_choices(game_after_discard, 1)

    assert any(c["type"] == "pass" for c in choices)
    pass_count = sum(1 for c in choices if c["type"] == "pass")
    assert pass_count >= 1


def test_peng_choice(game):
    game_after_draw, tile = draw(game, 0)
    game_after_discard = discard(game_after_draw, 0, tile)

    p1_hand = list(game_after_discard.players[1].hand)
    p1_hand[0] = tile
    p1_hand[1] = tile
    prepared_game = replace(game_after_discard,
        players=(
            game_after_discard.players[0],
            PlayerState(
                tuple(p1_hand),
                game_after_discard.players[1].melds,
                game_after_discard.players[1].discards,
            ),
        )
    )

    choices = legal_choices(prepared_game, 1)

    assert any(c["type"] == "peng" for c in choices)
    peng_choice = next(c for c in choices if c["type"] == "peng")
    assert peng_choice["tile"] == tile


def test_exposed_kong_choice(game):
    game_after_draw, tile = draw(game, 0)
    game_after_discard = discard(game_after_draw, 0, tile)

    p1_hand = list(game_after_discard.players[1].hand)
    p1_hand[0] = tile
    p1_hand[1] = tile
    p1_hand[2] = tile
    prepared_game = replace(game_after_discard,
        players=(
            game_after_discard.players[0],
            PlayerState(
                tuple(p1_hand),
                game_after_discard.players[1].melds,
                game_after_discard.players[1].discards,
            ),
        )
    )

    choices = legal_choices(prepared_game, 1)

    assert any(c["type"] == "kong" and c["style"] == "exposed" for c in choices)


def test_ron_choice(game):
    wall = (10,) + game.wall[1:]
    game = replace(game, wall=wall)
    game_after_draw, tile = draw(game, 0)
    game_after_discard = discard(game_after_draw, 0, tile)

    robber_hand = (6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10)
    robber_hand_with_tile = tuple(sorted(robber_hand + (tile,)))

    prepared_game = replace(game_after_discard,
        players=(
            game_after_discard.players[0],
            PlayerState(
                robber_hand,
                game_after_discard.players[1].melds,
                game_after_discard.players[1].discards,
            ),
        )
    )

    assert can_hu_four_plus_one(robber_hand_with_tile, prepared_game.players[1].melds)

    choices = legal_choices(prepared_game, 1)

    assert any(c["type"] == "hu" for c in choices)
    hu_choice = next(c for c in choices if c["type"] == "hu")
    assert hu_choice["style"] == "ron"
    assert hu_choice["tile"] == tile


def test_rob_kong_choices(game):
    tile = 1
    pending_game = replace(game,pending_rob_kong=(0, tile), turn=1)

    choices = legal_choices(pending_game, 1)
    assert any(c["type"] == "pass" for c in choices)


def test_rob_kong_hu_choice(game):
    tile = 10
    pending_game = replace(game, pending_rob_kong=(0, tile), turn=1)

    robber_hand = (6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10)
    robber_hand_with_tile = tuple(sorted(robber_hand + (tile,)))

    prepared_game = replace(pending_game,
        players=(
            pending_game.players[0],
            PlayerState(
                robber_hand,
                pending_game.players[1].melds,
                pending_game.players[1].discards,
            ),
        )
    )

    assert can_hu_four_plus_one(robber_hand_with_tile, prepared_game.players[1].melds)

    choices = legal_choices(prepared_game, 1)

    hu_choice = next(c for c in choices if c["type"] == "hu")
    assert hu_choice["style"] == "rob"
    assert hu_choice["tile"] == tile


def test_no_choices_when_not_turn(game):
    game_after_draw, _ = draw(game, 0)
    choices = legal_choices(game_after_draw, 1)

    assert len(choices) == 0
