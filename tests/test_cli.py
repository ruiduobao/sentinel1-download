"""Tests for CLI argument parsing, output formatting, and edge cases."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

import sentinel1_download


SAMPLE_FEATURES = [
    {
        "id": "S1A_IW_GRDH_1SDV_20240615T031234_20240615T031259_053456_068A1D_1234",
        "collection": "sentinel-1-grd",
        "bbox": [116.0, 39.0, 117.0, 40.0],
        "properties": {
            "datetime": "2024-06-15T03:12:34.000Z",
            "platform": "sentinel-1a",
            "sat:orbit_state": "ascending",
            "sar:polarizations": ["VV", "VH"],
        },
        "assets": {"vh": {}, "vv": {}},
    },
]


def test_format_scene_text_includes_key_fields():
    text = sentinel1_download._format_scene_text(SAMPLE_FEATURES[0], 1)
    assert "S1A_IW_GRDH" in text
    assert "2024-06-15" in text
    assert "sentinel-1a" in text
    assert "ascending" in text


def test_format_scene_json_has_all_keys():
    d = sentinel1_download._format_scene_json(SAMPLE_FEATURES[0])
    assert d["platform"] == "sentinel-1a"
    assert d["orbit_direction"] == "ascending"
    assert d["polarization"] == ["VV", "VH"]
    assert "vh" in d["assets"]


def test_format_results_text_no_features():
    text = sentinel1_download.format_results_text({}, [])
    assert "0 scene(s)" in text
    assert "no scenes match" in text


def test_format_results_json_is_valid_json():
    out = sentinel1_download.format_results_json({"polarization": "vv"}, SAMPLE_FEATURES)
    parsed = json.loads(out)
    assert parsed["count"] == 1
    assert parsed["scenes"][0]["id"] == SAMPLE_FEATURES[0]["id"]


def test_quiet_when_env_set():
    old = os.environ.get("SENTINEL1_DOWNLOAD_QUIET")
    try:
        os.environ["SENTINEL1_DOWNLOAD_QUIET"] = "1"
        assert sentinel1_download._quiet() is True
    finally:
        if old is None:
            os.environ.pop("SENTINEL1_DOWNLOAD_QUIET", None)
        else:
            os.environ["SENTINEL1_DOWNLOAD_QUIET"] = old


def test_main_missing_args_returns_2(capsys):
    rc = sentinel1_download.main([])
    captured = capsys.readouterr()
    assert rc == 2
    assert "missing required arguments" in captured.err


def test_main_help_runs():
    with pytest.raises(SystemExit) as e:
        sentinel1_download.main(["--help"])
    assert e.value.code == 0
