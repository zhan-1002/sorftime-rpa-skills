---
name: sorftime-market
description: Pull rich Amazon market-category data from sorftime 选市场 (/home/choosemarketblock) across 14 marketplaces. DOM-driven skill — reads `marketBoard.items` (auto-populated on page load, 20 categories per station × 251 fields per category). Fields cover pricing, sales, brand/seller density, AMZ FBA/EBC/FBM, Chinese seller %, tariffs, profit margin, CPC, new product trends, and more. Supports 4 sub-modes (multi / buyer / new / lowprice) for up to 80 categories per station.
---

# sorftime-market

Fetch **rich market-category data** from **sorftime 选市场** (`/home/choosemarketblock`).

The page auto-populates `marketBoard.items` on initial load with **20 top categories per station**, each carrying **251 fields** (246 raw sorftime fields + 5 metadata). This is the same data shown in the dashboard's "榜单" tab.

**Why this skill works now**: the `marketBoard` slice populates reliably without any UI interaction or `initData(nodeId)` call. Earlier attempts only used the trend chart (`marketTrendChartData`, 20 items per trigger) because other slices needed sub-tab clicks. The `marketBoard` slice is the dashboard's "top 20 categories" table which auto-loads on page mount.

**4 sub-modes** (multi / buyer / new / lowprice) each fetch a different top-20 list. Combining all 4 gives 80 categories per station.

## Quick start

```bash
# Single station, default sub_mode (multi)
python scripts/fetch_markets.py --station US --out data/us_markets.csv

# All 14 stations, multi mode only (fastest: ~15 min)
python scripts/fetch_all14.py --stations US,GB,DE,FR,IN,CA,JP,ES,IT,MX,AE,AU,BR,SA \
    --out data/markets_14sites.csv

# All 14 stations × 4 sub-modes (slowest: ~60 min, 80 cats/station)
python scripts/fetch_all14.py --all-4modes --out data/markets_14sites_4modes.csv

# US only with all 4 sub-modes (good test)
python scripts/fetch_all14.py --stations US --us-only-4modes \
    --out data/market_us_4modes.csv

# Retry stations that returned 0 items (IN, CA, MX, AU, SA common)
python scripts/fetch_retry.py

# Generate comprehensive 8-section report
python scripts/analyze.py --markets data/markets_14sites.csv \
    --out-md reports/markets_14sites.md
```

## Requirements

- **Kimi WebBridge daemon** running and extension connected (`~/.kimi-webbridge/bin/kimi-webbridge status`)
- **sorftime login** in the same browser profile
- Python 3.10+ (no third-party packages)

## What you get

Each CSV row = one category in the top-20 board, with **251 fields**:

| Field group | Key fields |
|---|---|
| **Identity** | `Name`, `NodeId`, `Number`, `Url`, `Id`, `IsCollet` |
| **Pricing** | `AveragePrice`, `AveragePriceHB`, `MarketMedianPrice`, `MarketPriceHigh`, `MarketPriceLow`, `MonthAvgPrice`, `LowPriceProductCount`, `PriceChangeRate`, `PriceCostRate`, `TypeAvgPriceCost` |
| **Volume** | `SaleCount`, `SaleCountAvg`, `SaleCountPrev`, `SaleCountPrev{Three,Five,Ten,Twenty}`, `SalesVolume`, `YearSaleCount`, `YearSaleVolume` |
| **Brand / Seller** | `BrandCount`, `SolderNumberCN`, `SolderRateCN`, `SolderSaleCountRateCN`, `SolderNumberCount`, `AveBrandRevenue`, `AveSellerRevenue`, `BrandPrev{,Three,Five,Ten,Twenty}` |
| **Time windows (1/2/3/6 mo)** | `XMonthProductCount{,Share,WithOutVariant}`, `XMonthCommentCount{,WithOutVariant}`, `XMonthScoreCount{,WithOutVariant}`, `XMonthHCCount{,WithOutVariant}`, `XMonthLCCount{,WithOutVariant}` |
| **Listing tiers** | `XCommentCountListing`, `XCommentCountShare` (for 2/5/10/20/30/50/100/400) |
| **AMZ logistics** | `AmzFbaRate`, `AmzFbaCount`, `AmzFbaSaleCount`, `AmzFbaSaleVolume`, `EbcRate`, `FBMCount`, `FBMCountShare`, `OneMonthAmzFbaSaleVolume`, `SixMonthAmzFbaSaleVolume`, `ThreeMonthAmzFbaSaleVolume` |
| **Fulfillment quality** | `ListingComplete`, `OutStockProductCount`, `SevenOutStockProductCount`, `ThirtyOutStockProductCount`, `SevenTightInventoryProductCount`, `TightInventoryProductCount`, `LowPriceValueNum` |
| **New product** | `NewProductCount`, `NewSalesVolumeRate`, `NewAvgPrice`, `NewAvgSalecount`, `NewAvgSalesvolume`, `NewProductComment`, `NewProductSaleCount`, `NewProductScore`, `NewAsinCount`, `MonthExpectAddRateLast/Next/Range/Three` |
| **Profit / Tariff** | `GrossProfitMargin`, `TariffValueNum`, `TariffSalePrice`, `TariffAvgPriceCost`, `CPCAvgPrice`, `AmzProfitRate`, `TemuProfitRate` |
| **Quality / risk** | `CompeteCount`, `AvgCompeteCount`, `AvgBsrAsinChangeRate`, `AvgScore`, `AvgVolume`, `AvgWeight`, `AvgZhl`, `AvgProfit`, `AvgSaleCount`, `AvgVariantCount`, `AvgOtherSeller`, `NoBrandRate`, `NoBrandSaleRate`, `ThrowGoodsRate`, `ReturnRatio`, `HavingVariantRate`, `CyclicalMarket` |
| **Reviews** | `OneMonthHCCount`, `OneMonthLCCount`, `HCCount`, `LCCount`, `NoScoreProductCount`, `ReviewAddRateBad/Good`, `ReviewRateBad/Good`, `CommentAddRate`, `CommentSaleRate` |
| **Lifecycle** | `FirstShelvesTime`, `SaleTimeAvgDay`, `SaleTimeNewest`, `SaleTimeOldest`, `BusySeason`, `BusySeasonStr`, `RegTrademark` |
| **Logistics** | `AirFirstVessel`, `KdFirstVessel`, `SeaFirstVessel`, `InternationalRate` |
| **Amazon programs** | `AmazonHaul`, `VideoRate`, `AddRate`, `AddRateAvg`, `AddRateYearAvg` |
| **Category rank** | `SorfTimeNumber`, `LowPriceValueNumRank`, `LowPriceValueNumTime` |
| **Trend (price/sale) ratios** | `Ratiooffirsttofifty`, `Ratiooffirsttofive`, `Ratiooffirsttolast`, `Ratiooffirsttoten`, `Ratiooffirsttotwenty` |
| **Stability** | `AsinChangeRate`, `SaleCountChangeRate`, `PriceSaleChangeRate`, `ReviewStayRate`, `RatingStayMonth`, `RatingMonth` |

Plus 5 metadata columns: `station`, `station_name`, `site_id`, `sub_mode`, `sub_mode_id`.

## CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--station` / `--stations` | required | Comma-separated site codes |
| `--out` | required | CSV output path |
| `--sub-modes` / `--us-only-4modes` / `--all-4modes` | `multi` | multi/buyer/new/lowprice (1/2/3/4) |
| `--sleep` | 12.0s | Wait after navigate/switch |

## Gotchas

1. **Per-station session isolation**: each site uses a unique session (`market_us`, `market_de`, etc.) with its own tab. Reusing a tab across sites causes Vue state contamination (per lessons-learned).

2. **Pro upgrade dialog**: must be hidden via `hide_pro_dialog()` (removes `.el-overlay` / `.v-modal`) before reading VM state.

3. **Page init 12-15s**: Vue mount + axios + jQuery + databoard POST takes time. Don't reduce `--sleep` below 10s.

4. **5 stations often return 0 items**: IN, CA, MX, AU, SA commonly show `itemsLen: 0` (likely geo/region restrictions on free tier). Use `fetch_retry.py` with longer sleeps (22s+) for these.

5. **localStorage site switching**: `localStorage.setItem("site", N)` + `location.reload()` (in that order). URL `?i=` param does NOT work.

6. **4 sub-modes are independent** boards: switching `vm.marketType` between 1/2/3/4 swaps the items array. Combine all 4 for max coverage (80 cats/station).

7. **No pagination**: `pageIndex=2..5` is implemented in the VM but doesn't actually change items (verified). To get more categories, switch sub-modes or click a different category node.

8. **20 items default**: free tier shows top 20. PRO may show more, but not via API.

## Architecture note

| | market | bestseller | product |
|---|---|---|---|
| Trigger | auto on page load | `vm.treeItemClick(node)` | auto on page load |
| Per fetch | 20 cats × 251 fields | 100 ASINs (full TOP100) | ~20 unmasked ASINs |
| Granularity | Category | ASIN | ASIN |
| Data surface | Full (251 fields) | Full | Partial (ASIN-mask) |
| 14-site coverage | 9/14 (free) | 14/14 | 14/14 |

For category-level analysis use `sorftime-market`. For per-ASIN product analysis use `sorftime-bestseller` or `sorftime-product`.

## See also

- `scripts/fetch_markets.py` — single-station, multi-sub-mode scraper
- `scripts/fetch_all14.py` — all 14 stations, configurable sub-modes
- `scripts/fetch_retry.py` — retry 5 common-fail stations with longer waits
- `scripts/analyze.py` — 8-section comprehensive report generator
- `scripts/common.py` — shared VM traversal, dialog hiding, helpers
