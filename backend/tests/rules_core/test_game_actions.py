import pytest

from mahjong_duo.rules_core import (
    init_game,
    draw,
    discard,
    claim_peng,
    claim_kong_exposed,
    kong_concealed,
    kong_added,
    Meld,
    PlayerState,
    replace,
)


@pytest.fixture
def game():
    return init_game(12345)


def test_draw_basic(game):
    initial_wall_length = len(game.wall)
    initial_hand_length = len(game.players[0].hand)

    new_game, tile = draw(game, 0)

    assert tile is not None
    assert len(new_game.wall) == initial_wall_length - 1
    assert len(new_game.players[0].hand) == initial_hand_length + 1
    assert new_game.turn == game.turn
    assert new_game.step_no == game.step_no + 1


def test_draw_empty_wall(game):
    empty_wall_game = replace(game,wall=())
    new_game, tile = draw(empty_wall_game, 0)

    assert tile is None
    assert new_game == empty_wall_game


def test_discard_basic(game):
    game_after_draw, tile = draw(game, 0)
    initial_hand_length = len(game_after_draw.players[0].hand)

    new_game = discard(game_after_draw, 0, tile)

    assert len(new_game.players[0].hand) == initial_hand_length - 1
    assert len(new_game.players[0].discards) == 1
    assert new_game.players[0].discards[0] == tile
    assert new_game.turn == 1
    assert new_game.last_discard == (0, tile)
    assert new_game.step_no == game_after_draw.step_no + 1


def test_discard_illegal(game):
    with pytest.raises(ValueError):
        discard(game, 0, 99)


def test_claim_peng_basic(game):
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

    new_game = claim_peng(prepared_game, 1, 0, tile)

    assert len(new_game.players[1].hand) == len(prepared_game.players[1].hand) - 2
    assert len(new_game.players[1].melds) == 1
    assert new_game.players[1].melds[0].kind == "pong"
    assert new_game.players[1].melds[0].tiles == (tile, tile, tile)
    assert new_game.turn == 1


def test_claim_peng_illegal(game):
    game_after_draw, tile = draw(game, 0)
    game_after_discard = discard(game_after_draw, 0, tile)

    with pytest.raises(ValueError):
        claim_peng(game_after_discard, 1, 0, tile)


def test_claim_kong_exposed_basic(game):
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

    new_game = claim_kong_exposed(prepared_game, 1, 0, tile)

    assert len(new_game.players[1].hand) == len(prepared_game.players[1].hand) - 3
    assert len(new_game.players[1].melds) == 1
    assert new_game.players[1].melds[0].kind == "kong_exposed"
    assert new_game.players[1].melds[0].tiles == (tile, tile, tile, tile)
    assert new_game.pending_kong_draw == 1


def test_kong_concealed_basic(game):
    p0_hand = list(game.players[0].hand)
    tile = p0_hand[0]
    p0_hand = [tile] * 4 + p0_hand[4:]
    prepared_game = replace(game,
        players=(
            PlayerState(
                tuple(p0_hand),
                game.players[0].melds,
                game.players[0].discards,
            ),
            game.players[1],
        )
    )

    new_game = kong_concealed(prepared_game, 0, tile)

    assert len(new_game.players[0].hand) == len(prepared_game.players[0].hand) - 4
    assert len(new_game.players[0].melds) == 1
    assert new_game.players[0].melds[0].kind == "kong_concealed"
    assert new_game.players[0].melds[0].tiles == (tile, tile, tile, tile)
    assert new_game.pending_kong_draw == 0


def test_kong_added_basic(game):
    tile = 1
    melds = (Meld("pong", (tile, tile, tile)),)
    hand = (tile, 2, 3, 4, 5)
    prepared_game = replace(game,
        players=(
            PlayerState(hand, melds, ()),
            game.players[1],
        )
    )

    new_game = kong_added(prepared_game, 0, tile)

    assert len(new_game.players[0].hand) == len(prepared_game.players[0].hand) - 1
    assert len(new_game.players[0].melds) == 1
    assert new_game.players[0].melds[0].kind == "kong_added"
    assert new_game.players[0].melds[0].tiles == (tile, tile, tile, tile)
    assert new_game.pending_kong_draw == 0


def test_kong_added_no_pong_to_upgrade(game):
    prepared_game = replace(game,
        players=(
            PlayerState((1, 2, 3, 4, 5), (), ()),
            game.players[1],
        )
    )

    with pytest.raises(ValueError):
        kong_added(prepared_game, 0, 1)


def test_kong_added_tile_not_in_hand(game):
    melds = (Meld("pong", (1, 1, 1)),)
    prepared_game = replace(game,
        players=(
            PlayerState((2, 3, 4, 5), melds, ()),
            game.players[1],
        )
    )

    with pytest.raises(ValueError):
        kong_added(prepared_game, 0, 1)
