---
name: sorftime-keyword
description: Scrape sorftime 关键词趋势选品 (/home/choosekeyword) page across 14 Amazon marketplaces. DOM-driven skill that reads 20 default hot keywords from the keywordData.listData Vue VM field (no category selection needed). Outputs one CSV row per keyword with avg price, score, review, growth rates, CPC, brand/competitor counts, etc.
---

# sorftime-keyword

Scrape **Amazon hot keywords** from **sorftime 关键词趋势选品** (`/home/choosekeyword`).

## Breakthrough (2026-07-04)

**The page DOES populate data by default** — no category selection required. The 20 hot keywords in `keywordData.listData` (note: lowercase `l`) load on page navigation. The previous "filter-gated" assumption was wrong because:

1. The data lives in an **anonymous parent VM at depth 6**, not in the `side-Keyword` component (which is at depth 3 with empty `List`/`table`).
2. The default filter shows the latest week's hot keywords for that site.

## Quick start

```bash
# Single station
python scripts/fetch_keywords.py --station US \
    --out data/keyword_us.csv

# Multi-station
python scripts/fetch_keywords.py --station US,JP,GB \
    --out data/keywords_3sites.csv \
    --summary data/keywords_3sites_summary.csv

# Generate analyze report
python scripts/analyze.py --keywords data/keywords_3sites.csv \
    --out-md reports/keyword_analysis.md
```

## Requirements

- **Kimi WebBridge daemon** running and extension connected
- **sorftime login** in the same browser profile
- Python 3.10+ (no third-party packages)

## What you get

A CSV with **one row per keyword** (20 rows per station by default).

| Field | Meaning |
|---|---|
| `station` / `station_name` | Amazon marketplace code + 中文 |
| `site` | Numeric site code (1=US, 7=JP, ...) |
| `rank` | Position in the listData array (1-20) |
| `name` | Keyword name (e.g. "kindle", "冷蔵庫", "mini fridge") |
| `id` | Sorftime internal keyword id |
| `avg_price` | Average product price for this keyword |
| `avg_score` | Average review score |
| `avg_review` | Average review count |
| `avg_comment_count` | Average comment count (alias field) |
| `brand_count` | Number of brands competing |
| `competitor_count` | Number of competing products |
| `coverage_count` | Coverage ratio |
| `buy_rate` | Buy box rate % |
| `cpc_storm` / `cpc_low` / `cpc_high` | Sponsored product CPC |
| `growth_3m` / `growth_6m` / `growth_12m` | Growth rate % |
| `buy_monopoly` | Buy box monopoly % |
| `fall_type_str` | Search volume bucket ("200万+", "30万+", etc.) |
| `busy_season` | JSON array of busy months |
| `cyclical_market` | Cyclical market info |
| `extend_word_count` | Number of related keyword extensions |

Sample output (US site, top 5 by CPC):
```
rank,name,avg_price,avg_score,competitor_count,growth_3m,cpc_storm
1,kindle,92.97,4.32,112635,2.55,0.35
2,ipad,150.37,4.43,62657,-0.95,0.93
3,apple watch,93.22,4.38,38922,-0.92,0.62
4,airpods,81.23,4.35,15244,3.21,0.96
5,laptop,496.45,4.35,126377,-1.61,1.29
```

## CLI flags

| Flag | Notes |
|---|---|
| `--station` | Required. Comma-separated site codes (US,JP,GB,...) |
| `--out` | Required. CSV output path (data rows) |
| `--summary` | Optional. Per-station summary CSV |
| `--sleep` | Page init sleep (default 12.0s — keyword page is heavy) |

## How it works

1. **Navigate** to `/home/choosekeyword` in a new tab
2. **Set site** via `localStorage.setItem("site", "<code>")` + reload
3. **Wait 12s** for Vue to mount + 5-8s for default data load
4. **Walk Vue tree** looking for any VM with `keywordData.listData.length > 0`
5. **Extract 20 items** with key fields, write to CSV

The data comes from `keywordData.listData` (lowercase `l`), an array in an anonymous parent VM. The `side-Keyword` component (at depth 3) is misleading because it has its own empty `List` and `table.node.data`.

## Gotchas

1. **ListData, not List**: use `keywordData.listData` (lowercase l), not `keywordData.List` (capital L). The latter is the filter result, which is empty by default.

2. **Anonymous VM, not side-Keyword**: don't look for the data in `side-Keyword._data`. The data is in an anonymous parent VM at depth 6.

3. **Page init 12s**: the keyword page is heavier than bestseller; the 20 default keywords take ~5-8s to load after Vue mounts. Use `--sleep 12` to be safe.

4. **20 items per page**: the default `listData` has 20 entries. Pagination via `keywordData.page.pageIndex` may give more — not yet implemented in scraper.

5. **Encrypted API**: POST to `/api/keywordboard/querykeywordboard?site=NN` is AES-encrypted (body + response). We don't call this directly; we read post-decryption state from Vue.

6. **`sideMarket` VM also present**: keyword page has a `sideMarket` VM at depth ~5 with `categoryListData` (empty until category dialog opens). This is the same VM as the market page.

7. **14 sites (not 10)**: US/GB/DE/FR/IN/CA/JP/ES/IT/MX/AE/AU/BR/SA.

8. **localStorage site switching**: same as other skills — `localStorage["site"]` then reload.

## Architecture

| | keyword | bestseller | product |
|---|---|---|---|
| Auto-load on nav | **YES** (20 hot keywords) | YES (per category click) | YES (full list) |
| Per fetch | 20 keywords (default mode) | 100 ASINs | ~20 unmasked |
| Need UI flow | NO | NO | NO |
| Surface | Full (avg price, CPC, growth) | Full TOP100 | Partial (ASIN-mask) |

## See also

- `references/api_notes.md` — encrypted API + VM architecture
- `references/environment.md` — Windows/bash/jq/heredoc quirks
- `references/analysis_recipe.md` — analysis report template
- `scripts/fetch_keywords.py` — main scraper
- `scripts/analyze.py` — multi-station report generator
