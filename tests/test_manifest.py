"""Manifest and repository metadata checks."""

import json
from pathlib import Path
import re


def test_manifest_keys_and_version():
    m = json.loads(Path("custom_components/on_air/manifest.json").read_text())
    keys = list(m)
    assert keys[:2] == ["domain", "name"] and keys[2:] == sorted(keys[2:])
    assert (m["domain"], m["iot_class"]) == ("on_air", "cloud_polling")
    # The exact version is checked against the tag by the release workflow.
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"])
    assert m["config_flow"] is True and m["requirements"] == []


def test_hacs_json():
    h = json.loads(Path("hacs.json").read_text())
    assert h["name"] == "On Air" and h["homeassistant"] == "2026.10.0"
