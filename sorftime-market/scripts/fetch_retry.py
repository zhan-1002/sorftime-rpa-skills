"""Retry the 5 stations that returned 0 items initially.

For each: navigate fresh, longer sleep for slow Pro dialog, more
retries if first attempt times out.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    SITE_TO_CODE, STATION_NAMES, SUB_MODES,
    call, ensure_market_page, read_market_board,
    read_market_state, wait_for_items, hide_pro_dialog, write_csv,
    switch_market_type,
)

FAILED = ["IN", "CA", "MX", "AU", "SA"]


def fetch_with_retry(station_code, max_retries=2, sleep_after=22.0, log=None):
    if log is None:
        log = print
    site_id = next((k for k, v in SITE_TO_CODE.items() if v == station_code), None)
    if site_id is None:
        return []
    session = f"market_retry_{station_code.lower()}"
    log(f"[{station_code}] navigating (site={site_id}, sleep={sleep_after}s)...")

    # Fresh session + new tab
    call("navigate", {"url": "https://seller.sorftime.com/home/choosemarketblock",
                       "newTab": True, "group_title": "sorftime-retry"}, session)
    time.sleep(5.0)
    res = call("evaluate", {"code": f'localStorage.setItem("site","{site_id}")'}, session)
    log(f"  setItem site={site_id}: ok={res.get('ok')}")
    call("evaluate", {"code": "location.reload()"}, session)
    time.sleep(sleep_after)

    rows = []
    for attempt in range(max_retries + 1):
        hide_pro_dialog(session)
        switch_market_type(SUB_MODES["multi"], session)
        state = wait_for_items(session, min_count=10, max_wait=sleep_after + 8)
        items_len = state.get("itemsLen", 0) if isinstance(state, dict) else 0
        log(f"  [{station_code}] attempt {attempt+1}: itemsLen={items_len}")
        if items_len >= 10:
            items = read_market_board(session)
            log(f"  [{station_code}] got {len(items)} items")
            for item in items:
                row = {
                    "station": station_code,
                    "station_name": STATION_NAMES.get(station_code, ""),
                    "site_id": site_id,
                    "sub_mode": "multi",
                    "sub_mode_id": SUB_MODES["multi"],
                }
                row.update(item)
                rows.append(row)
            return rows
        time.sleep(8)
    return rows


def main():
    all_rows = []
    for st in FAILED:
        try:
            rows = fetch_with_retry(st, max_retries=2, sleep_after=22.0)
            print(f"==> {st} total: {len(rows)} rows", flush=True)
            all_rows.extend(rows)
        except Exception as e:
            print(f"[{st}] FAILED: {e}", flush=True)

    out = Path("d:/sorftime-rpa/data/markets_retry.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not all_rows:
        print("no retry rows collected", flush=True)
    base = ["station", "station_name", "site_id", "sub_mode", "sub_mode_id",
            "Name", "NodeId", "Number", "Url", "SaleCount", "BrandCount",
            "AveragePrice"]
    fields = write_csv(out, all_rows, base)
    print(f"wrote {len(all_rows)} rows × {len(fields)} fields → {out}", flush=True)


if __name__ == "__main__":
    main()
