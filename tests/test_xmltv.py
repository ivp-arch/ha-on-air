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
