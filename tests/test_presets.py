"""Tests for sentinel1-download v0.2.0: --preset / --year / --season / --pick-best / --qa-mode."""
import argparse
import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))


# Load the hyphenated module via conftest (sentinel1-download already loads it)
import sentinel1_download as s1d  # noqa: E402


# ── PRESETS dict sanity ──
class TestPresets:
    def test_presets_dict_is_nonempty(self):
        assert isinstance(s1d.PRESETS, dict)
        assert len(s1d.PRESETS) >= 3

    def test_annual_2024_full_year(self):
        p = s1d.PRESETS["annual-2024"]
        assert p["start_date"] == "2024-01-01"
        assert p["end_date"] == "2024-12-31"

    def test_flood_2024_summer_flood_season(self):
        p = s1d.PRESETS["flood-2024"]
        assert p["start_date"] == "2024-06-01"
        assert p["end_date"] == "2024-09-30"

    def test_winter_2024_crosses_year(self):
        p = s1d.PRESETS["winter-2024"]
        # 12 月 → 次年 2 月 跨年
        assert p["start_date"] == "2023-12-01"
        assert p["end_date"] == "2024-02-29"


# ── SEASON_MONTHS ──
class TestSeasonMonths:
    def test_summer(self):
        assert s1d.SEASON_MONTHS["summer"] == (6, 8)

    def test_winter_crosses_year(self):
        assert s1d.SEASON_MONTHS["winter"] == (12, 2)


# ── _auto_buffer_for_place ──
class TestAutoBuffer:
    def test_province(self):
        assert s1d._auto_buffer_for_place("四川省") == 5.0

    def test_city(self):
        assert s1d._auto_buffer_for_place("成都市") == 0.6

    def test_district(self):
        assert s1d._auto_buffer_for_place("朝阳区") == 0.15

    def test_county(self):
        assert s1d._auto_buffer_for_place("郫县") == 0.4

    def test_fallback(self):
        assert s1d._auto_buffer_for_place("Some Random") == 0.3

    def test_empty(self):
        assert s1d._auto_buffer_for_place("") == 0.3


# ── apply_preset ──
class TestApplyPreset:
    def _make_args(self, **kw):
        defaults = {
            "preset": None, "year": None, "season": None,
            "start_date": None, "end_date": None,
        }
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_annual_preset(self):
        args = self._make_args(preset="annual-2024")
        out = s1d.apply_preset(args)
        assert out.start_date == "2024-01-01"
        assert out.end_date == "2024-12-31"

    def test_flood_preset(self):
        args = self._make_args(preset="flood-2024")
        out = s1d.apply_preset(args)
        assert out.start_date == "2024-06-01"
        assert out.end_date == "2024-09-30"

    def test_user_date_overrides_preset(self):
        args = self._make_args(preset="annual-2024", start_date="2024-07-01")
        out = s1d.apply_preset(args)
        # 用户显式给 start_date → 不被 preset 覆盖
        assert out.start_date == "2024-07-01"

    def test_year_only(self):
        args = self._make_args(year=2024)
        out = s1d.apply_preset(args)
        assert out.start_date == "2024-01-01"
        assert out.end_date == "2024-12-31"

    def test_year_season_summer(self):
        args = self._make_args(year=2024, season="summer")
        out = s1d.apply_preset(args)
        assert out.start_date == "2024-06-01"
        assert out.end_date == "2024-08-31"

    def test_year_season_winter_crosses_year(self):
        args = self._make_args(year=2024, season="winter")
        out = s1d.apply_preset(args)
        assert out.start_date == "2024-12-01"
        assert out.end_date == "2025-02-28"

    def test_year_season_spring(self):
        args = self._make_args(year=2024, season="spring")
        out = s1d.apply_preset(args)
        assert out.start_date == "2024-03-01"
        assert out.end_date == "2024-05-31"

    def test_invalid_preset_raises(self):
        args = self._make_args(preset="nonexistent")
        with pytest.raises(SystemExit):
            s1d.apply_preset(args)

    def test_invalid_season_raises(self):
        args = self._make_args(year=2024, season="nonexistent")
        with pytest.raises(SystemExit):
            s1d.apply_preset(args)


# ── _write_qa helper ──
class TestWriteQa:
    def test_qa_writes_file(self, tmp_path):
        out = tmp_path / "test.qa.json"
        args = argparse.Namespace(
            start_date="2024-06-01", end_date="2024-08-31",
            polarization="all", orbit_direction="both",
            bands=["vh", "vv"], source="pc",
            preset="flood-2024", year=2024, season=None, pick_best=True,
            qa=str(out),
        )
        query_meta = {
            "bbox": [103.5, 30.0, 104.7, 31.3],
            "returned": 1, "picked": {"id": "S1A_IW_SLC__1SDV_20240801", "datetime": "2024-08-01"},
        }
        features = [
            {"id": "S1A_IW_SLC__1SDV_20240801",
             "properties": {"datetime": "2024-08-01", "platform": "sentinel-1a",
                            "sat:orbit_state": "ascending"}}
        ]
        place_info = {
            "query": "成都市", "display_name": "成都, 四川, 中国",
            "source": "open-meteo", "buffer_deg_used": 0.6,
        }
        s1d._write_qa(args, query_meta, features, place_info, 0, 0.0)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["skill"] == "sentinel1-download"
        assert data["version"] == "0.2.0"
        assert data["query"]["place"]["query"] == "成都市"
        assert data["query"]["place"]["buffer_deg"] == 0.6
        assert data["query"]["preset"] == "flood-2024"
        assert data["query"]["pick_best"] is True
        assert data["picked"]["id"] == "S1A_IW_SLC__1SDV_20240801"
        assert data["scenes"][0]["orbit_direction"] == "ascending"


# ── --help mentions new flags ──
class TestHelpText:
    def test_help_mentions_preset(self, capsys):
        with pytest.raises(SystemExit):
            s1d.build_parser().parse_args(["--help"])
        out = capsys.readouterr().out
        assert "--preset" in out
        assert "--year" in out
        assert "--season" in out
        assert "--pick-best" in out
        assert "--qa-mode" in out
        assert "--place" in out
