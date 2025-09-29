from mahjong_duo.rules_core import (
    is_four_concealed_triplets,
    is_four_kongs,
    is_all_terminals,
    is_tanyao,
    is_menzen,
    is_all_triplets,
    is_all_sequences,
    count_concealed_triplets,
    is_full_flush,
    count_kongs,
    compute_score_summary,
    fan_to_points,
    check_yakuman,
    init_game,
    PlayerState,
    Meld,
    replace,
)

SEED = 12345


def test_four_concealed_triplets():
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    assert is_four_concealed_triplets(hand, ())

    melds = (Meld("pong", (0, 0, 0)),)
    assert not is_four_concealed_triplets(hand, melds)

    seq_hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 10, 10)
    assert not is_four_concealed_triplets(seq_hand, ())


def test_four_kongs():
    melds = (
        Meld("kong_exposed", (0, 0, 0, 0)),
        Meld("kong_concealed", (1, 1, 1, 1)),
        Meld("kong_added", (2, 2, 2, 2)),
        Meld("kong_exposed", (3, 3, 3, 3)),
    )
    assert is_four_kongs(melds)

    melds = (
        Meld("kong_exposed", (0, 0, 0, 0)),
        Meld("kong_concealed", (1, 1, 1, 1)),
        Meld("kong_added", (2, 2, 2, 2)),
    )
    assert not is_four_kongs(melds)

    melds = (
        Meld("pong", (0, 0, 0)),
        Meld("pong", (1, 1, 1)),
        Meld("pong", (2, 2, 2)),
        Meld("pong", (3, 3, 3)),
    )
    assert not is_four_kongs(melds)


def test_all_terminals():
    hand = (0, 0, 8, 8, 9, 9, 17, 17, 18, 18, 26, 26, 0, 8)
    assert is_all_terminals(hand, ())

    mixed_hand = (0, 1, 8, 8, 9, 9, 17, 17, 18, 18, 26, 26, 0, 8)
    assert not is_all_terminals(mixed_hand, ())


def test_tanyao():
    hand = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 15, 16)
    assert is_tanyao(hand, ())

    mixed_hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
    assert not is_tanyao(mixed_hand, ())


def test_menzen():
    assert is_menzen((), ())
    assert is_menzen((), (Meld("kong_concealed", (0, 0, 0, 0)),))
    assert not is_menzen((), (Meld("pong", (0, 0, 0)),))
    assert not is_menzen((), (Meld("kong_exposed", (0, 0, 0, 0)),))
    assert not is_menzen((), (Meld("kong_added", (0, 0, 0, 0)),))


def test_all_triplets():
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    assert is_all_triplets(hand, ())

    seq_hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12)
    assert not is_all_triplets(seq_hand, ())


def test_all_sequences():
    hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12)
    assert is_all_sequences(hand, ())

    triplet_hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    assert not is_all_sequences(triplet_hand, ())


def test_count_concealed_triplets():
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    assert count_concealed_triplets(hand, ()) == 4

    hand = (1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    melds = (Meld("pong", (0, 0, 0)),)
    assert count_concealed_triplets(hand, melds) == 3


def test_full_flush():
    hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 0, 0, 0, 1, 1)
    assert is_full_flush(hand, ())

    mixed_hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12)
    assert not is_full_flush(mixed_hand, ())


def test_count_kongs():
    melds = (
        Meld("kong_exposed", (0, 0, 0, 0)),
        Meld("kong_concealed", (1, 1, 1, 1)),
        Meld("kong_added", (2, 2, 2, 2)),
        Meld("pong", (3, 3, 3)),
    )
    assert count_kongs(melds) == 3

    melds = (
        Meld("pong", (0, 0, 0)),
        Meld("pong", (1, 1, 1)),
    )
    assert count_kongs(melds) == 0


def test_fan_to_points():
    assert fan_to_points(1) == 16
    assert fan_to_points(2) == 32
    assert fan_to_points(3) == 64
    assert fan_to_points(0) == 8


def test_check_yakuman():
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    assert check_yakuman(hand, (), "") == 8

    melds = (
        Meld("kong_exposed", (0, 0, 0, 0)),
        Meld("kong_concealed", (1, 1, 1, 1)),
        Meld("kong_added", (2, 2, 2, 2)),
        Meld("kong_exposed", (3, 3, 3, 3)),
    )
    assert check_yakuman((0, 0, 1, 1), melds, "") == 8

    hand = (0, 0, 8, 8, 9, 9, 17, 17, 18, 18, 26, 26, 0, 8)
    assert check_yakuman(hand, (), "") == 8

    non_yaku_hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12)
    assert check_yakuman(non_yaku_hand, (), "") == 0


def test_compute_score_summary():
    game = init_game(SEED)
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    game = replace(game,
        players=(
            PlayerState(hand, (), ()),
            game.players[1],
        )
    )

    summary = compute_score_summary(game, 0, "zimo")

    assert "fan_unit" in summary
    assert "net_score" in summary
    assert "players" in summary
    assert "0" in summary["players"]
    assert "1" in summary["players"]
    assert summary["players"]["0"]["net_change"] > 0
    assert summary["players"]["1"]["net_change"] < 0
    assert "fan_breakdown" in summary["players"]["0"]
    assert "fan_total" in summary["players"]["0"]


def test_compute_score_yakuman():
    game = init_game(SEED)
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    game = replace(game,
        players=(
            PlayerState(hand, (), ()),
            game.players[1],
        )
    )

    summary = compute_score_summary(game, 0, "zimo")
    assert summary["players"]["0"]["fan_total"] >= 8
