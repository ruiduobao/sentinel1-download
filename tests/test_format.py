"""Tests for the --format (csv|json) flag on sentinel1-download.

This module verifies that the new --format side-file export works
independent of the existing --output-format flag.
"""
import csv
import json
import os
import sys
from unittest.mock import patch

import pytest

import sentinel1_download as s1d


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_features():
    return [
        {
            "id": "S1A_IW_GRDH_1SDV_20240624T101408_20240624T101433_054464",
            "type": "Feature",
            "bbox": [121.0, 30.0, 122.0, 31.0],
            "properties": {
                "datetime": "2024-06-24T10:14:08.000Z",
                "platform": "sentinel-1a",
                "constellation": "sentinel-1",
                "instruments": ["c-sar"],
                "sat:orbit_state": "ascending",
                "sar:polarizations": ["VV", "VH"],
                "sar:product_type": "GRD",
            },
            "assets": {"vh": {}, "vv": {}},
        },
        {
            "id": "S1A_IW_GRDH_1SDV_20240710T101411_20240710T101436_054639",
            "type": "Feature",
            "bbox": [121.0, 30.0, 122.0, 31.0],
            "properties": {
                "datetime": "2024-07-10T10:14:11.000Z",
                "platform": "sentinel-1a",
                "constellation": "sentinel-1",
                "instruments": ["c-sar"],
                "sat:orbit_state": "descending",
                "sar:polarizations": ["VV"],
                "sar:product_type": "GRD",
            },
            "assets": {"vv": {}},
        },
    ]


@pytest.fixture
def query_meta():
    return {
        "dataset": "sentinel-1-grd",
        "bbox": [121.0, 30.0, 122.0, 31.0],
        "start_date": "2024-06-01",
        "end_date": "2024-07-31",
        "polarization": "vv+vh",
        "orbit_direction": "both",
        "limit": 50,
    }


# ---------------------------------------------------------------------------
# Parser-level tests
# ---------------------------------------------------------------------------

class TestFormatFlagParser:
    def test_help_lists_format(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "..", "sentinel1-download.py"),
             "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        assert "--format" in text
        assert "csv" in text
        assert "json" in text
        assert "--format-output" in text

    def test_default_format_is_none(self):
        from sentinel1_download import build_parser
        parser = build_parser()
        args = parser.parse_args(["--bbox", "121", "30", "122", "31",
                                  "--start-date", "2024-06-01",
                                  "--end-date", "2024-07-31"])
        assert args.format is None
        assert args.format_output == "./sentinel1_metadata"

    def test_format_csv_choice(self):
        from sentinel1_download import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--bbox", "121", "30", "122", "31",
            "--start-date", "2024-06-01", "--end-date", "2024-07-31",
            "--format", "csv",
        ])
        assert args.format == "csv"

    def test_format_json_choice(self):
        from sentinel1_download import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--bbox", "121", "30", "122", "31",
            "--start-date", "2024-06-01", "--end-date", "2024-07-31",
            "--format", "json",
        ])
        assert args.format == "json"

    def test_output_format_unchanged(self):
        """The new --format must NOT collide with --output-format."""
        from sentinel1_download import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--bbox", "121", "30", "122", "31",
            "--start-date", "2024-06-01", "--end-date", "2024-07-31",
            "--output-format", "json",
            "--format", "csv",
        ])
        assert args.output_format == "json"
        assert args.format == "csv"


# ---------------------------------------------------------------------------
# Helper-function tests
# ---------------------------------------------------------------------------

class TestFormatResultsCsv:
    def test_csv_basic(self, sample_features, query_meta):
        out = s1d.format_results_csv(query_meta, sample_features)
        reader = list(csv.reader(out.splitlines()))
        # Header + 2 rows
        assert len(reader) == 3
        # First column = id
        assert reader[0][0] == "id"
        assert "S1A_IW_GRDH_1SDV_20240624T101408" in reader[1][0]
        # Polarization is a |-joined string
        pol_idx = reader[0].index("polarizations")
        assert "VV" in reader[1][pol_idx]
        assert "VH" in reader[1][pol_idx]

    def test_csv_empty(self, query_meta):
        out = s1d.format_results_csv(query_meta, [])
        reader = list(csv.reader(out.splitlines()))
        # Just the header
        assert len(reader) == 1
        assert reader[0][0] == "id"

    def test_csv_handles_missing_polarizations(self, query_meta):
        feats = [{
            "id": "x", "bbox": [0, 0, 1, 1],
            "properties": {"datetime": "2024-01-01T00:00:00Z"},
            "assets": {},
        }]
        out = s1d.format_results_csv(query_meta, feats)
        reader = list(csv.reader(out.splitlines()))
        assert reader[1][0] == "x"
        pol_idx = reader[0].index("polarizations")
        # Missing polarizations should be an empty string
        assert reader[1][pol_idx] == ""


class TestWriteMetadataFile:
    def test_write_csv(self, sample_features, query_meta, tmp_path):
        out_path = str(tmp_path / "meta.csv")
        written = s1d.write_metadata_file("csv", out_path, query_meta, sample_features)
        # write_metadata_file writes to whatever path it's given (extension is
        # the caller's responsibility). It returns the path written.
        assert written == out_path
        assert os.path.exists(written)
        with open(written, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == "id"

    def test_write_json(self, sample_features, query_meta, tmp_path):
        out_path = str(tmp_path / "meta.json")
        written = s1d.write_metadata_file("json", out_path, query_meta, sample_features)
        assert written == out_path
        with open(written, encoding="utf-8") as f:
            d = json.load(f)
        assert d["count"] == 2
        assert d["query"] == query_meta
        assert d["scenes"][0]["id"] == sample_features[0]["id"]

    def test_invalid_format_raises(self, sample_features, query_meta, tmp_path):
        out_path = str(tmp_path / "x")
        with pytest.raises(ValueError):
            s1d.write_metadata_file("xml", out_path, query_meta, sample_features)
