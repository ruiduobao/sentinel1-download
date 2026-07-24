---
name: sentinel1-download
display_name: Sentinel-1 SAR Downloader
version: 0.1.0
author: rui.duobao
license: MIT-0
description: |
  通过 STAC 搜索和下载 Sentinel-1 SAR (C 波段) 影像。
  默认后端是 Microsoft Planetary Computer（公开数据，无需账号）。
  支持极化方式过滤（VV/VH/VV+VH / lowercase: vv/vh/vv+vh/all）、轨道方向过滤（ascending/descending）、
  安全的 .part 临时文件写入以及可视化下载进度。
  Use for Sentinel-1 SAR imagery search by bounding box / date / polarization,
  orbit direction, and large-file downloads with visual progress.

  English: STAC-based Sentinel-1 SAR (C-band) downloader.
  Data source: Microsoft Planetary Computer (Sentinel-1 GRD, public domain).
  Supports polarization filter, orbit direction filter, safe .part temp writes,
  and visual progress (speed + ETA).
runtime: python>=3.9
tags: [gis, remote-sensing, sar, sentinel-1, stac, planetary-computer, earth-observation, 下载]
---

# Sentinel-1 SAR Downloader | Sentinel-1 SAR 影像下载器

通过 STAC API 搜索并下载 Sentinel-1 SAR (C 波段) GRD 影像。
本 skill 沿用 [Landsat Downloader](https://clawhub.ai/skills/landsat-download)
的架构（STAC + 单文件 CLI + 可视化进度 + `.part` 安全写入），但适配
Sentinel-1 的元数据约定（极化方式、轨道方向、GRD/SLC 产品类型）。

## 依赖

```bash
pip install 'requests>=2.28.0'
```

## 数据源 / Source

| 后端 | URL | 凭证 | 默认 |
|---|---|---|---|
| **Planetary Computer**（推荐） | `https://planetarycomputer.microsoft.com/api/stac/v1/` | 无（公开） | ✅ |
| AWS Open Data（高级） | `https://earth-search.aws.element84.com/v1/` | 无（公开） | — |

> **License** — Sentinel-1 数据由 ESA 持有，**免费开放**（Copernicus Open Data）。
> 本 skill 抓取的是公开的 STAC 索引 + 公开的资产，不需要任何账号或凭证。

## 使用方法

### 搜索 Sentinel-1 SAR 影像（仅查询，不下载）

```bash
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31
```

### 限制极化方式（推荐 vv+vh 双极化，注意小写）

```bash
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --polarization vv+vh
```

### 搜索 + 下载

```bash
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --download \
    --output-dir ./data
```

### 仅 ascending 轨道

```bash
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --orbit-direction ascending
```

---

## 常用参数 / Parameters

| 参数 / Parameter | 说明 / Description | 必填 / Required |
|---|---|---|
| `--bbox` | 地理范围 `[minLon minLat maxLon maxLat]` | ✅ |
| `--start-date` | 开始日期 `YYYY-MM-DD` | ✅ |
| `--end-date` | 结束日期 `YYYY-MM-DD` | ✅ |
| `--polarization` | `vv` / `vh` / `vv+vh` / `all`（默认 `all`） | ❌ |
| `--orbit-direction` | `ascending` / `descending` / `both`（默认 `both`） | ❌ |
| `--limit` | 限制返回条目数（默认 10） | ❌ |
| `--bands` | 下载的资产列表（默认 `vh vv`） | ❌ |
| `--download` | 触发实际下载（默认仅查询） | ❌ |
| `--output-dir` | 下载目录（默认 `./sentinel1_data`） | ❌ |
| `--output-format` | `text`（默认）/ `json` | ❌ |
| `--source` | `pc`（默认）/ `aws` | ❌ |
| `--no-progress` | 关闭动态进度条 | ❌ |
| `--download-timeout` | 单个请求超时秒数（默认 600） | ❌ |
| `--quiet` | 关闭进度条 + 隐私告示 | ❌ |

## 支持的 Sentinel-1 卫星

| 卫星 | 发射 | 传感器 | 波段 | 分辨率 |
|---|---|---|---|---|
| **Sentinel-1A** | 2014-04-03 | C-SAR | C 波段 (5.4 GHz) | 10m (IW) |
| **Sentinel-1B** | 2016-04-25 | C-SAR | C 波段 (5.4 GHz) | 10m (IW) |

## 默认下载波段 / Default Bands

| 资产 / Asset | 含义 | 说明 |
|---|---|---|
| `vh` | VH 极化 | 交叉极化，对植被/土壤敏感 |
| `vv` | VV 极化 | 共极化，对水面/建筑敏感 |

## STAC 端点

| 用途 | URL |
|---|---|
| Planetary Computer 搜索 | `https://planetarycomputer.microsoft.com/api/stac/v1/search` |
| Element84 Earth Search（AWS） | `https://earth-search.aws.element84.com/v1/search` |

## Permissions

- **网络出口**：`https://planetarycomputer.microsoft.com`（默认后端）
- **环境变量**：`SENTINEL1_DOWNLOAD_USE_PROXY=1` 走系统代理
- **文件写入**：`--output-dir`（默认 `./sentinel1_data`）

## License

MIT-0 — 详见 [LICENSE](./LICENSE)。
Sentinel-1 数据 © ESA Copernicus，免费开放。
