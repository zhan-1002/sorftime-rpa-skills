"""sorftime 关键词趋势选品 scraper — 读取 side-Keyword VM 的 listData.

选关键词 page (/home/choosekeyword) 默认模式（最新热搜词）会加载
20 条热门关键词到 `keywordData.listData`，**无需用户选类目**。

This scraper:
  1. Navigates + sets site via localStorage
  2. Reads `keywordData.listData` from side-Keyword VM
  3. Extracts key fields: name, avg price/score/review, brand count,
     competitor count, growth rates, CPC, busy season, etc.
  4. Writes one row per keyword per station
"""
import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    SITE_TO_CODE, STATION_NAMES,
    ensure_keyword_page, find_side_keyword_vm,
    read_state, read_listdata, write_csv,
)


KEYWORD_FIELDS = [
    "station", "station_name", "site", "rank",
    "name", "id",
    "avg_price", "avg_score", "avg_review", "avg_comment_count",
    "brand_count", "competitor_count", "coverage_count",
    "buy_rate", "cpc_storm", "cpc_low", "cpc_high",
    "growth_3m", "growth_6m", "growth_12m",
    "buy_monopoly",
    "fall_type_str",
    "busy_season", "cyclical_market",
    "extend_word_count",
]


def extract_row(item, station, station_name, site, rank):
    """Flatten one keyword item into a CSV row."""
    return {
        "station": station,
        "station_name": station_name,
        "site": site,
        "rank": rank,
        "name": item.get("Name") or item.get("name") or "",
        "id": item.get("Id") or item.get("id") or "",
        "avg_price": item.get("AveragePrice") or item.get("AvgPrice") or "",
        "avg_score": item.get("AvgScore") or "",
        "avg_review": item.get("AvgReview") or "",
        "avg_comment_count": item.get("AvgCommentCount") or item.get("AvgComentCount") or "",
        "brand_count": item.get("BrandCount") or "",
        "competitor_count": item.get("CompetitorCount") or "",
        "coverage_count": item.get("CoverageCount") or "",
        "buy_rate": item.get("BuyRate") or "",
        "cpc_storm": item.get("CpcStorm") or "",
        "cpc_low": item.get("CpcLow") or "",
        "cpc_high": item.get("CpcHigh") or "",
        "growth_3m": item.get("GrowthRateThree") or "",
        "growth_6m": item.get("GrowthRateSix") or "",
        "growth_12m": item.get("GrowthRateTwelve") or "",
        "buy_monopoly": item.get("BuyMonopoly") or "",
        "fall_type_str": item.get("FallTypeStr") or "",
        "busy_season": item.get("BusySeason") or "",
        "cyclical_market": item.get("CyclicalMarket") or "",
        "extend_word_count": item.get("ExtendWordCount") or "",
    }


def fetch_station(station_code, sleep_after=12.0):
    """Fetch keyword trends for one station.

    Returns (rows, summary_dict). rows is a list of dicts (one per
    keyword), summary_dict is a one-row status dict.
    """
    site_id = next((k for k, v in SITE_TO_CODE.items() if v == station_code), None)
    if site_id is None:
        print(f"[skip] unknown station {station_code}", file=sys.stderr)
        return [], {"station": station_code, "error": "unknown_station"}

    print(f"[{station_code}] navigate + reload (site={site_id})...",
          file=sys.stderr)
    ensure_keyword_page(session="sorftime-keyword", site=site_id,
                        sleep_after=sleep_after)

    vm_check = find_side_keyword_vm("sorftime-keyword")
    if not (isinstance(vm_check, dict) and vm_check.get("ok")):
        print(f"[{station_code}] side-Keyword VM not found", file=sys.stderr)
        return [], {"station": station_code, "vm_found": False}

    state = read_state("sorftime-keyword")
    if not isinstance(state, dict) or state.get("_error"):
        print(f"[{station_code}] state read failed: {state}", file=sys.stderr)
        return [], {"station": station_code, "vm_found": True, "state_err": True}

    listdata_len = state.get("kw_listdata_len", 0) or 0
    print(f"[{station_code}] kw_listdata={listdata_len} | kw_list="
          f"{state.get('kw_list_len', 0)} | table_data="
          f"{state.get('table_data_len', 0)} | total="
          f"{state.get('table_total', 0)}", file=sys.stderr)

    items = read_listdata("sorftime-keyword", max_items=200)
    if not items:
        print(f"[{station_code}] no listData", file=sys.stderr)
        return [], {
            "station": station_code,
            "station_name": STATION_NAMES.get(station_code, ""),
            "site": site_id,
            "vm_found": True,
            "data_count": 0,
            "screen_select": state.get("screen_select", ""),
        }

    rows = []
    for i, item in enumerate(items, 1):
        rows.append(extract_row(item, station_code,
                                STATION_NAMES.get(station_code, ""),
                                site_id, i))
    print(f"[{station_code}] extracted {len(rows)} keywords", file=sys.stderr)
    return rows, {
        "station": station_code,
        "station_name": STATION_NAMES.get(station_code, ""),
        "site": site_id,
        "vm_found": True,
        "data_count": len(rows),
        "screen_select": state.get("screen_select", ""),
        "kw_listdata_len": listdata_len,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--station", required=True,
                   help="Comma-separated site codes (US,JP,GB,...)")
    p.add_argument("--out", required=True,
                   help="CSV output path (one row per keyword)")
    p.add_argument("--summary", default=None,
                   help="Optional summary CSV path")
    p.add_argument("--sleep", type=float, default=12.0,
                   help="Page init sleep (s) — keyword page is slow to load")
    args = p.parse_args()

    stations = [s.strip().upper() for s in args.station.split(",") if s.strip()]
    if not stations:
        print("error: --station required", file=sys.stderr)
        sys.exit(2)

    all_rows = []
    summaries = []
    for st in stations:
        try:
            rows, summary = fetch_station(st, args.sleep)
            all_rows.extend(rows)
            summaries.append(summary)
        except Exception as e:
            print(f"[{st}] failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            summaries.append({"station": st, "error": str(e)})

    write_csv(args.out, all_rows, KEYWORD_FIELDS)
    print(f"wrote {len(all_rows)} keyword rows → {args.out}", file=sys.stderr)

    if args.summary:
        summary_fields = ["station", "station_name", "site", "vm_found",
                          "data_count", "kw_listdata_len", "screen_select",
                          "error"]
        write_csv(args.summary, summaries, summary_fields)
        print(f"wrote {len(summaries)} summaries → {args.summary}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
