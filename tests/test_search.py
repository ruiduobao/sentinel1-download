"""Tests for STAC search and signing (mocked network)."""

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

import sentinel1_download


SAMPLE_STAC_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "S1A_IW_GRDH_1SDV_20240615T031234",
            "collection": "sentinel-1-grd",
            "bbox": [116.0, 39.0, 117.0, 40.0],
            "properties": {
                "datetime": "2024-06-15T03:12:34.000Z",
                "platform": "sentinel-1a",
                "sat:orbit_state": "ascending",
                "sar:polarizations": ["VV", "VH"],
            },
            "assets": {
                "vh": {"href": "https://example.com/vh.tif"},
                "vv": {"href": "https://example.com/vv.tif"},
            },
        },
    ],
}


def test_stac_endpoints_have_required_keys():
    for src, cfg in sentinel1_download.STAC_ENDPOINTS.items():
        assert "search" in cfg
        assert "root" in cfg
        if src == "pc":
            assert cfg.get("sign") is not None


def test_default_bands():
    assert sentinel1_download.DEFAULT_BANDS == ["vh", "vv"]


def test_stac_search_builds_correct_query():
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=SAMPLE_STAC_RESPONSE)
        return resp

    with patch.object(sentinel1_download.requests, "Session") as MockSession:
        session = MagicMock()
        session.trust_env = False
        session.headers = {}
        session.post = fake_post
        MockSession.return_value = session

        sentinel1_download.stac_search(
            bbox=(116.0, 39.0, 117.0, 40.0),
            start_date="2024-06-01", end_date="2024-06-30",
            polarization="vv+vh", orbit_direction="ascending",
            limit=5, source="pc",
        )

    body = captured["json"]
    assert body["collections"] == ["sentinel-1-grd"]
    assert body["query"]["sar:polarizations"] == {"eq": ["VV", "VH"]}
    assert body["query"]["sat:orbit_state"] == {"eq": "ascending"}


def test_stac_search_invalid_source_raises():
    with pytest.raises(ValueError, match="Unknown source"):
        sentinel1_download.stac_search(
            bbox=(0, 0, 1, 1), start_date="2024-01-01", end_date="2024-01-02", source="bogus",
        )


def test_get_signed_href_aws_returns_href_unchanged():
    item = SAMPLE_STAC_RESPONSE["features"][0]
    href = sentinel1_download.get_signed_href(item, "vh", source="aws")
    assert href == "https://example.com/vh.tif"


def test_get_signed_href_pc_appends_token():
    sentinel1_download._SAS_CACHE.clear()
    fake_token = "se=2026-01-01&sp=rl&sv=2023-11-03"
    with patch.object(sentinel1_download.requests, "Session") as MockSession:
        session = MagicMock()
        session.trust_env = False
        session.headers = {}
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"token": fake_token})
        session.get = MagicMock(return_value=resp)
        MockSession.return_value = session
        item = SAMPLE_STAC_RESPONSE["features"][0]
        href = sentinel1_download.get_signed_href(item, "vh", source="pc")
    assert href.startswith("https://example.com/vh.tif?")
    assert fake_token in href


def test_get_signed_href_missing_asset_returns_none():
    item = SAMPLE_STAC_RESPONSE["features"][0]
    assert sentinel1_download.get_signed_href(item, "nonexistent", source="pc") is None
