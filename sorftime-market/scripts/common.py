"""Shared helpers for sorftime-market scripts.

DOM-driven skill. The 选市场 page (/home/choosemarketblock) auto-populates
`marketBoard.items` with the top 20 categories per station on page load.
Each item has 246 fields covering pricing, sales, brand/seller stats,
tariff, profit, etc. This is the main data slice we use.

Strategy: navigate → wait for databoard API to populate `marketBoard.items`
→ read directly. No need for initData(nodeId) manual trigger.

Pagination (`pageIndex=2..5`) does not actually swap items in the VM
(verified: data fetches but items array is unchanged) — so we cap at the
default 20 categories per station. To get more, switch the page's
`marketType` to the other 3 sub-modes (消费需求 / 自营新品 / 低价商城).

Same 14 Amazon markets, same localStorage site switching.
"""
import json
import time
import urllib.request
from pathlib import Path

DAEMON = "http://127.0.0.1:10086"
DEFAULT_SESSION = "sorftime-market"
MARKET_URL = "https://seller.sorftime.com/home/choosemarketblock"

SITE_TO_CODE = {
    "1": "US",   "2": "GB",  "3": "DE",  "4": "FR",  "5": "IN",
    "6": "CA",   "7": "JP",  "8": "ES",  "9": "IT",  "10": "MX",
    "11": "AE",  "12": "AU", "13": "BR", "14": "SA",
}
CODE_TO_SITE = {v: k for k, v in SITE_TO_CODE.items()}

STATION_NAMES = {
    "US": "美国", "GB": "英国", "DE": "德国", "FR": "法国", "IN": "印度",
    "CA": "加拿大", "JP": "日本", "ES": "西班牙", "IT": "意大利", "MX": "墨西哥",
    "AE": "阿联酋", "AU": "澳大利亚", "BR": "巴西", "SA": "沙特",
}

SUB_MODES = {
    "multi":     1,   # 多维度选市场
    "buyer":     2,   # 消费需求选市场
    "new":       3,   # 自营新品选市场
    "lowprice":  4,   # 低价商城选市场
}


def call(action, args, session):
    body = json.dumps({"action": action, "args": args, "session": session}).encode()
    req = urllib.request.Request(f"{DAEMON}/command", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def evaluate(code, session):
    res = call("evaluate", {"code": code}, session)
    if not res.get("ok"):
        return {"_error": res.get("error", {}).get("message", "unknown")}
    data = res["data"]
    if isinstance(data, dict) and data.get("type") == "string":
        try:
            return json.loads(data["value"])
        except Exception:
            return {"raw": data.get("value")}
    return data


def ensure_market_page(session, site=None, sub_mode=None, sleep_after=8.0):
    """Open market page. Optionally switch site (1-14) and sub_mode (1-4)."""
    if site is not None:
        call("navigate", {"url": MARKET_URL, "newTab": True,
                          "group_title": "sorftime"}, session)
        time.sleep(4.0)
        evaluate(f'localStorage.setItem("site","{site}")', session)
        evaluate('location.reload()', session)
        time.sleep(sleep_after)
    else:
        call("navigate", {"url": MARKET_URL, "newTab": True,
                          "group_title": "sorftime"}, session)
        time.sleep(sleep_after)
    if sub_mode is not None:
        switch_market_type(sub_mode, session)


def switch_market_type(market_type, session):
    """Switch to one of the 4 sub-modes (1=multi, 2=buyer, 3=new, 4=lowprice).

    Idempotent: if already at requested marketType, no-op.
    """
    code = f"""
    (function () {{
      const r = document.querySelector('#app');
      const seen = new Set();
      const visit = (n, d) => {{
        if (d > 15 || !n || seen.has(n)) return null;
        seen.add(n);
        const dk = n._data ? Object.keys(n._data) : [];
        if (dk.includes('marketBoard')) return n;
        if (n.$children) {{
          for (const c of n.$children) {{
            const r = visit(c, d + 1);
            if (r) return r;
          }}
        }}
        return null;
      }};
      const vm = visit(r.__vue__, 0);
      if (!vm) return JSON.stringify({{err: 'no marketBoard vm'}});
      if (vm.marketType === {json.dumps(market_type)}) {{
        return JSON.stringify({{ok: true, marketType: vm.marketType, changed: false}});
      }}
      vm.marketType = {json.dumps(market_type)};
      return JSON.stringify({{ok: true, marketType: vm.marketType, changed: true}});
    }})()
    """
    return evaluate(code, session)


def find_market_vm(session):
    """Return the VM that owns marketBoard.items (the main category table)."""
    code = """
    (function () {
      const r = document.querySelector('#app');
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 15 || !n || seen.has(n)) return null;
        seen.add(n);
        const dk = n._data ? Object.keys(n._data) : [];
        if (dk.includes('marketBoard')) return n;
        if (n.$children) {
          for (const c of n.$children) {
            const r = visit(c, d + 1);
            if (r) return r;
          }
        }
        return null;
      };
      const vm = visit(r.__vue__, 0);
      return JSON.stringify({ok: !!vm});
    })()
    """
    return evaluate(code, session)


def read_market_board(session):
    """Read the full marketBoard.items array (top-20 categories per page load).

    Each item has 246 fields (Name, NodeId, SaleCount, BrandCount,
    AveragePrice, One/Two/Three/SixMonthProductCount + Share, comment
    counts, scores, FBA/FBM, tariff, profit, etc.).
    """
    code = """
    (function () {
      const r = document.querySelector('#app');
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 15 || !n || seen.has(n)) return null;
        seen.add(n);
        const dk = n._data ? Object.keys(n._data) : [];
        if (dk.includes('marketBoard')) return n;
        if (n.$children) {
          for (const c of n.$children) {
            const r = visit(c, d + 1);
            if (r) return r;
          }
        }
        return null;
      };
      const vm = visit(r.__vue__, 0);
      if (!vm) return JSON.stringify({err: 'no marketBoard vm'});
      const items = vm.marketBoard && vm.marketBoard.items || [];
      return JSON.stringify(items);
    })()
    """
    res = evaluate(code, session)
    return res if isinstance(res, list) else []


def read_market_state(session):
    """Diagnostic: dump pagination, current pageIndex, items count, total."""
    code = """
    (function () {
      const r = document.querySelector('#app');
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 15 || !n || seen.has(n)) return null;
        seen.add(n);
        const dk = n._data ? Object.keys(n._data) : [];
        if (dk.includes('marketBoard')) return n;
        if (n.$children) {
          for (const c of n.$children) {
            const r = visit(c, d + 1);
            if (r) return r;
          }
        }
        return null;
      };
      const vm = visit(r.__vue__, 0);
      if (!vm) return JSON.stringify({err: 'no vm'});
      return JSON.stringify({
        marketType: vm.marketType,
        categoryLoad: vm.categoryLoad,
        pageIndex: vm.selectAllParam && vm.selectAllParam.pageIndex,
        pageSize: vm.selectAllParam && vm.selectAllParam.pageSize,
        itemsLen: (vm.marketBoard && vm.marketBoard.items || []).length,
        tbloading: vm.tbloading,
        runStep: vm.runStep,
        recommendMode: vm.recommendMode,
      });
    })()
    """
    return evaluate(code, session)


def wait_for_items(session, min_count=10, max_wait=15.0, poll=1.0):
    """Poll the VM until `marketBoard.items` has at least `min_count` items."""
    elapsed = 0.0
    last_len = 0
    while elapsed < max_wait:
        state = read_market_state(session)
        if isinstance(state, dict):
            last_len = state.get("itemsLen", 0) or 0
            if last_len >= min_count:
                return state
        time.sleep(poll)
        elapsed += poll
    return {"itemsLen": last_len, "timed_out": True}


def hide_pro_dialog(session):
    """Remove the .el-overlay / .v-modal pro-upgrade dialog if present."""
    code = """
    (function () {
      let n = 0;
      document.querySelectorAll('.el-overlay, .v-modal, .el-dialog__wrapper')
        .forEach(el => { try { el.remove(); n++; } catch (e) {} });
      return JSON.stringify({removed: n});
    })()
    """
    return evaluate(code, session)


def write_csv(path, rows, base_fields):
    extra = []
    seen = set(base_fields)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                extra.append(k)
                seen.add(k)
    fields = base_fields + extra
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        import csv
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return fields
