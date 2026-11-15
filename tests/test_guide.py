"""Now, next, tonight and timer boundaries."""

from datetime import time

from custom_components.on_air.guide import (
    next_boundary,
    now_next,
    overlapping,
    tonight_window,
)
from tests.helpers import prog, rome

D = (2026, 11, 15)
RAI1 = [
    prog("Tg1", rome(*D, 20, 0), rome(*D, 20, 30), "Notizie"),
    prog("Belgio - Italia", rome(*D, 20, 30), rome(*D, 23, 20), "Sport"),
    prog("Tg1", rome(*D, 23, 20), rome(*D, 23, 25), "Notizie"),
]
GAP = [  # nothing between 20:50 and 21:10
    prog("Tg2", rome(*D, 20, 30), rome(*D, 20, 50)),
    prog("The Rookie", rome(*D, 21, 10), rome(*D, 21, 50), "Serie TV"),
]


def test_now_and_next():
    now, nxt = now_next(RAI1, rome(*D, 21, 40))
    assert (now.title, nxt.title) == ("Belgio - Italia", "Tg1")


def test_start_is_inclusive_end_exclusive():
    now, nxt = now_next(RAI1, rome(*D, 20, 30))
    assert now.title == "Belgio - Italia" and nxt.start == rome(*D, 23, 20)


def test_gap_has_no_now_but_has_next():
    now, nxt = now_next(GAP, rome(*D, 21, 0))
    assert now is None and nxt.title == "The Rookie"


def test_after_last_programme():
    assert now_next(RAI1, rome(*D, 23, 40)) == (None, None)


def test_overlapping_includes_programme_started_before_window():
    progs = [prog("D'Artagnan", rome(*D, 19, 10), rome(*D, 21, 15)), *RAI1]
    got = overlapping(progs, rome(*D, 20), rome(2026, 11, 16, 0))
    assert [p.title for p in got] == ["D'Artagnan", "Tg1", "Belgio - Italia", "Tg1"]
    assert overlapping(progs, rome(*D, 23, 30), rome(*D, 23, 40)) == []


def test_tonight_window_rolls_over_until_six():
    s, e = time(20), time(0)
    assert tonight_window(rome(2026, 11, 16, 0, 30), s, e) == (rome(*D, 20), rome(2026, 11, 16, 0))
    assert tonight_window(rome(2026, 11, 16, 5, 59), s, e)[0] == rome(*D, 20)
    assert tonight_window(rome(2026, 11, 16, 6, 0), s, e)[0] == rome(2026, 11, 16, 20)
    assert tonight_window(rome(*D, 21, 40), s, e) == (rome(*D, 20), rome(2026, 11, 16, 0))


def test_tonight_window_same_day_end():
    assert tonight_window(rome(*D, 12), time(20), time(23, 30)) == (rome(*D, 20), rome(*D, 23, 30))


def test_next_boundary():
    assert next_boundary(RAI1, rome(*D, 21, 40)) == rome(*D, 23, 20)
    assert next_boundary(GAP, rome(*D, 21, 0)) == rome(*D, 21, 10)
    assert next_boundary(RAI1, rome(*D, 19, 0)) == rome(*D, 20, 0)
    assert next_boundary(RAI1, rome(*D, 23, 30)) is None
