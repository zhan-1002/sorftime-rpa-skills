"""Shared helpers for sorftime-seller scripts.

DOM-driven skill. The 选卖家 page (/home/chooseseller) reuses the same
`side-Keyword` VM as keyword/brand pages for the filter UI, but the
**多维度卖家选品** default tab populates `_data.sellerBoard.items`
with 20 seller rows in an anonymous parent VM — same pattern as
the brand page's `board.items`. No category selection needed.

Schema: Name, Id, SolderId, SolderUrl, EnterpriseName, BusinessAddress,
SellerNationalityOrRegion, SellerOnlineTime, FeedbackCount, ProductCount,
AllBrandCount, BSR* group (50+ fields incl. operating categories,
estimated monthly sales, FBA/FBM breakdown, new product stats),
ImageData (top 10 ASINs as JSON array).

Same 14 Amazon markets, same localStorage site switching.
"""
import json
import time
import urllib.request
from pathlib import Path

DAEMON = "http://127.0.0.1:10086"
DEFAULT_SESSION = "sorftime-seller"
SELLER_URL = "https://seller.sorftime.com/home/chooseseller"

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


def hide_pro_dialog(session):
    """Hide the Sorftime Pro upgrade dialog overlay.

    The Pro dialog blocks the page (including Vue re-rendering) until
    the user dismisses it. We need to remove it programmatically so
    that the data tables populate.
    """
    code = r"""
    (function () {
      const allOverlays = document.querySelectorAll('div');
      let removed = 0;
      for (const d of allOverlays) {
        const t = d.textContent || '';
        if ((t.includes('购买Sorftime') || t.includes('专业版')) && t.length < 200) {
          let p = d;
          for (let i = 0; i < 5 && p; i++) {
            if (p.className && (String(p.className).includes('el-overlay') || String(p.className).includes('el-dialog'))) {
              p.style.display = 'none';
              p.remove();
              removed++;
              break;
            }
            p = p.parentElement;
          }
        }
      }
      document.querySelectorAll('.v-modal, .el-overlay').forEach(v => { v.remove(); removed++; });
      return JSON.stringify({ok: true, removed});
    })()
    """
    return evaluate(code, session)


def ensure_seller_page(session, site=None, sleep_after=8.0):
    if site is not None:
        # 1) Navigate first to establishes the origin context
        call("navigate", {"url": SELLER_URL, "newTab": True,
                          "group_title": "sorftime"}, session)
        time.sleep(4.0)
        # 2) Set localStorage AFTER navigation
        evaluate(f'localStorage.setItem("site","{site}")', session)
        # 3) Reload so the page reads the new site
        evaluate('location.reload()', session)
        time.sleep(sleep_after)
    else:
        call("navigate", {"url": SELLER_URL, "newTab": True,
                          "group_title": "sorftime"}, session)
        time.sleep(sleep_after)
    # Hide the Pro dialog. The Pro upgrade dialog BLOCKS page interaction
    # AND prevents the data board from populating. Hide it BEFORE the data
    # load window — then wait for the data to actually fill in.
    hide_pro_dialog(session)
    time.sleep(3.0)


def find_seller_board_vm(session):
    """Return sellerBoard VM presence check (where sellerBoard.items lives)."""
    code = """
    (function () {
      const root = document.querySelector('#app');
      let vm = null;
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 18 || !n || seen.has(n)) return;
        seen.add(n);
        const data = n._data || {};
        if (!vm && data.sellerBoard && Array.isArray(data.sellerBoard.items) && data.sellerBoard.items.length > 0) {
          vm = n;
        }
        if (n.$children) n.$children.forEach(c => visit(c, d + 1));
      };
      visit(root.__vue__, 0);
      return JSON.stringify({
        ok: true,
        seller_board_vm_found: !!vm,
        items_count: vm && vm._data.sellerBoard ? vm._data.sellerBoard.items.length : 0,
      });
    })()
    """
    return evaluate(code, session)


def read_state(session):
    """Read sellerBoard VM state — page summary for diagnostic."""
    code = """
    (function () {
      const root = document.querySelector('#app');
      let vm = null;
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 18 || !n || seen.has(n)) return;
        seen.add(n);
        const data = n._data || {};
        if (!vm && data.sellerBoard && Array.isArray(data.sellerBoard.items)) {
          vm = n;
        }
        if (n.$children) n.$children.forEach(c => visit(c, d + 1));
      };
      visit(root.__vue__, 0);
      if (!vm) return JSON.stringify({err: 'no sellerBoard'});
      const d = vm._data;
      const b = d.sellerBoard;
      return JSON.stringify({
        loading: d.loading,
        seller_items_len: b.items.length,
        seller_page: b.page,
        site: d.site,
        first_seller: b.items[0] ? b.items[0].Name : null,
      });
    })()
    """
    return evaluate(code, session)


def read_seller_items(session, max_items=100):
    """Read `sellerBoard.items` (20 默认卖家行).

    Returns list of plain dicts. Each has Name, Id, SolderId, SolderUrl,
    EnterpriseName, BusinessAddress, SellerNationalityOrRegion,
    SellerOnlineTime, FeedbackCount, ProductCount, AllBrandCount,
    CompareLastMonthProductCount, BSR* (50+ fields), ImageData (top
    10 ASINs as JSON string).
    """
    code = f"""
    (function () {{
      const root = document.querySelector('#app');
      let vm = null;
      const seen = new Set();
      const visit = (n, d) => {{
        if (d > 18 || !n || seen.has(n)) return;
        seen.add(n);
        const data = n._data || {{}};
        if (!vm && data.sellerBoard && Array.isArray(data.sellerBoard.items)) {{
          vm = n;
        }}
        if (n.$children) n.$children.forEach(c => visit(c, d + 1));
      }};
      visit(root.__vue__, 0);
      if (!vm) return JSON.stringify({{err: 'no sellerBoard'}});
      const items = vm._data.sellerBoard.items.slice(0, {max_items});
      return JSON.stringify(items);
    }})()
    """
    result = evaluate(code, session)
    if isinstance(result, dict) and result.get("err"):
        return []
    if isinstance(result, list):
        return result
    return []


def write_csv(path, rows, base_fields):
    extra = []
    seen = set(base_fields)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                extra.append(k); seen.add(k)
    fields = base_fields + extra
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        import csv
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
