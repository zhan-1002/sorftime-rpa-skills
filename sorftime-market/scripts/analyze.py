"""Multi-station market analysis report generator (rich 251-field data).

Reads CSV produced by fetch_markets.py / fetch_all14.py (which extracts
marketBoard.items — 20 categories per station, 251 fields per row) and
produces a Markdown report covering per-station category leaders,
cross-station recurring categories, brand/seller density, FBA/AMZ
metrics, tariff and profit indicators, and station summary.

Usage:
    python analyze.py --markets data/markets_14sites.csv --out-md reports/markets.md
"""
import argparse
import csv
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path


def safe_float(s, default=0.0):
    if s is None:
        return default
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().rstrip("%")
    s = re.sub(r"[,$¥€£￥\s]", "", s)
    try:
        return float(s) if s and s != "-9999" else default
    except (ValueError, TypeError):
        return default


def load_rows(path):
    with Path(path).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def station_summary(rows):
    by_st = defaultdict(int)
    sale_sum = defaultdict(float)
    brand_sum = defaultdict(int)
    fba_sum = defaultdict(float)
    for r in rows:
        st = r.get("station", "?")
        by_st[st] += 1
        sale_sum[st] += safe_float(r.get("SaleCount"))
        brand_sum[st] += int(safe_float(r.get("BrandCount")))
        fba_sum[st] += safe_float(r.get("AmzFbaRate"))
    if not by_st:
        return "_No rows_"
    lines = ["| Station | Categories | Brand Sum | Sale Sum | FBA Avg % |",
             "|---|---|---|---|---|"]
    for st in sorted(by_st.keys()):
        n = by_st[st]
        fba_avg = fba_sum[st] / n if n else 0
        lines.append(f"| {st} | {n} | {brand_sum[st]:,} | {sale_sum[st]:,.0f} | {fba_avg:.1f} |")
    return "\n".join(lines)


def top_per_station(rows, n=10):
    sections = []
    by_station = defaultdict(list)
    for r in rows:
        by_station[r["station"]].append(r)
    for st in sorted(by_station.keys()):
        items = sorted(by_station[st], key=lambda r: -safe_float(r.get("SaleCount")))
        top = items[:n]
        if not top:
            continue
        lines = [f"### {st} — Top {len(top)} (按 SaleCount)",
                 "",
                 "| # | Category | Sale | Brand | Price($) | FBA% | Score |",
                 "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(top, 1):
            lines.append(
                f"| {i} | {(r.get('Name','') or '')[:30]} | "
                f"{int(safe_float(r.get('SaleCount'))):,} | "
                f"{int(safe_float(r.get('BrandCount'))):,} | "
                f"{safe_float(r.get('AveragePrice')):.2f} | "
                f"{safe_float(r.get('AmzFbaRate')):.1f} | "
                f"{safe_float(r.get('SorfTimeNumber')):.1f} |"
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else "_No data_"


def cross_station_categories(rows, min_stations=2):
    by_name = defaultdict(set)
    name_sales = defaultdict(list)
    for r in rows:
        nm = (r.get("Name") or "").strip()
        if not nm:
            continue
        by_name[nm].add(r["station"])
        name_sales[nm].append((r["station"], safe_float(r.get("SaleCount"))))
    recurring = [(n, sts) for n, sts in by_name.items() if len(sts) >= min_stations]
    if not recurring:
        return "_No category appears in multiple stations_"
    recurring.sort(key=lambda x: -len(x[1]))
    lines = [f"### 跨站点出现 ≥ {min_stations} 次的类目（按出现站数）",
             "",
             "| Category | Stations | Count |",
             "|---|---|---|"]
    for nm, sts in recurring[:30]:
        lines.append(f"| {nm[:40]} | {', '.join(sorted(sts))} | {len(sts)} |")
    return "\n".join(lines)


def cross_station_sale_compare(rows, top_n=15):
    """Top recurring categories, with per-station sale comparison."""
    by_name = defaultdict(dict)
    for r in rows:
        nm = (r.get("Name") or "").strip()
        if not nm:
            continue
        by_name[nm][r["station"]] = safe_float(r.get("SaleCount"))
    recurring = {n: sts for n, sts in by_name.items() if len(sts) >= 3}
    if not recurring:
        return "_No category with ≥3 stations_"
    sorted_cats = sorted(recurring.keys(),
                         key=lambda n: -max(recurring[n].values()))[:top_n]
    stations = sorted({s for sts in recurring.values() for s in sts.keys()})
    lines = [f"### Top 跨站类目销量对比 (SaleCount，按 max)",
             "",
             "| Category | " + " | ".join(stations) + " |",
             "|" + "---|" * (len(stations) + 1)]
    for nm in sorted_cats:
        row = [nm[:30]]
        for st in stations:
            v = recurring[nm].get(st, 0)
            row.append(f"{int(v):,}" if v else "—")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def china_seller_breakdown(rows):
    sections = []
    by_station = defaultdict(list)
    for r in rows:
        by_station[r["station"]].append(r)
    for st in sorted(by_station.keys()):
        items = by_station[st]
        cn_sellers = [r for r in items if safe_float(r.get("SolderNumberCN")) > 0]
        if not cn_sellers:
            continue
        cn_count = len(cn_sellers)
        cn_rate_sum = sum(safe_float(r.get("SolderRateCN")) for r in items) / len(items)
        cn_sale_sum = sum(safe_float(r.get("SolderSaleCountRateCN")) for r in items) / len(items)
        sections.append(f"| {st} | {cn_count}/{len(items)} | {cn_rate_sum:.1f}% | {cn_sale_sum:.1f}% |")
    if not sections:
        return "_No CN seller data_"
    header = "| Station | CN Categories | CN Rate Avg | CN Sale Rate Avg |\n|---|---|---|---|"
    return header + "\n" + "\n".join(sections)


def amz_fba_breakdown(rows):
    sections = []
    by_station = defaultdict(list)
    for r in rows:
        by_station[r["station"]].append(r)
    for st in sorted(by_station.keys()):
        items = by_station[st]
        fba_avg = sum(safe_float(r.get("AmzFbaRate")) for r in items) / len(items)
        ebc_avg = sum(safe_float(r.get("EbcRate")) for r in items) / len(items)
        fbm_sum = sum(safe_float(r.get("FBMCount")) for r in items)
        haul = sum(1 for r in items if str(r.get("AmazonHaul", "")).lower() in ("true", "1", "yes"))
        sections.append(f"| {st} | {fba_avg:.1f}% | {ebc_avg:.1f}% | {int(fbm_sum):,} | {haul} |")
    if not sections:
        return "_No FBA data_"
    header = "| Station | FBA Avg | EBC Avg | FBM Sum | AmazonHaul Cat |\n|---|---|---|---|---|"
    return header + "\n" + "\n".join(sections)


def profit_tariff_breakdown(rows):
    sections = []
    by_station = defaultdict(list)
    for r in rows:
        by_station[r["station"]].append(r)
    for st in sorted(by_station.keys()):
        items = by_station[st]
        gpm_avg = sum(safe_float(r.get("GrossProfitMargin")) for r in items) / len(items)
        tariff_avg = sum(safe_float(r.get("TariffValueNum")) for r in items) / len(items)
        cpc_avg = sum(safe_float(r.get("CPCAvgPrice")) for r in items) / len(items)
        add_rate = sum(safe_float(r.get("AddRate")) for r in items) / len(items)
        sections.append(f"| {st} | {gpm_avg:.1f}% | {tariff_avg:.1f}% | {cpc_avg:.2f} | {add_rate:.1f}% |")
    if not sections:
        return "_No profit data_"
    header = "| Station | GrossProfit | Tariff | CPC Avg | AddRate |\n|---|---|---|---|---|"
    return header + "\n" + "\n".join(sections)


def new_product_trend(rows):
    sections = []
    by_station = defaultdict(list)
    for r in rows:
        by_station[r["station"]].append(r)
    for st in sorted(by_station.keys()):
        items = by_station[st]
        np_avg = sum(safe_float(r.get("NewProductCount")) for r in items) / len(items)
        ns_avg = sum(safe_float(r.get("NewSalesVolumeRate")) for r in items) / len(items)
        opc_avg = sum(safe_float(r.get("OneMonthProductCount")) for r in items) / len(items)
        tpc_avg = sum(safe_float(r.get("ThreeMonthProductCount")) for r in items) / len(items)
        spc_avg = sum(safe_float(r.get("SixMonthProductCount")) for r in items) / len(items)
        sections.append(
            f"| {st} | {np_avg:.0f} | {ns_avg:.1f}% | {opc_avg:.0f} | {tpc_avg:.0f} | {spc_avg:.0f} |"
        )
    if not sections:
        return "_No new product data_"
    header = "| Station | NewCat Avg | NewSale% | 1M Prod | 3M Prod | 6M Prod |\n|---|---|---|---|---|---|"
    return header + "\n" + "\n".join(sections)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--markets", required=True, help="CSV from fetch_markets.py")
    p.add_argument("--out-md", required=True, help="Markdown report path")
    args = p.parse_args()

    rows = load_rows(args.markets)
    if not rows:
        print("no rows loaded", file=sys.stderr)
        sys.exit(1)
    stations = sorted({r["station"] for r in rows})
    sample = len(rows)
    fields_per_row = len(rows[0].keys()) if rows else 0
    n_stations = len(stations)

    report = f"""# sorftime 多站点选市场综合报告（251 字段全维度）

> Auto-generated by `analyze.py` for rich market data.
> 数据源：sorftime `/home/choosemarketblock` 的 `marketBoard.items`（20 类目/站，{fields_per_row} 字段/类目）。

**抓取时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')} |
**样本量**: {sample} 条类目行 | **站点数**: {n_stations} |
**站点列表**: {", ".join(stations) or "无"}

> 这是 4 个 sub-modes 中的 `multi`（多维度选市场）模式，14 站点部分覆盖。
> 完整 80 条/站需要 4 个 sub-mode 都跑（multi/buyer/new/lowprice）。

---

## 一、站点汇总（按品牌、销量、FBA 比例）

{station_summary(rows)}

---

## 二、各站点 Top 10 销量类目

{top_per_station(rows, 10)}

---

## 三、跨站点重复类目

{cross_station_categories(rows, min_stations=2)}

---

## 四、跨站类目销量对比 (Top 15)

{cross_station_sale_compare(rows, top_n=15)}

---

## 五、中国卖家密度

{china_seller_breakdown(rows)}

---

## 六、AMZ FBA / EBC / FBM 分布

{amz_fba_breakdown(rows)}

---

## 七、利润/关税/CPC 概况

{profit_tariff_breakdown(rows)}

---

## 八、新品增长趋势

{new_product_trend(rows)}

---

## 九、行动建议（模板）

| 角色 | 建议 |
|---|---|
| **跨境新手** | 选 FBA 占比 >70% 且 中国卖家比例 <30% 的市场（低竞争、平台扶持） |
| **成熟品牌** | 跨站重复类目中：先看 max(SaleCount) 高的站做主战场，再覆盖 30% 以下的次战场 |
| **新卖家** | 找 NewProductCount 高 + GrossProfitMargin 高的类目（新品有机会 + 利润空间大） |
| **关税敏感** | 避开 TariffValueNum 高的类目（特别是 DE/FR/IT/ES），优先 AE/SA/JP 低关税区 |

---

## 报告复现命令

```bash
python <path-to-skill>/scripts/fetch_all14.py \\
    --stations US,GB,DE,FR,IN,CA,JP,ES,IT,MX,AE,AU,BR,SA \\
    --out data/markets_14sites.csv
python <path-to-skill>/scripts/analyze.py \\
    --markets data/markets_14sites.csv \\
    --out-md reports/markets_14sites.md
```

`<path-to-skill>` = `.claude/skills/sorftime-market` for project install.

**数据说明**：

- 每条类目有 246 字段（CSV 总 251 列含 station/site_id/sub_mode 元数据）
- 字段涵盖：价格/销量/品牌/卖家/评论/星级/FBA/低价商品/关税/利润/CPC/趋势/竞争/中国卖家比例等
- 失败站：部分站点可能因登录态或地理限制返回 0 数据（`itemsLen: 0`）。通常 IN/CA/MX/AU/SA 较常见。
"""
    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote report → {out}")


if __name__ == "__main__":
    main()
