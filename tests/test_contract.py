"""Attribute contract v1."""

from datetime import UTC, datetime, timedelta
import json

from custom_components.on_air.contract import (
    CONTRACT_VERSION,
    UNRECORDED_ATTRIBUTES,
    channel_attributes,
    channel_state,
)
from custom_components.on_air.models import SourceStatus
from tests.helpers import ROME, prog, rome

D = (2026, 11, 15)
AT = rome(*D, 21, 40)
WINDOW = (rome(*D, 20), rome(2026, 11, 16, 0))
UPDATED = datetime(2026, 11, 15, 11, 5, tzinfo=UTC)
SOURCES = {
    "open_epg": SourceStatus("ok", UPDATED),
    "iptv_epg": SourceStatus("error", None),
}
RAI1 = [
    prog("Tg1", rome(*D, 20, 0), rome(*D, 20, 30), "Notizie", "iptv_epg"),
    prog("Belgio - Italia", rome(*D, 20, 30), rome(*D, 23, 20), "Sport"),
    prog("Tg1", rome(*D, 23, 20), rome(*D, 23, 25), "Notizie", "iptv_epg"),
]
KEYS = {"contract_version", "channel_name", "now", "next", "tonight",
        "tonight_window", "updated_at", "sources"}


def test_attributes_shape_and_values():
    a = channel_attributes("Rai 1", RAI1, AT, WINDOW, UPDATED, SOURCES, ROME)
    assert set(a) == KEYS
    assert a["contract_version"] == CONTRACT_VERSION == 1
    assert a["channel_name"] == "Rai 1"
    assert a["now"] == {
        "title": "Belgio - Italia",
        "start": "2026-11-15T20:30:00+01:00",
        "end": "2026-11-15T23:20:00+01:00",
        "category": "Sport",
        "source": "open_epg",
    }
    assert a["next"]["title"] == "Tg1" and a["next"]["source"] == "iptv_epg"
    assert [x["title"] for x in a["tonight"]] == ["Tg1", "Belgio - Italia", "Tg1"]
    assert a["tonight_window"] == {"start": "2026-11-15T20:00:00+01:00", "end": "2026-11-16T00:00:00+01:00"}
    assert a["updated_at"] == "2026-11-15T12:05:00+01:00"
    assert a["sources"] == {
        "open_epg": {"status": "ok", "updated_at": "2026-11-15T12:05:00+01:00"},
        "iptv_epg": {"status": "error", "updated_at": None},
    }
    json.dumps(a)  # serializable


def test_gap_gives_unknown_state_and_next():
    gap = [prog("Tg2", rome(*D, 20, 30), rome(*D, 20, 50)),
           prog("The Rookie", rome(*D, 21, 10), rome(*D, 21, 50), "Serie TV")]
    at = rome(*D, 21, 0)
    assert channel_state(gap, at) is None
    a = channel_attributes("Rai 2", gap, at, WINDOW, None, {}, ROME)
    assert a["now"] is None and a["next"]["title"] == "The Rookie"
    assert a["updated_at"] is None and a["sources"] == {}


def test_next_is_null_after_last_programme():
    rete4 = [prog("Fuori dal coro", rome(*D, 21, 33), rome(2026, 11, 16, 0, 57), "Informazione")]
    a = channel_attributes("Rete 4", rete4, AT, WINDOW, None, {}, ROME)
    assert a["now"]["title"] == "Fuori dal coro" and a["next"] is None


def test_no_programmes_at_all():
    a = channel_attributes("Ghost", [], AT, WINDOW, None, {}, ROME)
    assert (a["now"], a["next"], a["tonight"]) == (None, None, [])
    assert channel_state([], AT) is None


def test_state_truncated_to_255():
    p = prog("x" * 300, rome(*D, 21), rome(*D, 22))
    assert channel_state([p], AT) == "x" * 255
    a = channel_attributes("X", [p], AT, WINDOW, None, {}, ROME)
    assert len(a["now"]["title"]) == 300  # attributes keep the full title


def test_attributes_stay_far_below_recorder_limit():
    step = timedelta(minutes=20)
    progs = [
        prog("t" * 200, rome(*D, 20) + i * step, rome(*D, 20) + (i + 1) * step,
             "Intrattenimento", "iptv_epg")
        for i in range(12)
    ]
    a = channel_attributes("X", progs, AT, WINDOW, UPDATED, SOURCES, ROME)
    assert len(a["tonight"]) == 12
    assert len(json.dumps(a).encode()) < 16384 // 2


def test_unrecorded_attributes():
    assert UNRECORDED_ATTRIBUTES == frozenset({"next", "tonight", "tonight_window"})
