"""sorftime 多维度品牌选品 scraper.

选品牌 page (/home/choosebrand) 「多维度品牌选品」tab 默认加载 20 个品牌
排行到 `_data.board.items`（匿名父 VM depth 6），无需选类目。

This scraper:
  1. Navigates + sets site via localStorage
  2. Reads `board.items` from the anonymous parent VM
  3. Extracts: Brand, ProductCount, SellerCount, TopProductCount,
     TopSellerCount, TopSaleCount, TopSaleVolume, TopAvgPrice,
     TopAvgCommentCount, MonthProductCount, MonthSaleCount,
     TopProductMaxNodeId, TopSaleMaxNodeId, TopMinSaleTime
  4. Writes one row per brand per station
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
    ensure_brand_page, find_board_vm, read_state, read_board_items, write_csv,
)


BRAND_FIELDS = [
    "station", "station_name", "site", "rank",
    "brand", "id", "brand_url",
    "product_count", "seller_count",
    "top_product_count", "top_seller_count",
    "top_product_count_rate", "top_sale_count", "top_sale_volume",
    "top_avg_price", "top_avg_comment_count",
    "top_min_sale_time",
    "top_product_max_node", "top_sale_max_node",
    "month_product_count", "month_sale_count",
    "month_avg_price", "month_avg_sale_count",
    "top_asins",
]


def extract_row(item, station, station_name, site, rank):
    """Flatten one brand item into a CSV row."""
    img_list = item.get("ImageList") or item.get("RowImage") or []
    asins = [str(x.get("ASIN") or "") for x in img_list if isinstance(x, dict)][:5]
    top_asins = "|".join(a for a in asins if a)

    return {
        "station": station,
        "station_name": station_name,
        "site": site,
        "rank": rank,
        "brand": item.get("Brand") or "",
        "id": item.get("Id") or "",
        "brand_url": item.get("BrandUrl") or "",
        "product_count": item.get("ProductCount") or "",
        "seller_count": item.get("SellerCount") or "",
        "top_product_count": item.get("TopProductCount") or "",
        "top_seller_count": item.get("TopSellerCount") or "",
        "top_product_count_rate": item.get("TopProductCountRate") or "",
        "top_sale_count": item.get("TopSaleCount") or "",
        "top_sale_volume": item.get("TopSaleVolume") or "",
        "top_avg_price": item.get("TopAvgPrice") or "",
        "top_avg_comment_count": item.get("TopAvgCommentCount") or "",
        "top_min_sale_time": item.get("TopMinSaleTime") or "",
        "top_product_max_node": item.get("TopProductMaxNodeId") or "",
        "top_sale_max_node": item.get("TopSaleMaxNodeId") or "",
        "month_product_count": item.get("MonthProductCount") or "",
        "month_sale_count": item.get("MonthSaleCount") or "",
        "month_avg_price": item.get("MonthAvgPrice") or "",
        "month_avg_sale_count": item.get("MonthAvgSaleCount") or "",
        "top_asins": top_asins,
    }


def fetch_station(station_code, session=None, sleep_after=12.0):
    """Fetch brand board for one station.

    Each station gets its own session+tab to avoid Vue data staleness
    when reusing the same tab across many site switches.
    """
    if session is None:
        session = f"brand_{station_code.lower()}"

    site_id = next((k for k, v in SITE_TO_CODE.items() if v == station_code), None)
    if site_id is None:
        print(f"[skip] unknown station {station_code}", file=sys.stderr)
        return [], {"station": station_code, "error": "unknown_station"}

    print(f"[{station_code}] navigate + reload (site={site_id}, session={session})...",
          file=sys.stderr)
    ensure_brand_page(session=session, site=site_id, sleep_after=sleep_after)

    vm_check = find_board_vm(session)
    if not (isinstance(vm_check, dict) and vm_check.get("ok")):
        print(f"[{station_code}] board VM not found", file=sys.stderr)
        return [], {"station": station_code, "vm_found": False}

    state = read_state(session)
    if not isinstance(state, dict) or state.get("_error"):
        print(f"[{station_code}] state read failed: {state}", file=sys.stderr)
        return [], {"station": station_code, "vm_found": True, "state_err": True}

    items_count = state.get("board_items_len", 0) or 0
    if items_count == 0:
        # Wait longer for slow data loads
        time.sleep(8)
        state = read_state(session)
        items_count = state.get("board_items_len", 0) or 0

    print(f"[{station_code}] board_items={items_count} | first="
          f"{state.get('first_brand', '?')!r}", file=sys.stderr)

    items = read_board_items(session, max_items=100)
    if not items:
        print(f"[{station_code}] no board items", file=sys.stderr)
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
    print(f"[{station_code}] extracted {len(rows)} brands", file=sys.stderr)
    return rows, {
        "station": station_code,
        "station_name": STATION_NAMES.get(station_code, ""),
        "site": site_id,
        "vm_found": True,
        "data_count": len(rows),
        "first_brand": state.get("first_brand", ""),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--station", required=True,
                   help="Comma-separated site codes (US,JP,GB,...)")
    p.add_argument("--out", required=True, help="CSV output path (data rows)")
    p.add_argument("--summary", default=None, help="Optional summary CSV path")
    p.add_argument("--sleep", type=float, default=12.0,
                   help="Page init sleep (s) — brand page is heavy")
    p.add_argument("--session", default="sorftime-brand",
                   help="Kimi WebBridge session ID (default: sorftime-brand). "
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
            session = f"brand_{st.lower()}"
            rows, summary = fetch_station(st, session=session, sleep_after=args.sleep)
            all_rows.extend(rows)
            summaries.append(summary)
        except Exception as e:
            print(f"[{st}] failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            summaries.append({"station": st, "error": str(e)})

    write_csv(args.out, all_rows, BRAND_FIELDS)
    print(f"wrote {len(all_rows)} brand rows → {args.out}", file=sys.stderr)

    if args.summary:
        summary_fields = ["station", "station_name", "site", "vm_found",
                          "data_count", "first_brand", "error"]
        write_csv(args.summary, summaries, summary_fields)
        print(f"wrote {len(summaries)} summaries → {args.summary}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
