"""Integration smoke tests against the real Planetary Computer STAC."""

import os
import pytest
import sentinel1_download


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.environ.get("RUN_S1_INTEGRATION"),
    reason="set RUN_S1_INTEGRATION=1 to run real-network tests",
)
def test_real_stac_search_returns_scene():
    resp = sentinel1_download.stac_search(
        bbox=(116.0, 39.0, 117.0, 40.0),
        start_date="2024-06-01",
        end_date="2024-06-30",
        polarization="vv+vh",
        limit=3,
        source="pc",
    )
    features = resp.get("features", [])
    assert len(features) >= 1
    assert "S1" in features[0]["id"]


@pytest.mark.skipif(
    not os.environ.get("RUN_S1_INTEGRATION"),
    reason="set RUN_S1_INTEGRATION=1 to run real-network tests",
)
def test_real_list_bands_endpoint():
    import requests
    session = requests.Session()
    if os.environ.get("SENTINEL1_DOWNLOAD_USE_PROXY") != "1":
        session.trust_env = False
    r = session.get(
        "https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-grd",
        timeout=30,
    )
    r.raise_for_status()
    coll = r.json()
    asset_keys = set((coll.get("item_assets") or {}).keys())
    for b in sentinel1_download.DEFAULT_BANDS:
        assert b in asset_keys, f"default band {b!r} not in collection item_assets"
