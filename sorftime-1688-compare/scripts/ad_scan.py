"""Scan ad dependency for all sample ASINs via sellersprite ad insight."""
import json, urllib.request, time, sys, io, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DAEMON = "http://127.0.0.1:10086/command"
BASE = "ad_scan"

# All sample ASINs
ASINS = [
    ("B0GGYCN7SX", "告示板DIY套装", 146),
    ("B0DCZL7V9M", "派对横幅DIY", 171),
    ("B0FG7VNRS1", "水果玻璃杯", 141),
    ("B0GTQZCRFB", "露营折叠椅", 122),
    ("B0F4QRR2R3", "螃蟹头箍", 87),
    ("B0FHKLQXYD", "圣诞袜架", 198),
    ("B0FVXKNYQV", "新居礼物套装", 78),
    ("B0GCLN6RQZ", "汤碗4件套", 99),
    ("B0FJR5XMWC", "圣诞产品", 125),
    ("B0D2NQ5BX7", "圣诞产品", 167),
]

def call(action, args, session):
    body = json.dumps({"action": action, "args": args, "session": session}).encode()
    req = urllib.request.Request(DAEMON, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def evaluate(code, session):
    try:
        res = call("evaluate", {"code": code}, session)
        if not res.get("ok"):
            return None
        d = res["data"]
        if isinstance(d, dict) and d.get("type") == "string":
            v = d.get("value", "")
            try: return json.loads(v)
            except: return v[:5000]
        return str(d)[:5000]
    except:
        return None

results = []

for asin, name, roi in ASINS:
    session = f"{BASE}_{asin}"
    url = f"https://www.sellersprite.com/v3/ads-insights?q={asin}&marketId=1&months=6"

    print(f"\n{asin} {name} (ROI:{roi}%)...", end=" ", flush=True)

    try:
        call("navigate", {"url": url, "newTab": True, "group_title": BASE}, session)
        time.sleep(8)
    except:
        print("NAV_FAIL")
        results.append((asin, name, roi, "NAV_ERR", 0))
        continue

    # Extract ad summary from page body
    body = evaluate("document.body ? document.body.innerText.substring(0, 2000) : ''", session)
    if not body or isinstance(body, dict):
        print("EVAL_FAIL")
        results.append((asin, name, roi, "EVAL_ERR", 0))
        continue

    # Parse: "共计有：X个投放小组（Y个SP、Z个SBV），属于W个广告活动"
    import re
    match = re.search(r'共计有[：:]?\s*(\d+)\s*个投放小组[（(]\s*(\d+)\s*个SP[、，]\s*(\d+)\s*个SBV', body)
    if match:
        total_groups = int(match.group(1))
        sp_count = int(match.group(2))
        sbv_count = int(match.group(3))

        # Also count campaigns
        camp_match = re.search(r'属于\s*(\d+)\s*个广告活动', body)
        campaigns = int(camp_match.group(1)) if camp_match else 0

        if total_groups <= 2:
            level = "低"
        elif total_groups <= 8:
            level = "中"
        else:
            level = "高"

        print(f"{total_groups}组({sp_count}SP+{sbv_count}SBV) {campaigns}活动 [{level}]")
        results.append((asin, name, roi, level, total_groups, sp_count, sbv_count, campaigns))
    else:
        # Check if any ad data exists
        has_ad = "广告组" in body or "广告活动" in body
        if has_ad:
            # Try to count groups differently
            groups = body.count("广告组")
            print(f"~{groups} groups (manual count)")
            results.append((asin, name, roi, "~" + str(groups), groups, 0, 0, 0))
        else:
            print("NO_AD_DATA")
            results.append((asin, name, roi, "无广告", 0, 0, 0, 0))

    time.sleep(2)

# Summary
print(f"\n{'='*80}")
print(f"{'ASIN':<12} {'Product':<16} {'ROI':>5} {'Ad Level':<8} {'Groups':>6} {'SP':>4} {'SBV':>4} {'Camps':>5}")
print(f"{'-'*80}")
for r in results:
    if len(r) == 8:
        asin, name, roi, level, groups, sp, sbv, camps = r
        print(f"{asin:<12} {name:<16} {roi:>4}% {level:<8} {groups:>6} {sp:>4} {sbv:>4} {camps:>5}")
    else:
        asin, name, roi, level, groups = r
        print(f"{asin:<12} {name:<16} {roi:>4}% {level:<8} {groups:>6}")

# Save
out = os.path.expanduser("~/sorftime-data/ad_scan_results.csv")
with open(out, "w", encoding="utf-8-sig") as f:
    f.write("asin,name,roi,ad_level,ad_groups,sp_groups,sbv_groups,campaigns\n")
    for r in results:
        f.write(",".join(str(x) for x in r) + "\n")
print(f"\nSaved: {out}")
