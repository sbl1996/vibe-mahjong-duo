import pytest

from mahjong_duo.rules_core import (
    init_game,
    PlayerState,
    Meld,
    prepare_added_kong,
    resolve_rob_kong_hu,
    resolve_rob_kong_pass,
    can_hu_four_plus_one,
    replace,
)

SEED = 12345


@pytest.fixture
def game():
    return init_game(SEED)


def test_prepare_added_kong_no_rob_possible(game):
    tile = 1
    melds = (Meld("pong", (tile, tile, tile)),)
    hand = (tile, 2, 3, 4, 5)

    prepared_game = replace(game,
        players=(
            PlayerState(hand, melds, ()),
            PlayerState((6, 7, 8, 9, 10), (), ()),
        )
    )

    result = prepare_added_kong(prepared_game, 0, tile)

    assert not result.rob_pending
    assert len(result.state.players[0].melds) == 1
    assert result.state.players[0].melds[0].kind == "kong_added"


def test_prepare_added_kong_with_rob_possible(game):
    tile = 10
    melds = (Meld("pong", (tile, tile, tile)),)
    hand = (tile, 2, 3, 4, 5)

    robber_hand = (6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10)
    robber_hand_with_tile = tuple(sorted(robber_hand + (tile,)))
    assert can_hu_four_plus_one(robber_hand_with_tile, ())

    prepared_game = replace(game,
        players=(
            PlayerState(hand, melds, ()),
            PlayerState(robber_hand, (), ()),
        )
    )

    result = prepare_added_kong(prepared_game, 0, tile)

    assert result.rob_pending
    assert result.state.pending_rob_kong == (0, tile)
    assert result.state.turn == 1


def test_prepare_added_kong_illegal(game):
    melds = (Meld("pong", (1, 1, 1)),)
    prepared_game = replace(game,
        players=(
            PlayerState((2, 3, 4, 5), melds, ()),
            game.players[1],
        )
    )

    with pytest.raises(ValueError):
        prepare_added_kong(prepared_game, 0, 1)


def test_prepare_added_kong_no_pong_to_upgrade(game):
    prepared_game = replace(game,
        players=(
            PlayerState((1, 2, 3, 4, 5), (), ()),
            game.players[1],
        )
    )

    with pytest.raises(ValueError):
        prepare_added_kong(prepared_game, 0, 1)


def test_resolve_rob_kong_hu_basic(game):
    tile = 1
    pending_game = replace(game,pending_rob_kong=(0, tile), turn=1)

    result = resolve_rob_kong_hu(pending_game, 1)

    assert result.state.ended
    assert result.state.turn == 1
    assert result.state.pending_rob_kong is None
    assert result.kong_owner == 0
    assert result.tile == tile


def test_resolve_rob_kong_hu_with_specific_tile(game):
    tile = 1
    pending_game = replace(game,pending_rob_kong=(0, tile), turn=1)

    result = resolve_rob_kong_hu(pending_game, 1, tile)

    assert result.tile == tile


def test_resolve_rob_kong_hu_illegal_no_pending(game):
    with pytest.raises(ValueError):
        resolve_rob_kong_hu(game, 1)


def test_resolve_rob_kong_hu_illegal_wrong_robber(game):
    tile = 1
    pending_game = replace(game,pending_rob_kong=(0, tile), turn=1)

    with pytest.raises(ValueError):
        resolve_rob_kong_hu(pending_game, 0)


def test_resolve_rob_kong_pass_basic(game):
    tile = 1
    pending_game = replace(game,pending_rob_kong=(0, tile), turn=1)

    result = resolve_rob_kong_pass(pending_game, 1)

    assert result.state.pending_rob_kong is None
    assert result.state.turn == 0
    assert result.kong_owner == 0
    assert result.tile == tile


def test_resolve_rob_kong_pass_illegal_no_pending(game):
    with pytest.raises(ValueError):
        resolve_rob_kong_pass(game, 1)


def test_resolve_rob_kong_pass_illegal_wrong_robber(game):
    tile = 1
    pending_game = replace(game,pending_rob_kong=(0, tile), turn=1)

    with pytest.raises(ValueError):
        resolve_rob_kong_pass(pending_game, 0)


def test_complete_rob_kong_scenario(game):
    tile = 10
    melds = (Meld("pong", (tile, tile, tile)),)
    hand = (tile, 2, 3, 4, 5)
    robber_hand = (6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10)

    prepared_game = replace(game,
        players=(
            PlayerState(hand, melds, ()),
            PlayerState(robber_hand, (), ()),
        )
    )

    step1 = prepare_added_kong(prepared_game, 0, tile)
    assert step1.rob_pending

    step2 = resolve_rob_kong_hu(step1.state, 1)

    assert step2.state.ended
    assert step2.state.pending_rob_kong is None
    assert step2.state.turn == 1


def test_complete_rob_kong_pass_scenario(game):
    tile = 1
    melds = (Meld("pong", (tile, tile, tile)),)
    hand = (tile, 2, 3, 4, 5)

    prepared_game = replace(game,
        players=(
            PlayerState(hand, melds, ()),
            PlayerState((6, 7, 8, 9, 10), (), ()),
        )
    )

    step1 = prepare_added_kong(prepared_game, 0, tile)

    assert not step1.rob_pending
    assert len(step1.state.players[0].melds) == 1
    assert step1.state.players[0].melds[0].kind == "kong_added"
