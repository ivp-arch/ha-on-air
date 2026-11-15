"""Channel identity across guide sources, presets and groups.

Pure module: no Home Assistant imports, so it can be tested on its own.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Final

_PREFIX = re.compile(r"^\s*IT\s*-\s*", re.IGNORECASE)
_SUFFIX = re.compile(r"\.it\s*$", re.IGNORECASE)
# " HD" with an optional channel number ("Rai 1 HD 101").
_HD = re.compile(r"\s+HD(?:\s*\d+)?\b", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]")
_VARIANT_MARK: Final = "plus"

# Agreed with the user on 2026-11-15.
DEFAULT_CHANNELS: Final[tuple[str, ...]] = (
    "rai1",
    "rai2",
    "rai3",
    "rete4",
    "canale5",
    "italia1",
    "skyuno",
    "skyatlantic",
    "skyserie",
    "skycinemauno",
    "skysportuno",
)

# Group -> channel key prefixes.
GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "rai": ("rai",),
    "mediaset": (
        "rete4",
        "canale5",
        "italia1",
        "italia2",
        "la5",
        "iris",
        "focus",
        "topcrime",
        "mediasetextra",
        "boing",
        "cartoonito",
        "tgcom24",
        "cine34",
        "twentyseven",
        "mediaset20",
    ),
    "sky_cinema": ("skycinema",),
    "sky_sport": ("skysport",),
    "sky": (
        "skyuno",
        "skyatlantic",
        "skyserie",
        "skyinvestigation",
        "skycrime",
        "skydocumentaries",
        "skynature",
        "skyarte",
        "skyadventure",
        "skycollection",
    ),
}


def channel_key(display_name: str) -> str:
    """Return a stable key that matches the same channel across sources.

    "IT - La7" and "La 7.it" both become "la7"; "Rai 1 HD 101.it" becomes
    "rai1"; time-shifted variants keep their own key ("Sky Uno +1" ->
    "skyunoplus1").
    """
    name = _PREFIX.sub("", display_name)
    name = _SUFFIX.sub("", name)
    name = _HD.sub("", name)
    name = name.replace("+", f" {_VARIANT_MARK}").lower()
    return _NON_ALNUM.sub("", name)


def clean_name(display_name: str) -> str:
    """Return a readable channel name: "IT - Sky Uno +1" -> "Sky Uno +1", "Rai 1 HD 101.it" -> "Rai 1"."""
    name = _PREFIX.sub("", display_name.strip())
    name = _SUFFIX.sub("", name)
    name = _HD.sub("", name)
    return " ".join(name.split()) or display_name.strip()


def is_variant(display_name: str) -> bool:
    """Return True for time-shifted variants such as "+1", "+24" or "Sky Uno +"."""
    return "+" in display_name


def channels_in_groups(catalog: Mapping[str, str], groups: Iterable[str]) -> list[str]:
    """Return the catalog keys belonging to the groups, without variants.

    ``catalog`` maps channel key -> display name. Unknown groups are ignored.
    The result is sorted by display name.
    """
    prefixes = tuple(p for g in groups for p in GROUPS.get(g, ()))
    if not prefixes:
        return []
    keys = [
        key
        for key in catalog
        if key.startswith(prefixes) and _VARIANT_MARK not in key
    ]
    return sorted(keys, key=lambda k: catalog[k].casefold())
