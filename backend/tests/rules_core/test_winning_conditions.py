from mahjong_duo.rules_core import (
    can_hu_four_plus_one,
    _can_form_melds,
    _try_meld_triplet,
    _try_meld_sequence,
    Meld,
)


def test_basic_winning_hand():
    hand = (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4)
    assert can_hu_four_plus_one(hand)


def test_winning_with_sequences():
    hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 10, 10)
    assert can_hu_four_plus_one(hand)


def test_winning_with_melds():
    hand = (1, 1, 2, 2)
    melds = (
        Meld("pong", (3, 3, 3)),
        Meld("pong", (4, 4, 4)),
        Meld("pong", (5, 5, 5)),
    )
    assert not can_hu_four_plus_one(hand, melds)


def test_not_enough_tiles():
    hand = (1, 1, 1, 2, 2)
    assert not can_hu_four_plus_one(hand)


def test_wrong_number_of_tiles():
    hand = (1, 1, 1, 2, 2, 2, 3)
    assert not can_hu_four_plus_one(hand)


def test_no_pair():
    hand = (1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 7)
    assert not can_hu_four_plus_one(hand)


def test_cannot_form_melds():
    working_hand = (1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5)
    failing_hand = (1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 7)

    assert can_hu_four_plus_one(working_hand)
    assert not can_hu_four_plus_one(failing_hand)


def test_try_meld_triplet():
    counts = [3, 2, 1, 0]
    assert _try_meld_triplet(counts, 0)
    assert counts[0] == 0

    counts = [2, 2, 1, 0]
    assert not _try_meld_triplet(counts, 0)
    assert counts[0] == 2


def test_try_meld_sequence():
    counts = [1, 1, 1, 0]
    assert _try_meld_sequence(counts, 0)
    assert counts[0] == counts[1] == counts[2] == 0

    counts = [1, 1, 0, 0]
    assert not _try_meld_sequence(counts, 0)

    counts = [0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0]
    assert not _try_meld_sequence(counts, 7)


def test_complex_winning_hands():
    hand = (0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10)
    assert not can_hu_four_plus_one(hand)

    hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
    assert not can_hu_four_plus_one(hand)

    hand = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12)
    assert can_hu_four_plus_one(hand)


def test_edge_cases():
    assert not can_hu_four_plus_one(())

    hand = (0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3)
    assert can_hu_four_plus_one(hand)


def test_can_form_melds_cache():
    counts = (1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    need = 1

    result1 = _can_form_melds(counts, need)
    assert result1

    result2 = _can_form_melds(counts, need)
    assert result2 == result1


def test_winning_with_different_suits():
    hand = (0, 1, 2, 9, 10, 11, 18, 19, 20, 3, 3, 3, 4, 4)
    assert can_hu_four_plus_one(hand)
