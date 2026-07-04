"""sorftime 选市场 scraper (multi-mode).

Reads `marketBoard.items` (top 20 categories per station, 246 fields each)
from the Vue VM — no need to manually call initData(nodeId) because the
page auto-populates this slice on initial load.

For deeper coverage, switch to the 4 sub-modes (multi / buyer / new /
lowprice) — each fetches a different 20-category top list.

Output CSV: one row per (station, sub_mode, category) with station
metadata + all 246 raw fields prefixed.
"""
import argparse
import csv
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


SESS_PREFIX = "market"


def fetch_station(station_code, sub_modes, sleep_after=10.0):
    """Scrape one station across all requested sub-modes.

    Strategy: navigate once per station, then for each sub_mode just
    switch the VM's `marketType` and wait for items to repopulate.
    """
    site_id = next((k for k, v in SITE_TO_CODE.items() if v == station_code), None)
    if site_id is None:
        print(f"[skip] unknown station {station_code}", file=sys.stderr)
        return []

    session = f"{SESS_PREFIX}_{station_code.lower()}"
    print(f"[{station_code}] navigating (site={site_id})...", file=sys.stderr)
    ensure_market_page(session=session, site=site_id, sleep_after=sleep_after)

    rows = []
    for mode_name, mode_id in sub_modes:
        print(f"[{station_code}] switching to sub_mode={mode_name}({mode_id})",
              file=sys.stderr)
        res = switch_market_type(mode_id, session)
        print(f"[{station_code}/{mode_name}] switch result: {res}",
              file=sys.stderr)

        if isinstance(res, dict) and res.get("changed"):
            time.sleep(sleep_after)

        hide_pro_dialog(session)
        state = wait_for_items(session, min_count=10, max_wait=sleep_after + 5)
        print(f"[{station_code}/{mode_name}] state: {state}", file=sys.stderr)

        items = read_market_board(session)
        print(f"[{station_code}/{mode_name}] got {len(items)} items",
              file=sys.stderr)
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
    p = argparse.ArgumentParser()
    p.add_argument("--station", required=True,
                   help="Comma-separated site codes (US,JP,GB,...)")
    p.add_argument("--out", required=True, help="CSV output path")
    p.add_argument("--sub-modes", default="multi",
                   help="Comma-separated: multi,buyer,new,lowprice")
    p.add_argument("--sleep-after", type=float, default=10.0,
                   help="Seconds to wait after navigate/switch")
    args = p.parse_args()

    stations = [s.strip().upper() for s in args.station.split(",") if s.strip()]
    if not stations:
        print("error: --station required", file=sys.stderr)
        sys.exit(2)

    sub_modes = []
    for m in args.sub_modes.split(","):
        m = m.strip()
        if m in SUB_MODES:
            sub_modes.append((m, SUB_MODES[m]))
        else:
            print(f"warn: unknown sub_mode {m}; skipping", file=sys.stderr)

    all_rows = []
    for st in stations:
        try:
            all_rows.extend(fetch_station(st, sub_modes, args.sleep_after))
        except Exception as e:
            print(f"[{st}] failed: {e}", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not all_rows:
        print("no rows collected; writing empty CSV", file=sys.stderr)
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
