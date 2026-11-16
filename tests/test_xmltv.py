"""XMLTV parsing."""

from datetime import UTC, datetime
import gzip
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.on_air.xmltv import parse_time, parse_xmltv

ROME = ZoneInfo("Europe/Rome")
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def iptv_bytes() -> bytes:
    return (FIXTURES / "iptv_sample.xml").read_bytes()


@pytest.fixture
def open_bytes() -> bytes:
    return (FIXTURES / "open_sample.xml").read_bytes()


def test_offset_and_naive_times():
    assert parse_time("20261115193000 +0000", ROME) == datetime(2026, 11, 15, 19, 30, tzinfo=UTC)
    assert parse_time("20261115213000 +0100", ROME) == datetime(2026, 11, 15, 20, 30, tzinfo=UTC)
    assert parse_time("20261115213000", ROME) == datetime(2026, 11, 15, 20, 30, tzinfo=UTC)
    assert parse_time("2026-11-15", ROME) is None
    assert parse_time("20261315213000 +0000", ROME) is None  # month 13


def test_gzip_and_plain_give_same_result(open_bytes):
    plain = parse_xmltv(open_bytes, source="open_epg")
    assert parse_xmltv(gzip.compress(open_bytes), source="open_epg") == plain
    assert plain.source == "open_epg"


def test_placeholder_and_untitled_are_dropped(iptv_bytes):
    g = parse_xmltv(iptv_bytes, source="iptv_epg")
    assert [p.title for p in g.programmes["skysportuno"]] == ["Tennis"]
    assert [p.title for p in g.programmes["rai2"]] == ["The Rookie"]


def test_first_non_empty_category(iptv_bytes):
    g = parse_xmltv(iptv_bytes, source="iptv_epg")
    assert g.programmes["rai2"][0].category == "Serie TV"


def test_missing_stop_uses_next_start(iptv_bytes):
    p = parse_xmltv(iptv_bytes, source="iptv_epg").programmes["rai1"][0]
    assert (p.title, p.end) == ("Tg1", datetime(2026, 11, 15, 19, 30, tzinfo=UTC))


def test_bad_rows_are_skipped(iptv_bytes):
    g = parse_xmltv(iptv_bytes, source="iptv_epg")
    assert "ghost" not in g.programmes
    assert [p.title for p in g.programmes["rai1"]] == ["Tg1", "UEFA Nations League", "Tg1"]
    assert all(p.start < p.end for ps in g.programmes.values() for p in ps)
    assert all(p.source == "iptv_epg" for ps in g.programmes.values() for p in ps)


def test_channel_without_display_name_uses_id(iptv_bytes):
    g = parse_xmltv(iptv_bytes, source="iptv_epg")
    assert g.channels["nodisplay"] == "nodisplay"
    assert g.channels["skyunoplus1"] == "IT - Sky Uno +1"


def test_naive_times_use_default_tz(open_bytes):
    g = parse_xmltv(open_bytes, source="open_epg", default_tz=ROME)
    assert g.programmes["canale5"][0].start == datetime(2026, 11, 15, 20, 30, tzinfo=UTC)


def test_keep_window_and_duplicate_keys(open_bytes):
    w = (datetime(2026, 11, 15, 19, 0, tzinfo=UTC), datetime(2026, 11, 15, 23, 0, tzinfo=UTC))
    g = parse_xmltv(open_bytes, source="open_epg", keep=lambda k: k == "rai1", window=w)
    assert list(g.channels) == ["rai1"]
    # "Rai 1.it" (3 programmes in the window) wins over "Rai 1 HD 101.it" (2).
    assert [p.title for p in g.programmes["rai1"]] == ["TELEGIORNALE", "Belgio - Italia", "TG1 Sera"]
    assert g.channels["rai1"] == "Rai 1.it"


def test_channels_only_reads_no_programmes(open_bytes):
    g = parse_xmltv(open_bytes, source="open_epg", channels_only=True)
    assert set(g.channels) == {"rai1", "skysportuno", "canale5"}
    assert g.programmes == {}


def _guide(programmes: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><tv>'
        '<channel id="s1"><display-name>Sky Sport Uno</display-name></channel>'
        f"{programmes}</tv>"
    ).encode()


def _prog(start: str, title: str, stop: str | None = None, category: str | None = None) -> str:
    stop_attr = f' stop="{stop} +0000"' if stop else ""
    cat = f"<category>{category}</category>" if category else ""
    return f'<programme channel="s1" start="{start} +0000"{stop_attr}><title>{title}</title>{cat}</programme>'


@pytest.mark.parametrize(
    "title",
    ["15/11/2026", "16.11.26", "2026-11-16", "No Game Today", "no game today",
     "Next Game: Perugia - Torres on 2026-11-16 at 02:15PM EST"],
)
def test_filler_titles_are_dropped(title):
    data = _guide(
        _prog("20261116180000", "Tennis", "20261116190000")
        + _prog("20261116190000", title, "20261116200000")
    )
    g = parse_xmltv(data, source="open_epg")
    assert [p.title for p in g.programmes["skysportuno"]] == ["Tennis"]


@pytest.mark.parametrize("title", ["Ep.7", "Next Gen ATP Finals", "1mattina News", "10050 Cielo Drive", "Tg1 15/11"])
def test_real_titles_are_kept(title):
    g = parse_xmltv(_guide(_prog("20261116190000", title, "20261116200000")), source="open_epg")
    assert [p.title for p in g.programmes["skysportuno"]] == [title]


def test_dropped_filler_still_ends_the_previous_programme():
    # Without stop, a programme ends where the next row starts, filler or not.
    data = _guide(
        _prog("20261116180000", "Tennis")
        + _prog("20261116190000", "15/11/2026")
        + _prog("20261116200000", "Golf", "20261116210000")
    )
    progs = parse_xmltv(data, source="open_epg").programmes["skysportuno"]
    assert [(p.title, p.end.hour) for p in progs] == [("Tennis", 19), ("Golf", 21)]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Sports", "Sport"), ("sports", "Sport"), ("Documentari", "Documentario"),
     ("Sport", "Sport"), ("Cinema", "Cinema"), ("Film", "Film")],
)
def test_category_aliases(raw, expected):
    g = parse_xmltv(_guide(_prog("20261116190000", "Tennis", "20261116200000", raw)), source="iptv_epg")
    assert g.programmes["skysportuno"][0].category == expected
