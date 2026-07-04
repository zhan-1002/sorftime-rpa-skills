"""Fetch market data for all 14 sorftime stations.

For each station, navigates the market page, waits for marketBoard.items
to populate (20 categories per station), then writes all 246 fields per
category. US additionally gets 4 sub-modes (multi/buyer/new/lowprice).

Uses per-station session to avoid Vue state contamination between sites.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    SITE_TO_CODE, STATION_NAMES, SUB_MODES,
    call, ensure_market_page, find_market_vm, read_market_board,
    read_market_state, wait_for_items, hide_pro_dialog, write_csv,
    switch_market_type,
)

ALL_14 = ["US", "GB", "DE", "FR", "IN", "CA", "JP", "ES", "IT", "MX",
          "AE", "AU", "BR", "SA"]


def fetch_station(station_code, sub_modes, sleep_after=12.0, log=print):
    site_id = next((k for k, v in SITE_TO_CODE.items() if v == station_code), None)
    if site_id is None:
        log(f"[skip] unknown station {station_code}")
        return []

    session = f"market_{station_code.lower()}"
    log(f"[{station_code}] navigating (site={site_id}, session={session})...")
    ensure_market_page(session=session, site=site_id, sleep_after=sleep_after)

    rows = []
    for mode_name, mode_id in sub_modes:
        log(f"[{station_code}] switching to sub_mode={mode_name}({mode_id})")
        res = switch_market_type(mode_id, session)
        log(f"[{station_code}/{mode_name}] switch: {res}")

        if isinstance(res, dict) and res.get("changed"):
            time.sleep(sleep_after)
        elif isinstance(res, dict) and res.get("err"):
            log(f"[{station_code}/{mode_name}] VM not found, skipping")
            continue

        hide_pro_dialog(session)
        state = wait_for_items(session, min_count=10, max_wait=sleep_after + 8)
        log(f"[{station_code}/{mode_name}] state: {state}")

        items = read_market_board(session)
        log(f"[{station_code}/{mode_name}] got {len(items)} items")
        for item in items:
            row = {
                "station": station_code,
                "station_name": STATION_NAMES.get(station_code, ""),
                "site_id": site_id,
                "sub_mode": mode_name,
                "sub_mode_id": mode_id,
            }
            row.update(item)
            rows.append(row)
    return rows


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--stations", default=",".join(ALL_14),
                   help="Comma-separated station codes")
    p.add_argument("--us-only-4modes", action="store_true",
                   help="Only US, with 4 sub-modes; others just multi")
    p.add_argument("--all-4modes", action="store_true",
                   help="All 14 stations × 4 sub-modes (slow)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--sleep", type=float, default=12.0)
    args = p.parse_args()

    stations = [s.strip().upper() for s in args.stations.split(",") if s.strip()]
    if not args.out:
        print("error: --out required")
        sys.exit(2)

    all_rows = []
    for st in stations:
        if args.us_only_4modes and st == "US":
            sub_modes = list(SUB_MODES.items())
        elif args.all_4modes:
            sub_modes = list(SUB_MODES.items())
        else:
            sub_modes = [("multi", SUB_MODES["multi"])]
        try:
            rows = fetch_station(st, sub_modes, sleep_after=args.sleep)
            all_rows.extend(rows)
            print(f"==> {st} total: {len(rows)} rows", file=sys.stderr)
        except Exception as e:
            print(f"[{st}] FAILED: {e}", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not all_rows:
        print("no rows collected!", file=sys.stderr)
    base = ["station", "station_name", "site_id", "sub_mode", "sub_mode_id",
            "Name", "NodeId", "Number", "Url", "SaleCount", "BrandCount",
            "AveragePrice", "SolderNumberCN", "SolderRateCN",
            "OneMonthProductCount", "ThreeMonthProductCount", "SixMonthProductCount",
            "NewProductCount", "NewSalesVolumeRate",
            "OneMonthCommentCount", "OneMonthScoreCount",
            "AmzFbaRate", "EbcRate", "FBMCount",
            "LowPriceProductCount", "TariffValueNum", "AmazonHaul",
            "CPCAvgPrice", "AveragePriceHB",
            "SaleCountPrev", "SaleCountPrevThree", "SaleCountPrevTen",
            "SolderPrev", "BrandPrev",
            "SorfTimeNumber", "AddRate", "GrossProfitMargin"]
    fields = write_csv(out, all_rows, base)
    print(f"wrote {len(all_rows)} rows × {len(fields)} fields → {out}")


if __name__ == "__main__":
    main()
