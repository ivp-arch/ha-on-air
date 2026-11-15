"""Merging guide sources per channel."""

from datetime import UTC, datetime, timedelta

from custom_components.on_air.const import SOURCE_ORDER
from custom_components.on_air.merge import merge_guides, merge_programmes
from custom_components.on_air.models import Programme, SourceGuide


def t(h: int, m: int = 0) -> datetime:
    """15/11/2026 at h:m UTC (h may exceed 23)."""
    return datetime(2026, 11, 15, tzinfo=UTC) + timedelta(hours=h, minutes=m)


def p(title, start, end, category=None, source="open_epg") -> Programme:
    return Programme(title, start, end, category, source)


def test_category_from_secondary_within_tolerance():
    out = merge_programmes(
        {
            "open_epg": [p("Belgio - Italia", t(19, 30), t(22, 20))],
            "iptv_epg": [p("UEFA Nations League", t(19, 30), t(22, 20), "Sport", "iptv_epg")],
        },
        SOURCE_ORDER,
    )
    assert [(x.title, x.category, x.source) for x in out] == [("Belgio - Italia", "Sport", "open_epg")]


def _pair(offset_min: int):
    return {
        "open_epg": [p("Belgio - Italia", t(19, 30), t(22, 20))],
        "iptv_epg": [
            p("UEFA", t(19, 30 + offset_min), t(22, 20), "Sport", "iptv_epg"),
        ],
    }


def test_tolerance_is_five_minutes_inclusive():
    assert merge_programmes(_pair(5), SOURCE_ORDER)[0].category == "Sport"
    assert merge_programmes(_pair(6), SOURCE_ORDER)[0].category is None


def test_primary_category_is_kept():
    out = merge_programmes(
        {
            "open_epg": [p("Film", t(20), t(22), "Film")],
            "iptv_epg": [p("Film", t(20), t(22), "Intrattenimento", "iptv_epg")],
        },
        SOURCE_ORDER,
    )
    assert out[0].category == "Film"


def test_gaps_filled_and_clipped():
    # Primary: 19-20 and 21-22 UTC. Secondary fills before, between and after.
    out = merge_programmes(
        {
            "open_epg": [p("A", t(19), t(20)), p("B", t(21), t(22))],
            "iptv_epg": [
                p("Prima", t(18), t(19), "News", "iptv_epg"),
                p("Film", t(19, 55), t(21, 10), "Film", "iptv_epg"),
                p("Sliver", t(21, 58), t(22, 3), None, "iptv_epg"),
                p("Dopo", t(22), t(23), "Show", "iptv_epg"),
            ],
        },
        SOURCE_ORDER,
    )
    got = [(x.title, x.start, x.end, x.source) for x in out]
    assert got == [
        ("Prima", t(18), t(19), "iptv_epg"),
        ("A", t(19), t(20), "open_epg"),
        ("Film", t(20), t(21), "iptv_epg"),  # clipped to the gap
        ("B", t(21), t(22), "open_epg"),
        ("Dopo", t(22), t(23), "iptv_epg"),  # "Sliver" left only 3 minutes: dropped
    ]
    assert all(a.end <= b.start for a, b in zip(out, out[1:]))


def test_primary_empty_uses_secondary():
    sec = [p("X", t(19), t(20), "News", "iptv_epg"), p("Y", t(20), t(21), None, "iptv_epg")]
    out = merge_programmes({"open_epg": [], "iptv_epg": sec}, SOURCE_ORDER)
    assert out == sec


def test_no_data_at_all():
    assert merge_programmes({"open_epg": [], "iptv_epg": []}, SOURCE_ORDER) == []


def test_overlaps_inside_one_source_are_trimmed():
    out = merge_programmes(
        {"open_epg": [p("X", t(19), t(20, 10)), p("Y", t(20), t(21))]}, SOURCE_ORDER
    )
    assert [(x.title, x.end) for x in out] == [("X", t(20)), ("Y", t(21))]


def test_merge_guides_names_and_keys():
    open_g = SourceGuide(
        "open_epg",
        {"rai1": "Rai 1.it", "skysportmix": "Sky Sport Mix.it"},
        {"rai1": [p("Belgio - Italia", t(19, 30), t(22, 20))]},
    )
    iptv_g = SourceGuide(
        "iptv_epg",
        {"rai1": "IT - Rai 1", "skycrime": "IT - Sky Crime"},
        {
            "rai1": [p("UEFA", t(19, 30), t(22, 20), "Sport", "iptv_epg")],
            "skycrime": [p("Delitti", t(20), t(21), "Crime", "iptv_epg")],
        },
    )
    names, progs = merge_guides([iptv_g, open_g], SOURCE_ORDER)
    assert names == {"rai1": "Rai 1", "skysportmix": "Sky Sport Mix", "skycrime": "Sky Crime"}
    assert progs["rai1"][0].category == "Sport" and progs["rai1"][0].source == "open_epg"
    assert progs["skycrime"][0].title == "Delitti"
    assert "skysportmix" not in progs
