from mahjong_duo.rules_core import (
    can_peng,
    can_kong_exposed,
    can_kong_concealed,
    can_kong_added,
    Meld,
)


def test_can_peng():
    assert can_peng((1, 1, 2, 3), 1)
    assert can_peng((1, 1, 1, 2, 3), 1)
    assert not can_peng((1, 2, 3), 1)
    assert not can_peng((2, 3, 4), 1)


def test_can_kong_exposed():
    assert can_kong_exposed((1, 1, 1, 2, 3), 1)
    assert can_kong_exposed((1, 1, 1, 1, 2, 3), 1)
    assert not can_kong_exposed((1, 1, 2, 3), 1)
    assert not can_kong_exposed((1, 2, 3), 1)


def test_can_kong_concealed():
    assert can_kong_concealed((1, 1, 1, 1, 2, 3)) == 1
    result = can_kong_concealed((1, 1, 1, 1, 2, 2, 2, 2, 3))
    assert result in (1, 2)
    assert can_kong_concealed((1, 1, 1, 2, 3)) is None
    assert can_kong_concealed(()) is None


def test_can_kong_added():
    assert can_kong_added((Meld("pong", (1, 1, 1)),), (1, 2, 3)) == 1
    assert can_kong_added((Meld("pong", (1, 1, 1)),), (2, 3, 4)) is None
    assert can_kong_added((), (1, 1, 1, 1)) is None
    result = can_kong_added(
        (Meld("pong", (1, 1, 1)), Meld("pong", (2, 2, 2))),
        (1, 2, 3),
    )
    assert result in (1, 2)
    assert can_kong_added((Meld("kong_exposed", (1, 1, 1, 1)),), (1, 2, 3)) is None


def test_mixed_meld_types():
    melds = (
        Meld("pong", (1, 1, 1)),
        Meld("kong_exposed", (2, 2, 2, 2)),
        Meld("kong_concealed", (3, 3, 3, 3)),
        Meld("kong_added", (4, 4, 4, 4)),
    )
    hand = (1, 4, 5)

    assert can_kong_added(melds, hand) == 1


def test_edge_cases():
    assert not can_peng((), 1)
    assert not can_kong_exposed((), 1)
    assert can_kong_concealed(()) is None
    assert can_kong_added((), ()) is None

    hand = (1, 1, 2, 3)
    assert not can_peng(hand, 99)
    assert not can_kong_exposed(hand, 99)
