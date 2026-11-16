"""Channel keys, variants, presets and groups."""

import pytest

from custom_components.on_air.channels import (
    DEFAULT_CHANNELS,
    GROUPS,
    channel_key,
    channels_in_groups,
    clean_name,
    is_variant,
)


@pytest.mark.parametrize(
    "a,b",
    [
        ("La 7.it", "IT - La7"),
        ("Sky Sport 24.it", "IT - Sky Sport24"),
        ("Rai 1 HD 101.it", "IT - Rai 1"),
        ("TV 8.it", "IT - TV8"),
        ("Nove.it", "IT - NOVE"),
        ("Sky Cinema Uno.it", "IT - Sky Cinema Uno"),
    ],
)
def test_same_channel_same_key(a, b):
    assert channel_key(a) == channel_key(b)


def test_known_keys():
    assert channel_key("IT - Rai 1") == "rai1"
    assert channel_key("Rete 4.it") == "rete4"
    assert channel_key("IT - Sky Sport Uno") == "skysportuno"


def test_variants_keep_distinct_keys():
    keys = {
        channel_key(n)
        for n in ["IT - Sky Uno", "IT - Sky Uno +1", "IT - Sky Uno +", "IT - Sky Cinema Uno +24"]
    }
    assert keys == {"skyuno", "skyunoplus1", "skyunoplus", "skycinemaunoplus24"}


def test_is_variant():
    assert is_variant("IT - Sky Atlantic +1") and is_variant("IT - Sky Uno +")
    assert not is_variant("Rai 1 HD 101.it")


def test_defaults_are_the_agreed_eleven():
    assert DEFAULT_CHANNELS == (
        "rai1", "rai2", "rai3", "rete4", "canale5", "italia1",
        "skyuno", "skyatlantic", "skyserie", "skycinemauno", "skysportuno",
    )


def test_groups_names():
    assert set(GROUPS) == {"rai", "mediaset", "sky_cinema", "sky_sport", "sky"}


def test_group_excludes_variants():
    catalog = {
        "skycinemauno": "Sky Cinema Uno",
        "skycinemaunoplus24": "Sky Cinema Uno +24",
        "skycinemaaction": "Sky Cinema Action",
        "rai1": "Rai 1",
    }
    assert channels_in_groups(catalog, ["sky_cinema"]) == ["skycinemaaction", "skycinemauno"]


def test_groups_union_sorted_by_name_and_unknown_group_ignored():
    catalog = {"rai2": "Rai 2", "rai1": "Rai 1", "canale5": "Canale 5"}
    assert channels_in_groups(catalog, ["mediaset", "rai", "nope"]) == ["canale5", "rai1", "rai2"]


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("IT - Sky Uno +1", "Sky Uno +1"),
        ("Rai 1 HD 101.it", "Rai 1"),
        ("Sky Sport Mix.it", "Sky Sport Mix"),
        ("  IT - La7  ", "La7"),
        ("nodisplay", "nodisplay"),
    ],
)
def test_clean_name(raw, clean):
    assert clean_name(raw) == clean


def test_rai_group_skips_satellite_duplicates_and_radio():
    # Real catalog entries seen on 16/11/2026.
    catalog = {
        "rai": "Rai", "rai1": "Rai 1", "rai4": "Rai 4", "rai45021": "Rai 4 5021",
        "rairadio2": "Rai Radio 2", "raisport": "Rai Sport", "raisport227": "RAI Sport 227",
        "raigulp": "Rai Gulp", "raigulp5042": "Rai Gulp 5042",
    }
    assert channels_in_groups(catalog, ["rai"]) == ["rai1", "rai4", "raigulp", "raisport"]


def test_sky_sport_group_skips_event_channels():
    catalog = {"skysportuno": "Sky Sport Uno", "skysport251": "Sky Sport 251",
               "skysport4k": "Sky Sport 4K", "skysportcalcio": "Sky Sport Calcio"}
    assert channels_in_groups(catalog, ["sky_sport"]) == ["skysportcalcio", "skysportuno"]
