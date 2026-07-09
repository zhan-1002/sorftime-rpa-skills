"""Shared helpers for sorftime-1688-compare skill.

DOM-driven skill. 1688 image search (s.1688.com) works via:
  1. Navigate to s.1688.com
  2. Download image blob, inject into file input via DataTransfer
  3. Click search button (.search-btn)
  4. Extract product listings from DOM

Requires manual 1688 login (one-time, cookie persists in WebBridge browser).
"""
import json
import time
import urllib.request
from pathlib import Path

DAEMON = "http://127.0.0.1:10086/command"
DEFAULT_SESSION = "sorftime-1688-compare"
SEARCH_URL = "https://s.1688.com/"

# Standard 1688 product detail URL template
DETAIL_URL = "https://detail.1688.com/offer/{}.html"


def call(action, args, session):
    """Send a command to Kimi WebBridge daemon."""
    body = json.dumps({"action": action, "args": args, "session": session}).encode()
    req = urllib.request.Request(DAEMON, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def evaluate(code, session):
    """Execute JavaScript in the browser and return parsed result."""
    res = call("evaluate", {"code": code}, session)
    if not res.get("ok"):
        return {"_error": res.get("error", {}).get("message", "unknown")}
    data = res["data"]
    if isinstance(data, dict) and data.get("type") == "string":
        try:
            return json.loads(data["value"])
        except Exception:
            return {"raw": data.get("value", "")}
    return data


def navigate(url, session):
    """Open a URL in a new tab."""
    return call("navigate", {"url": url, "newTab": True,
                             "group_title": "1688-compare"}, session)


def check_login(session):
    """Check if 1688 is logged in. Returns True if OK, False if login needed."""
    try:
        result = evaluate("window.location.href", session)
    except Exception:
        return False

    # evaluate() returns either a string or {"raw": "..."} dict
    if isinstance(result, dict):
        url = str(result.get("raw", ""))
    else:
        url = str(result)

    # Also check page body for login wall
    if "login.taobao.com" in url:
        return False
    # Double-check: look for the 1688 search UI elements
    if "s.1688.com" in url or "1688.com" in url:
        return True
    return False


def ensure_1688_page(session, sleep_after=10.0):
    """Navigate to 1688 image search page. Returns login status."""
    navigate(SEARCH_URL, session)
    time.sleep(sleep_after)

    if not check_login(session):
        return {"logged_in": False,
                "error": "1688 requires login. Please log in at https://s.1688.com/ in the WebBridge browser, then retry."}

    return {"logged_in": True}


def upload_image(image_url, session):
    """Download image from URL and inject into 1688 file input via DataTransfer.

    Returns dict with 'ok' and 'file_size' on success, or 'error' on failure.
    """
    code = f"""
(async function(){{
    try {{
        var resp = await fetch('{image_url}');
        var blob = await resp.blob();
        var file = new File([blob], 'product.jpg', {{type: blob.type || 'image/jpeg'}});
        var dt = new DataTransfer();
        dt.items.add(file);

        var fileInput = document.querySelector('input[type="file"]');
        if (!fileInput) return JSON.stringify({{err: 'no file input found'}});

        try {{ fileInput.files = dt.files; }} catch(e) {{}}
        fileInput.dispatchEvent(new Event('change', {{bubbles: true}}));

        return JSON.stringify({{ok: true, inputId: fileInput.id, fileSize: file.size}});
    }} catch(e) {{
        return JSON.stringify({{err: e.toString()}});
    }}
}})()
"""
    return evaluate(code, session)


def check_upload_state(session):
    """Check if the image was recognized by 1688.

    Returns dict with 'uploaded' (bool) and 'search_btn' (bool).
    """
    code = """
(function(){
    var b = document.body ? document.body.innerText : '';
    var uploaded = b.indexOf('已上传') > -1;
    var searchBtn = b.indexOf('搜索图片') > -1;
    return JSON.stringify({uploaded: uploaded, searchBtn: searchBtn});
})()
"""
    return evaluate(code, session)


def click_search(session):
    """Click the 1688 image search button. Returns click result."""
    code = """
(function(){
    var btn = document.querySelector('.search-btn');
    if (btn && btn.offsetParent) {
        btn.click();
        return JSON.stringify({clicked: 'search-btn'});
    }
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
        if ((all[i].textContent || '').trim() === '搜索图片' && all[i].offsetParent) {
            all[i].click();
            return JSON.stringify({clicked: 'fallback', tag: all[i].tagName});
        }
    }
    return JSON.stringify({clicked: false});
})()
"""
    return evaluate(code, session)


def extract_products(session, max_items=10):
    """Extract product listings from 1688 image search results page.

    Returns a list of dicts with: title, price, supplier, offer_id, detail_url.
    """
    code = """
(function(){
    var prods = [], seen = {};

    document.querySelectorAll('[class*="offer"]').forEach(function(card) {
        if (prods.length >= """ + str(max_items) + """) return;

        var titleEl = card.querySelector('a[title], h3, [class*="title"]');
        var title = titleEl ? (titleEl.textContent || titleEl.getAttribute('title') || '').trim() : '';
        if (!title || title.length < 8 || seen[title]) return;
        seen[title] = true;

        var priceEl = card.querySelector('[class*="price"]');
        var price = priceEl ? priceEl.textContent.replace(/\\s+/g, ' ').trim().substring(0, 50) : '';

        var supEl = card.querySelector('[class*="supplier"], [class*="company"], [class*="shop"]');
        var supplier = supEl ? supEl.textContent.trim().substring(0, 50) : '';

        var offerId = '';
        var links = card.querySelectorAll('a[href]');
        links.forEach(function(a) {
            var m = a.href.match(/offerId=(\\d+)/);
            if (m) offerId = m[1];
        });

        prods.push({
            title: title.substring(0, 80),
            price: price,
            supplier: supplier,
            offer_id: offerId
        });
    });

    return JSON.stringify({count: prods.length, products: prods});
})()
"""
    result = evaluate(code, session)
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "products" in result:
        return result["products"]
    return []


def write_csv(path, rows, image_url=""):
    """Write extracted products to CSV with detail URLs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    import csv
    fields = ["title", "price", "supplier", "offer_id",
              "detail_url", "image_url", "search_mode"]

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            oid = row.get("offer_id", "")
            row["detail_url"] = DETAIL_URL.format(oid) if oid else ""
            row["image_url"] = image_url
            w.writerow(row)

    return path


# ── 1688 Text Search ──


def search_by_text(keyword, session, sleep_after=10.0, max_items=10):
    """Search 1688 by text keyword (falls back when image search is noisy).

    Navigates to 1688 keyword search, extracts product listings.

    Args:
        keyword: search term (e.g. "万圣节窗户贴纸")
        session: WebBridge session name
        sleep_after: page load wait
        max_items: max results

    Returns:
        list of product dicts
    """
    import urllib.parse
    encoded = urllib.parse.quote(keyword)
    url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded}"

    navigate(url, session)
    time.sleep(sleep_after)

    if not check_login(session):
        return [{"error": "1688 login required for text search"}]

    return extract_products(session, max_items=max_items)


def combined_search(image_url, keywords, session, sleep_after=10.0, max_items=10):
    """Run both image search and text search, merge and deduplicate.

    Args:
        image_url: Amazon image URL for image search
        keywords: list of keyword strings for text search
        session: WebBridge session name
        sleep_after: page load wait
        max_items: max items per search mode

    Returns:
        dict with 'image_results', 'text_results', and 'merged' (deduplicated)
    """
    all_image = []
    all_text = []
    seen_titles = set()

    # Image search
    state = ensure_1688_page(session, sleep_after=sleep_after)
    if state.get("logged_in"):
        upload_result = upload_image(image_url, session)
        if isinstance(upload_result, dict) and not upload_result.get("err") and not upload_result.get("_error"):
            time.sleep(6)
            upload_state = check_upload_state(session)
            if isinstance(upload_state, dict) and upload_state.get("uploaded"):
                click_search(session)
                time.sleep(12)
                all_image = extract_products(session, max_items=max_items)
                for p in all_image:
                    p["search_mode"] = "image"
                    seen_titles.add(p.get("title", ""))

    # Text search for each keyword
    for kw in keywords:
        text_results = search_by_text(kw, session, sleep_after=sleep_after, max_items=max_items)
        for p in text_results:
            if isinstance(p, dict) and not p.get("error"):
                title = p.get("title", "")
                if title not in seen_titles:
                    p["search_mode"] = f"text:{kw}"
                    seen_titles.add(title)
                    all_text.append(p)

    # Merge: image results first (visually similar), then text (keyword match)
    merged = all_image + all_text

    return {
        "image_results": all_image,
        "text_results": all_text,
        "merged": merged
    }
