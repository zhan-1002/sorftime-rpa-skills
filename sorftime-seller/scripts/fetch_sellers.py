"""sorftime 多维度卖家选品 scraper.

选卖家 page (/home/chooseseller) 「多维度卖家选品」tab 默认加载 20 个卖家
排行到 `_data.sellerBoard.items`（匿名父 VM），无需选类目。

This scraper:
  1. Navigates + sets site via localStorage
  2. Hides the Pro upgrade dialog overlay (blocks page)
  3. Reads `sellerBoard.items` from the anonymous parent VM
  4. Extracts: Name, EnterpriseName, SolderId, SolderUrl, BusinessAddress,
     SellerNationalityOrRegion, SellerOnlineTime, FeedbackCount, ProductCount,
     AllBrandCount, BSR* group (50+ fields)
  5. Writes one row per seller per station
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    SITE_TO_CODE, STATION_NAMES,
    ensure_seller_page, find_seller_board_vm, read_state, read_seller_items, write_csv,
)


SELLER_FIELDS = [
    "station", "station_name", "site", "rank",
    "name", "id", "solder_id", "solder_url",
    "enterprise_name", "nationality", "online_time", "feedback_count",
    "business_address", "product_count", "all_brand_count",
    "compare_last_month_product_count",
    "bsr_product_count", "bsr_brand_count",
    "bsr_estimated_monthly_sale", "bsr_estimated_monthly_sale_amount",
    "bsr_operating_category_count", "bsr_operating_subcategory_count",
    "bsr_max_sale_subcategory", "bsr_max_product_source_subcategory",
    "bsr_fba_count", "bsr_fbm_count", "bsr_amazon_count", "bsr_no_brand_count",
    "bsr_avg_price", "bsr_avg_review", "bsr_variant_count",
    "bsr_avg_variant_count", "bsr_hot_search_word_home_product_count",
    "bsr_head_product_sale_rate", "bsr_earliest_product_launch_time",
    "bsr_new_product_count", "bsr_new_avg_price", "bsr_new_avg_rating",
    "bsr_new_avg_review", "bsr_new_max_sale", "bsr_new_avg_sale",
    "bsr_new_min_sale", "bsr_new_fbm_count", "bsr_new_fbm_product_rate",
    "bsr_new_fbm_sale_rate", "bsr_new_brand_count",
    "no_brand_ratio", "no_brand_sale_count", "no_brand_sale_ratio",
    "product_count_ratio", "sale_output",
    "is_collect", "top_asins",
]


def extract_row(item, station, station_name, site, rank):
    """Flatten one seller item into a CSV row."""
    img_data = item.get("ImageData") or "[]"
    asins = []
    try:
        imgs = json.loads(img_data) if isinstance(img_data, str) else (img_data or [])
        asins = [str(x.get("ASIN") or "") for x in imgs if isinstance(x, dict)][:5]
    except Exception:
        asins = []
    top_asins = "|".join(a for a in asins if a)

    return {
        "station": station,
        "station_name": station_name,
        "site": site,
        "rank": rank,
        "name": item.get("Name") or "",
        "id": item.get("Id") or "",
        "solder_id": item.get("SolderId") or "",
        "solder_url": item.get("SolderUrl") or "",
        "enterprise_name": item.get("EnterpriseName") or "",
        "nationality": item.get("SellerNationalityOrRegion") or "",
        "online_time": item.get("SellerOnlineTime") or "",
        "feedback_count": item.get("FeedbackCount") or "",
        "business_address": (item.get("BusinessAddress") or "").replace("<br/>", " | "),
        "product_count": item.get("ProductCount") or "",
        "all_brand_count": item.get("AllBrandCount") or "",
        "compare_last_month_product_count": item.get("CompareLastMonthProductCount") or "",
        "bsr_product_count": item.get("BSRProductCount") or "",
        "bsr_brand_count": item.get("BSRBrandCount") or "",
        "bsr_estimated_monthly_sale": item.get("BSREstimatedMonthlySale") or "",
        "bsr_estimated_monthly_sale_amount": item.get("BSREstimatedMonthlySaleAmount") or "",
        "bsr_operating_category_count": item.get("BSROperatingCategoryCount") or "",
        "bsr_operating_subcategory_count": item.get("BSROperatingSUBCategoryCount") or "",
        "bsr_max_sale_subcategory": item.get("BSRMaxSaleSUBCategory") or "",
        "bsr_max_product_source_subcategory": item.get("BSRMaxProductSourceSUBCategoriy") or "",
        "bsr_fba_count": item.get("BSRFBACount") or "",
        "bsr_fbm_count": item.get("BSRFBMCount") or "",
        "bsr_amazon_count": item.get("BSRACount") or "",
        "bsr_no_brand_count": item.get("BSRNoBrandCount") or "",
        "bsr_avg_price": item.get("BSRAvgPrice") or "",
        "bsr_avg_review": item.get("BSRAvgReview") or "",
        "bsr_variant_count": item.get("BSRVariantCount") or "",
        "bsr_avg_variant_count": item.get("BSRAvgVariantCount") or "",
        "bsr_hot_search_word_home_product_count": item.get("BSRHotSearchWordHomeProductCount") or "",
        "bsr_head_product_sale_rate": item.get("BSRHeadProductSaleRate") or "",
        "bsr_earliest_product_launch_time": item.get("BSREarliestProductLaunchTime") or "",
        "bsr_new_product_count": item.get("BSRNewProductCount") or "",
        "bsr_new_avg_price": item.get("BSRNewAvgPrice") or "",
        "bsr_new_avg_rating": item.get("BSRNewAvgRating") or "",
        "bsr_new_avg_review": item.get("BSRNewAvgReview") or "",
        "bsr_new_max_sale": item.get("BSRNewMaxSale") or "",
        "bsr_new_avg_sale": item.get("BSRNewAvgSale") or "",
        "bsr_new_min_sale": item.get("BSRNewMinSale") or "",
        "bsr_new_fbm_count": item.get("BSRNewFBMCount") or "",
        "bsr_new_fbm_product_rate": item.get("BSRNewFBMProductRate") or "",
        "bsr_new_fbm_sale_rate": item.get("BSRNewFBMSaleRate") or "",
        "bsr_new_brand_count": item.get("BSRNewBrandCount") or "",
        "no_brand_ratio": item.get("NoBrandRatio") or "",
        "no_brand_sale_count": item.get("NoBrandSaleCount") or "",
        "no_brand_sale_ratio": item.get("NoBrandSaleRatio") or "",
        "product_count_ratio": item.get("ProductCountRatio") or "",
        "sale_output": item.get("SaleOutput") or "",
        "is_collect": item.get("IsCollet") if item.get("IsCollet") is not None else "",
        "top_asins": top_asins,
    }


def fetch_station(station_code, session=None, sleep_after=12.0):
    """Fetch seller board for one station.

    Each station gets its own session+tab to avoid Vue data staleness
    when reusing the same tab across many site switches.
    """
    if session is None:
        session = f"seller_{station_code.lower()}"

    site_id = next((k for k, v in SITE_TO_CODE.items() if v == station_code), None)
    if site_id is None:
        print(f"[skip] unknown station {station_code}", file=sys.stderr)
        return [], {"station": station_code, "error": "unknown_station"}

    print(f"[{station_code}] navigate + reload (site={site_id}, session={session})...",
          file=sys.stderr)
    ensure_seller_page(session=session, site=site_id, sleep_after=sleep_after)

    vm_check = find_seller_board_vm(session)
    if not (isinstance(vm_check, dict) and vm_check.get("ok")):
        print(f"[{station_code}] sellerBoard VM not found", file=sys.stderr)
        return [], {"station": station_code, "vm_found": False}

    state = read_state(session)
    if not isinstance(state, dict) or state.get("_error"):
        print(f"[{station_code}] state read failed: {state}", file=sys.stderr)
        return [], {"station": station_code, "vm_found": True, "state_err": True}

    items_count = state.get("seller_items_len", 0) or 0
    if items_count == 0:
        time.sleep(8)
        state = read_state(session)
        items_count = state.get("seller_items_len", 0) or 0

    print(f"[{station_code}] seller_items={items_count} | first="
          f"{state.get('first_seller', '?')!r}", file=sys.stderr)

    items = read_seller_items(session, max_items=100)
    if not items:
        print(f"[{station_code}] no seller items", file=sys.stderr)
        return [], {
            "station": station_code,
            "station_name": STATION_NAMES.get(station_code, ""),
            "site": site_id,
            "vm_found": True,
            "data_count": 0,
        }

    rows = []
    for i, item in enumerate(items, 1):
        rows.append(extract_row(item, station_code,
                                STATION_NAMES.get(station_code, ""),
                                site_id, i))
    print(f"[{station_code}] extracted {len(rows)} sellers", file=sys.stderr)
    return rows, {
        "station": station_code,
        "station_name": STATION_NAMES.get(station_code, ""),
        "site": site_id,
        "vm_found": True,
        "data_count": len(rows),
        "first_seller": state.get("first_seller", ""),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--station", required=True,
                   help="Comma-separated site codes (US,JP,GB,...)")
    p.add_argument("--out", required=True, help="CSV output path (data rows)")
    p.add_argument("--summary", default=None, help="Optional summary CSV path")
    p.add_argument("--sleep", type=float, default=14.0,
                   help="Page init sleep (s) — seller page is heavy")
    p.add_argument("--session", default="sorftime-seller",
                   help="Kimi WebBridge session ID (default: sorftime-seller). "
                        "Use the same session across stations to reuse one tab.")
    args = p.parse_args()

    stations = [s.strip().upper() for s in args.station.split(",") if s.strip()]
    if not stations:
        print("error: --station required", file=sys.stderr)
        sys.exit(2)

    all_rows = []
    summaries = []
    for st in stations:
        try:
            # Per-station session ensures fresh Vue state each iteration
            session = f"seller_{st.lower()}"
            rows, summary = fetch_station(st, session=session, sleep_after=args.sleep)
            all_rows.extend(rows)
            summaries.append(summary)
        except Exception as e:
            print(f"[{st}] failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            summaries.append({"station": st, "error": str(e)})

    write_csv(args.out, all_rows, SELLER_FIELDS)
    print(f"wrote {len(all_rows)} seller rows → {args.out}", file=sys.stderr)

    if args.summary:
        summary_fields = ["station", "station_name", "site", "vm_found",
                          "data_count", "first_seller", "error"]
        write_csv(args.summary, summaries, summary_fields)
        print(f"wrote {len(summaries)} summaries → {args.summary}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
