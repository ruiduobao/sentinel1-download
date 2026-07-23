#!/usr/bin/env python3
"""Sentinel-1 SAR Downloader | Sentinel-1 SAR 影像下载器

通过 STAC API 搜索并下载 Sentinel-1 SAR (C 波段) GRD 影像。
沿用 Landsat Downloader 的架构（STAC + 单文件 CLI + 可视化进度 +
`.part` 安全写入），适配 Sentinel-1 的元数据约定（极化方式、轨道方向）。

数据源 / Source
----------------
* **Planetary Computer**（默认） — 公开 STAC + Azure Blob，无凭证
* **AWS Open Data / Element84 Earth Search**（可选） — 公开 STAC

License
-------
MIT-0. Sentinel-1 data © ESA Copernicus (free and open).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# STAC endpoints
# ---------------------------------------------------------------------------

STAC_ENDPOINTS = {
    "pc": {
        "search": "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        "root": "https://planetarycomputer.microsoft.com/api/stac/v1/",
        "sign": "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}",
    },
    "aws": {
        "search": "https://earth-search.aws.element84.com/v1/search",
        "root": "https://earth-search.aws.element84.com/v1/",
        "sign": None,
    },
}

SENTINEL1_COLLECTION = "sentinel-1-grd"

DEFAULT_BANDS = ["vh", "vv"]

BAND_DESCRIPTIONS: Dict[str, Tuple[str, str]] = {
    "vh": ("VH polarization (cross-pol)", "VH 极化（交叉极化）"),
    "vv": ("VV polarization (co-pol)", "VV 极化（共极化）"),
}

USER_AGENT = "sentinel1-download/0.1.0 (+https://clawhub.ai/skills/sentinel1-download)"

DEFAULT_TRUST_ENV = os.environ.get("SENTINEL1_DOWNLOAD_USE_PROXY") == "1"

_SAS_CACHE: Dict[str, Tuple[str, float]] = {}


def _quiet() -> bool:
    return os.environ.get("SENTINEL1_DOWNLOAD_QUIET") == "1"


def _emit_privacy_notice(source: str) -> None:
    if _quiet():
        return
    msg = (
        f"[sentinel1-download] contacting {source} STAC endpoint "
        f"(no API keys / no local files / no PII sent; "
        f"Sentinel-1 data © ESA Copernicus free and open). "
        f"Set SENTINEL1_DOWNLOAD_QUIET=1 to suppress this notice."
    )
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# STAC search
# ---------------------------------------------------------------------------

def stac_search(
    *,
    bbox: Tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    polarization: str = "all",
    orbit_direction: str = "both",
    limit: int = 10,
    source: str = "pc",
    timeout: int = 60,
) -> Dict[str, Any]:
    if source not in STAC_ENDPOINTS:
        raise ValueError(f"Unknown source: {source!r}; expected one of {list(STAC_ENDPOINTS)}")

    datetime_range = f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"

    query: Dict[str, Any] = {}
    if polarization != "all":
        pol_map = {"vv": ["VV"], "vh": ["VH"], "vv+vh": ["VV", "VH"]}
        pol_val = pol_map.get(polarization.lower())
        if pol_val:
            query["sar:polarizations"] = {"eq": pol_val}

    if orbit_direction == "ascending":
        query["sat:orbit_state"] = {"eq": "ascending"}
    elif orbit_direction == "descending":
        query["sat:orbit_state"] = {"eq": "descending"}

    body: Dict[str, Any] = {
        "collections": [SENTINEL1_COLLECTION],
        "bbox": list(bbox),
        "datetime": datetime_range,
        "limit": int(limit),
        "query": query,
    }
    if source == "pc":
        body["sortby"] = [{"field": "datetime", "direction": "desc"}]

    session = requests.Session()
    session.trust_env = DEFAULT_TRUST_ENV
    session.headers.update({"User-Agent": USER_AGENT, "Content-Type": "application/json"})

    url = STAC_ENDPOINTS[source]["search"]
    _emit_privacy_notice("Planetary Computer" if source == "pc" else "AWS Earth Search")

    r = session.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Planetary Computer signing
# ---------------------------------------------------------------------------

def get_signed_href(item: Dict[str, Any], asset_key: str, source: str = "pc") -> Optional[str]:
    asset = item.get("assets", {}).get(asset_key)
    if not asset:
        return None
    href = asset.get("href")
    if not href:
        return None

    if source == "aws":
        return href

    collection = item.get("collection", SENTINEL1_COLLECTION)
    token, expires_at = _SAS_CACHE.get(collection, ("", 0.0))
    now = time.time()
    if not token or now >= expires_at - 60:
        sign_url = STAC_ENDPOINTS["pc"]["sign"].format(collection=collection)
        session = requests.Session()
        session.trust_env = DEFAULT_TRUST_ENV
        session.headers.update({"User-Agent": USER_AGENT})
        r = session.get(sign_url, timeout=30)
        r.raise_for_status()
        token = r.json().get("token") or r.text.strip().strip('"')
        _SAS_CACHE[collection] = (token, now + 50 * 60)
    return f"{href}?{token}"


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _format_scene_text(item: Dict[str, Any], idx: int) -> str:
    item_id = item.get("id", "?")
    props = item.get("properties", {})
    datetime_str = props.get("datetime", "")[:10] or "?"
    platform = props.get("platform", "?")
    orbit_dir = props.get("sat:orbit_state", "?")
    pol = props.get("sar:polarizations", props.get("polarization", "?"))
    if isinstance(pol, list):
        pol = "+".join(pol)
    assets = list(item.get("assets", {}).keys())
    assets_str = " ".join(assets) if assets else "-"
    if len(assets_str) > 60:
        assets_str = assets_str[:57] + "..."
    return (
        f"  {idx}. {item_id}\n"
        f"     Date:        {datetime_str}\n"
        f"     Platform:    {platform}\n"
        f"     Orbit:       {orbit_dir}\n"
        f"     Polarization:{pol}\n"
        f"     Assets:      {assets_str}\n"
    )


def _format_scene_json(item: Dict[str, Any]) -> Dict[str, Any]:
    props = item.get("properties", {})
    return {
        "id": item.get("id"),
        "datetime": props.get("datetime"),
        "platform": props.get("platform"),
        "orbit_direction": props.get("sat:orbit_state"),
        "polarization": props.get("sar:polarizations"),
        "assets": list(item.get("assets", {}).keys()),
        "bbox": item.get("bbox"),
    }


def format_results_text(query_meta: Dict[str, Any], features: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append(f"[sentinel1-download] found {len(features)} scene(s)")
    if query_meta.get("polarization") and query_meta["polarization"] != "all":
        lines.append(f"[sentinel1-download] polarization = {query_meta['polarization']}")
    if query_meta.get("orbit_direction") and query_meta["orbit_direction"] != "both":
        lines.append(f"[sentinel1-download] orbit = {query_meta['orbit_direction']}")
    lines.append("")
    for i, f in enumerate(features, 1):
        lines.append(_format_scene_text(f, i))
    if not features:
        lines.append("  (no scenes match the query — try widening bbox or date range)")
    return "\n".join(lines)


def format_results_json(query_meta: Dict[str, Any], features: List[Dict[str, Any]]) -> str:
    return json.dumps(
        {"query": query_meta, "count": len(features), "scenes": [_format_scene_json(f) for f in features]},
        ensure_ascii=False, indent=2,
    )


# ---------------------------------------------------------------------------
# Download with progress
# ---------------------------------------------------------------------------

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _render_progress(downloaded: int, total: Optional[int], speed_bps: float,
                     eta_seconds: Optional[float], bar_width: int = 30) -> str:
    if total and total > 0:
        pct = downloaded / total
        filled = int(bar_width * pct)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct_str = f"{pct * 100:5.1f}%"
    else:
        bar = "?" * bar_width
        pct_str = "  ?  %"
    dl_str = _human_bytes(downloaded)
    tot_str = _human_bytes(total) if (total and total > 0) else "??"
    speed_str = f"{_human_bytes(int(speed_bps))}/s"
    if eta_seconds is not None and eta_seconds >= 0:
        m, s = divmod(int(eta_seconds), 60)
        eta_str = f"{m}:{s:02d}"
    else:
        eta_str = "  ?  "
    return f"┃{bar}┃ {pct_str}  {dl_str:>9s} / {tot_str:<9s}  {speed_str:>11s}  ETA {eta_str}"


def download_asset(url: str, dest_path: str, timeout: int = 600,
                   show_progress: bool = True) -> Tuple[bool, str]:
    tmp_path = dest_path + ".part"
    if os.path.exists(dest_path) and not os.path.exists(tmp_path):
        if not _quiet():
            print(f"  ↳ {os.path.basename(dest_path):<20s} already exists, skipping", file=sys.stderr)
        return True, "already exists, skipping"
    try:
        with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0)) or None
            downloaded = 0
            t0 = time.time()
            last_print = t0
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if show_progress and not _quiet() and (now - last_print) > 0.1:
                        elapsed = now - t0
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = ((total - downloaded) / speed) if (total and speed > 0) else None
                        line = _render_progress(downloaded, total, speed, eta)
                        sys.stdout.write(f"\r  ↳ {os.path.basename(dest_path):<20s} {line}")
                        sys.stdout.flush()
                        last_print = now
        if show_progress and not _quiet():
            sys.stdout.write("\n")
            sys.stdout.flush()
        os.replace(tmp_path, dest_path)
        return True, "ok"
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False, str(e)[:200]


def download_scene(item: Dict[str, Any], bands: List[str], output_dir: str,
                   source: str = "pc", timeout: int = 600,
                   show_progress: bool = True) -> Dict[str, Any]:
    item_id = item.get("id", "unknown")
    scene_dir = os.path.join(output_dir, item_id)
    os.makedirs(scene_dir, exist_ok=True)

    result: Dict[str, Any] = {"scene_id": item_id, "ok": True, "files": [], "total_bytes": 0}

    if not _quiet():
        print(f"\n[sentinel1-download] downloading {item_id}", file=sys.stderr)

    for band in bands:
        if band not in item.get("assets", {}):
            result["files"].append({"asset": band, "ok": False, "message": "asset not in item"})
            result["ok"] = False
            continue
        href = get_signed_href(item, band, source=source)
        if not href:
            result["files"].append({"asset": band, "ok": False, "message": "no signed href"})
            result["ok"] = False
            continue
        ext = ".tif"
        dest = os.path.join(scene_dir, f"{band}{ext}")
        ok, msg = download_asset(href, dest, timeout=timeout, show_progress=show_progress)
        result["files"].append({"asset": band, "path": dest, "ok": ok, "message": msg})
        if ok and os.path.exists(dest):
            result["total_bytes"] += os.path.getsize(dest)
        if not ok:
            result["ok"] = False
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sentinel1-download",
        description=(
            "Search and download Sentinel-1 SAR (C-band) GRD imagery "
            "via STAC. Default backend: Microsoft Planetary Computer (public). "
            "通过 STAC 搜索和下载 Sentinel-1 SAR GRD 影像。"
        ),
    )
    p.add_argument("--bbox", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                   help="Geographic extent in WGS84")
    p.add_argument("--start-date", help="Start date YYYY-MM-DD")
    p.add_argument("--end-date", help="End date YYYY-MM-DD")
    p.add_argument("--polarization", default="all", choices=["vv", "vh", "vv+vh", "all"],
                   help="Polarization filter (default: all)")
    p.add_argument("--orbit-direction", default="both", choices=["ascending", "descending", "both"],
                   help="Orbit direction (default: both)")
    p.add_argument("--limit", type=int, default=10, help="Max scenes to return (default 10)")
    p.add_argument("--bands", nargs="+", default=DEFAULT_BANDS,
                   help=f"Assets to download (default: {' '.join(DEFAULT_BANDS)})")
    p.add_argument("--download", action="store_true", help="Trigger actual download")
    p.add_argument("--output-dir", default="./sentinel1_data", help="Download directory")
    p.add_argument("--output-format", default="text", choices=["text", "json"], help="Output format")
    p.add_argument("--source", default="pc", choices=["pc", "aws"], help="STAC backend")
    p.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    p.add_argument("--download-timeout", type=int, default=600, help="Per-asset timeout seconds")
    p.add_argument("--quiet", action="store_true", help="Suppress progress + privacy notice")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    missing = []
    if not args.bbox: missing.append("--bbox")
    if not args.start_date: missing.append("--start-date")
    if not args.end_date: missing.append("--end-date")
    if missing:
        print(f"ERROR: missing required arguments: {', '.join(missing)}", file=sys.stderr)
        return 2

    if args.quiet:
        os.environ["SENTINEL1_DOWNLOAD_QUIET"] = "1"

    bbox = tuple(args.bbox)
    query_meta = {
        "bbox": list(bbox),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "polarization": args.polarization,
        "orbit_direction": args.orbit_direction,
        "limit": args.limit,
        "source": args.source,
    }

    try:
        resp = stac_search(
            bbox=bbox, start_date=args.start_date, end_date=args.end_date,
            polarization=args.polarization, orbit_direction=args.orbit_direction,
            limit=args.limit, source=args.source,
        )
    except requests.HTTPError as e:
        print(f"ERROR: STAC search failed: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"  body: {e.response.text[:300]}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"ERROR: network error during STAC search: {e}", file=sys.stderr)
        return 1

    features = resp.get("features", [])
    query_meta["returned"] = len(features)

    if args.output_format == "json":
        print(format_results_json(query_meta, features))
    else:
        if not _quiet():
            print("[sentinel1-download] searching Planetary Computer STAC ..."
                  if args.source == "pc" else "[sentinel1-download] searching AWS Earth Search STAC ...",
                  file=sys.stderr)
            print(f"[sentinel1-download] bbox: [{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]", file=sys.stderr)
            print(f"[sentinel1-download] date: {args.start_date} → {args.end_date}", file=sys.stderr)
        print(format_results_text(query_meta, features))

    if not args.download:
        if not _quiet():
            print("\n[sentinel1-download] search done. Add --download to fetch.", file=sys.stderr)
        return 0

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    if not features:
        if not _quiet():
            print("[sentinel1-download] no scenes to download.", file=sys.stderr)
        return 0

    if not _quiet():
        print(f"\n[sentinel1-download] downloading {len(features)} scene(s) to {output_dir}", file=sys.stderr)

    overall_ok = True
    total_bytes = 0
    t0 = time.time()
    for i, item in enumerate(features, 1):
        if not _quiet():
            print(f"\n[{i}/{len(features)}]", file=sys.stderr)
        r = download_scene(item, bands=args.bands, output_dir=output_dir,
                           source=args.source, timeout=args.download_timeout,
                           show_progress=not args.no_progress)
        total_bytes += r["total_bytes"]
        if not r["ok"]:
            overall_ok = False
    elapsed = time.time() - t0
    if not _quiet():
        print(f"\n[sentinel1-download] done in {elapsed:.0f}s — "
              f"downloaded {_human_bytes(total_bytes)} across {len(features)} scene(s)", file=sys.stderr)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
