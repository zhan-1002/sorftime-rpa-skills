"""Probe sellersprite 广告洞察 (ad insight) tool."""
import json, urllib.request, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DAEMON = "http://127.0.0.1:10086/command"
S = "ad_insight"

def call(action, args):
    body = json.dumps({"action": action, "args": args, "session": S}).encode()
    req = urllib.request.Request(DAEMON, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def evaluate(code):
    res = call("evaluate", {"code": code})
    if not res.get("ok"):
        return {"err": str(res.get("error", {}))[:200]}
    d = res["data"]
    if isinstance(d, dict) and d.get("type") == "string":
        v = d.get("value", "")
        try: return json.loads(v)
        except: return v[:3000]
    return str(d)[:3000]

# Step 1: Navigate to sellersprite and find 广告洞察
print("1. Opening sellersprite...")
call("navigate", {"url": "https://www.sellersprite.com/", "newTab": True, "group_title": "sp_adinsight"})
time.sleep(8)

# Find the toolbar and 广告洞察 link
print("2. Finding 广告洞察 in toolbar...")
nav = evaluate("""
(function(){
    var results = [];
    // Find all nav/toolbar items
    document.querySelectorAll('a, li, span, div[class*=menu], div[class*=nav], div[class*=tool]').forEach(function(el){
        var txt = (el.textContent || '').trim();
        if (txt.indexOf('广告') > -1 || txt.indexOf('洞察') > -1 || txt.indexOf('工具') > -1) {
            var href = el.getAttribute('href') || '';
            var parent = el.closest('a');
            if (parent) href = parent.getAttribute('href') || href;
            results.push({text: txt.substring(0, 30), href: href.substring(0, 100), tag: el.tagName});
        }
    });
    return JSON.stringify(results);
})()
""")
print(f"   Found: {nav}")

# Step 3: Try common ad insight URL patterns
print("3. Trying ad insight URLs...")
urls_to_try = [
    "/v3/ad-insight",
    "/v3/ad-research",
    "/v3/advertising-insight",
    "/v3/ppc-research",
    "/v3/ads",
    "/v3/tools/ad-insight",
    "/v3/ad",
]

found_api = None
for u in urls_to_try:
    full = f"https://www.sellersprite.com{u}"
    call("navigate", {"url": full, "newTab": True, "group_title": "sp_adinsight"})
    time.sleep(5)
    title = evaluate("document.title")
    url = evaluate("window.location.href")
    print(f"   {u}: {title}")

    # Check if page has search/ASIN input (means it's functional)
    has_input = evaluate("""
    (function(){
        var inputs = document.querySelectorAll('input[type=text], textarea, input[placeholder*=asin i], input[placeholder*=ASIN]');
        return inputs.length;
    })()
    """)
    if isinstance(has_input, int) and has_input > 0:
        print(f"      *** HAS INPUT: {has_input} inputs ***")
        found_api = u
        break

if found_api:
    print(f"\n4. Found functional page: {found_api}")
    # Try to find the API endpoint by checking network activity or page source
    # Look for API paths in the page
    apis = evaluate("""
    (function(){
        var scripts = document.querySelectorAll('script');
        var found = [];
        scripts.forEach(function(s){
            var t = s.textContent || '';
            var matches = t.match(/\\/v3\\/api\\/[a-zA-Z_-]+/g);
            if (matches) found = found.concat(matches);
        });
        return JSON.stringify([...new Set(found)]);
    })()
    """)
    print(f"   API endpoints found: {apis}")
else:
    print("\nNo functional ad insight page found. Manual navigation needed.")
    print("Please navigate to 广告洞察 manually in the browser, then re-run.")
