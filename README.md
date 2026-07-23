# Sentinel-1 SAR Downloader · Sentinel-1 SAR 影像下载器

> 通过 STAC 搜索和下载 **Sentinel-1 SAR (C 波段)** GRD 影像。
> 默认后端是 **Microsoft Planetary Computer**（公开数据，无需账号）。
> MIT-0 开源。

[English](#quickstart) | 中文

## 为什么做这个

做 SAR 遥感时常需要 Sentinel-1 数据来监测地表形变、洪水、船只、海冰等。
ESA Copernicus 数据免费开放，但手动下载流程繁琐。本 skill 通过 STAC API
一键搜索和下载，沿用 Landsat Downloader 的架构。

## Quickstart

```bash
# 1) Install dependency
pip install 'requests>=2.28.0'

# 2) Search Sentinel-1 SAR imagery (search only)
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31

# 3) Filter by polarization + download
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --polarization vv+vh \
    --download \
    --output-dir ./data
```

## 快速开始 / Quickstart

```bash
# 安装依赖
pip install 'requests>=2.28.0'

# 搜索 Sentinel-1 SAR 影像（仅查询）
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31

# 限制极化方式 + 下载
python sentinel1-download.py \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --polarization vv+vh \
    --download \
    --output-dir ./data
```

## 数据源 / Data Source

| 后端 | URL | 凭证 |
|---|---|---|
| **Planetary Computer**（默认） | `https://planetarycomputer.microsoft.com/api/stac/v1/` | 无 |
| AWS Earth Search | `https://earth-search.aws.element84.com/v1/` | 无 |

> **License** — Sentinel-1 数据由 ESA 持有，**免费开放**（Copernicus Open Data）。

## 支持的卫星 / Supported Satellites

| 卫星 | 发射 | 传感器 | 波段 | 分辨率 |
|---|---|---|---|---|
| **Sentinel-1A** | 2014-04-03 | C-SAR | C 波段 (5.4 GHz) | 10m (IW) |
| **Sentinel-1B** | 2016-04-25 | C-SAR | C 波段 (5.4 GHz) | 10m (IW) |

## 参数一览 / Parameters

| 参数 | 说明 | 必填 |
|---|---|---|
| `--bbox` | 地理范围 `[minLon minLat maxLon maxLat]` | ✅ |
| `--start-date` | 开始日期 `YYYY-MM-DD` | ✅ |
| `--end-date` | 结束日期 `YYYY-MM-DD` | ✅ |
| `--polarization` | `vv` / `vh` / `vv+vh` / `all` | ❌ |
| `--orbit-direction` | `ascending` / `descending` / `both` | ❌ |
| `--limit` | 限制返回条目数 | ❌ |
| `--bands` | 下载的资产列表（默认 `vh vv`） | ❌ |
| `--download` | 触发实际下载 | ❌ |
| `--output-dir` | 下载目录（默认 `./sentinel1_data`） | ❌ |
| `--output-format` | `text` / `json` | ❌ |

## 默认下载波段 / Default Bands

| 资产 | 含义 | 说明 |
|---|---|---|
| `vh` | VH 极化 | 交叉极化，对植被/土壤敏感 |
| `vv` | VV 极化 | 共极化，对水面/建筑敏感 |

## License

MIT-0（详见 [LICENSE](./LICENSE)）。
Sentinel-1 数据 © ESA Copernicus，免费开放。
