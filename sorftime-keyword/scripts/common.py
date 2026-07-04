"""Shared helpers for sorftime-keyword scripts.

DOM-driven skill. The 关键词趋势选品 page (/home/choosekeyword) actually
DOES populate data by default (20 hot keywords in `keywordData.listData`)
even without category selection. The "filter-gated" assumption was wrong.

Key fact: `keywordData.listData` lives in an anonymous parent VM at
depth 6, NOT in the side-Keyword component (which is at depth 3 with
empty List/table).

Page state shape:
  Anonymous parent VM (depth 6) holds:
    - keywordData.listData   (20 default hot keywords, populated!)
    - keywordData.options    (column schema)
    - keywordData.page       (pagination)
    - screen.select          (filter spec, "" when no filter)
    - table.node.data        (filtered results, empty by default)

  side-Keyword VM (depth 3) holds:
    - keywordData.List       (empty unless filter applied)
    - table.node.data        (empty unless filter applied)
    - table.node.options     (column schema)
    - screen.select/nodeData (filter state)

API endpoint (encrypted):
  POST https://api.sorftime.com/api/keywordboard/querykeywordboard?site=NN
  Body: AES-encrypted via page's app.js obfuscator
  Response: {v:3, k:"<b64>", d:"<AES ciphertext>"} decrypted by axios
  transformResponse back into JSON. We don't call this directly — we
  read the decrypted result from VM state.

Same 14 Amazon markets, same localStorage site switching.
"""
import json
import time
import urllib.request
from pathlib import Path

DAEMON = "http://127.0.0.1:10086"
DEFAULT_SESSION = "sorftime-keyword"
KEYWORD_URL = "https://seller.sorftime.com/home/choosekeyword"

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


def ensure_keyword_page(session, site=None, sleep_after=8.0):
    """Navigate to the keyword page; optionally set site via localStorage.

    The page needs ~7-8s to fully mount Vue + initialize the
    side-Keyword VM + fire initial encrypted POSTs.
    """
    if site is not None:
        call("navigate", {"url": KEYWORD_URL, "newTab": True,
                          "group_title": "sorftime"}, session)
        time.sleep(4.0)
        evaluate(f'localStorage.setItem("site","{site}")', session)
        evaluate('location.reload()', session)
        time.sleep(sleep_after)
    else:
        call("navigate", {"url": KEYWORD_URL, "newTab": True,
                          "group_title": "sorftime"}, session)
        time.sleep(sleep_after)
    # Hide the Pro dialog that blocks the page
    hide_pro_dialog(session)
    time.sleep(2.0)


def find_side_keyword_vm(session):
    """Return side-Keyword VM presence check.

    The `keywordData.listData` (20 default hot keywords) lives in an
    anonymous parent VM at depth 6, not in the side-Keyword component
    (which only has empty `List` and `table.node.data`). We look for
    the VM that has the populated listData.
    """
    code = """
    (function () {
      const root = document.querySelector('#app');
      let vm = null;
      let sideKw = null;
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 15 || !n || seen.has(n)) return;
        seen.add(n);
        const name = n.$options && (n.$options.name || n.$options._componentTag);
        const data = n._data || {};
        if (!sideKw && name === 'side-Keyword') sideKw = n;
        if (!vm && data.keywordData && Array.isArray(data.keywordData.listData) && data.keywordData.listData.length > 0) {
          vm = n;
        }
        if (n.$children) n.$children.forEach(c => visit(c, d + 1));
      };
      visit(root.__vue__, 0);
      return JSON.stringify({
        ok: true,
        listData_vm_found: !!vm,
        side_keyword_found: !!sideKw,
      });
    })()
    """
    return evaluate(code, session)


def read_state(session):
    """Read VM state — page summary for diagnostic.

    Returns dict with: loading, kw_listdata_len (default 20), kw_list_len
    (often 0), table_data_len (often 0 until filter), screen_select,
    options_count (column schema), and the first row if populated.

    NOTE: 选关键词 page (默认 / 趋势模式) actually has 20 default items
    in `keywordData.listData` even when categoryLoad=false. This
    listData is in an anonymous parent VM at depth 6, NOT in
    side-Keyword (which is at depth 3 with empty List/table). We look
    for whichever VM has populated listData.
    """
    code = """
    (function () {
      const root = document.querySelector('#app');
      let vm = null;
      const seen = new Set();
      const visit = (n, d) => {
        if (d > 15 || !n || seen.has(n)) return;
        seen.add(n);
        const data = n._data || {};
        if (!vm && data.keywordData && Array.isArray(data.keywordData.listData) && data.keywordData.listData.length > 0) {
          vm = n;
        }
        if (n.$children) n.$children.forEach(c => visit(c, d + 1));
      };
      visit(root.__vue__, 0);
      if (!vm) return JSON.stringify({err: 'no listData VM'});
      const d = vm._data;
      const table = d.table && d.table.node;
      const kw = d.keywordData;
      return JSON.stringify({
        loading: d.loading,
        table_data_len: table && table.data ? table.data.length : 0,
        table_total: table && table.page ? table.page.totalCount : 0,
        table_page_size: table && table.page ? table.page.pageSize : 0,
        table_options_count: table && table.options ? table.options.length : 0,
        kw_list_len: kw && kw.List ? kw.List.length : 0,
        kw_listdata_len: kw && kw.listData ? kw.listData.length : 0,
        screen_select: d.screen && d.screen.select,
        screen_nodeData_keys: d.screen && d.screen.nodeData
          ? Object.keys(d.screen.nodeData) : [],
        site: d.site,
        first_row: table && table.data && table.data[0]
          ? JSON.stringify(table.data[0]).slice(0, 800) : null,
        first_kw: kw && kw.List && kw.List[0]
          ? JSON.stringify(kw.List[0]).slice(0, 800) : null,
        first_listdata: kw && kw.listData && kw.listData[0]
          ? JSON.stringify(kw.listData[0]).slice(0, 800) : null
      });
    })()
    """
    return evaluate(code, session)


def read_listdata(session, max_items=200):
    """Read `keywordData.listData` (20 默认热门词) from anonymous parent VM.

    Returns list of plain dicts. Each dict has the full keyword record
    (id, name, avgPrice, avgScore, cpc, growth rates, busySeason,
    cyclicalMarket, asinList, cpcTrend, etc.). Empty list if no data.
    """
    code = f"""
    (function () {{
      const root = document.querySelector('#app');
      let vm = null;
      const seen = new Set();
      const visit = (n, d) => {{
        if (d > 15 || !n || seen.has(n)) return;
        seen.add(n);
        const data = n._data || {{}};
        if (!vm && data.keywordData && Array.isArray(data.keywordData.listData) && data.keywordData.listData.length > 0) {{
          vm = n;
        }}
        if (n.$children) n.$children.forEach(c => visit(c, d + 1));
      }};
      visit(root.__vue__, 0);
      if (!vm) return JSON.stringify({{err: 'no listData VM'}});
      const kw = vm._data.keywordData;
      if (!kw || !kw.listData || !Array.isArray(kw.listData)) {{
        return JSON.stringify({{err: 'no listData'}});
      }}
      const items = kw.listData.slice(0, {max_items});
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
