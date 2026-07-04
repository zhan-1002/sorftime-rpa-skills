"""Multi-station keyword trend analysis report.

Reads the per-keyword CSV from fetch_keywords.py (20 keywords × N stations)
and produces a Markdown report with:
  - Cross-station leaderboards (highest CPC, biggest growth, etc.)
  - Per-station top keywords
  - Site-by-site competitive landscape
"""
import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_rows(path):
    with Path(path).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keywords", required=True,
                   help="Per-keyword CSV from fetch_keywords.py")
    p.add_argument("--out-md", required=True, help="Markdown report path")
    args = p.parse_args()

    rows = load_rows(args.keywords)
    if not rows:
        print("error: empty CSV", file=sys.stderr)
        sys.exit(2)

    # Group by station
    by_station = defaultdict(list)
    for r in rows:
        st = r.get("station", "?")
        by_station[st].append(r)

    stations = sorted(by_station.keys())
    station_name = {}
    for r in rows:
        if r.get("station") and r.get("station_name"):
            station_name[r["station"]] = r["station_name"]

    # Per-station stats
    station_stats = []
    for st in stations:
        items = by_station[st]
        cpcs = [to_float(r.get("cpc_storm")) for r in items]
        cpcs = [c for c in cpcs if c is not None]
        growths = [to_float(r.get("growth_3m")) for r in items]
        growths = [g for g in growths if g is not None]
        comp = [to_float(r.get("competitor_count")) for r in items]
        comp = [c for c in comp if c is not None]
        prices = [to_float(r.get("avg_price")) for r in items]
        prices = [p for p in prices if p is not None]
        station_stats.append({
            "station": st,
            "station_name": station_name.get(st, ""),
            "n": len(items),
            "avg_cpc": sum(cpcs)/len(cpcs) if cpcs else 0,
            "max_cpc": max(cpcs) if cpcs else 0,
            "avg_growth_3m": sum(growths)/len(growths) if growths else 0,
            "max_growth_3m": max(growths) if growths else 0,
            "avg_competitors": sum(comp)/len(comp) if comp else 0,
            "avg_price": sum(prices)/len(prices) if prices else 0,
        })

    # Cross-station top CPC
    all_with_cpc = [r for r in rows if to_float(r.get("cpc_storm")) is not None]
    top_cpc = sorted(all_with_cpc, key=lambda r: -to_float(r.get("cpc_storm")))[:15]

    # Top growth (3m)
    all_with_g = [r for r in rows if to_float(r.get("growth_3m")) is not None]
    top_growth = sorted(all_with_g, key=lambda r: -to_float(r.get("growth_3m")))[:15]

    # Most competitive (highest competitor_count)
    all_with_comp = [r for r in rows if to_float(r.get("competitor_count")) is not None]
    top_comp = sorted(all_with_comp, key=lambda r: -to_float(r.get("competitor_count")))[:15]

    # Cross-station keyword match (same name across stations)
    name_to_stations = defaultdict(list)
    for r in rows:
        n = r.get("name", "").strip().lower()
        if n:
            name_to_stations[n].append(r)
    cross_station = [(n, items) for n, items in name_to_stations.items()
                     if len({r.get("station") for r in items}) >= 2]
    cross_station.sort(key=lambda x: -len(x[1]))

    # Build report
    today = datetime.now().strftime('%Y-%m-%d')
    lines = []
    lines.append(f"# sorftime 多站点热门关键词趋势报告")
    lines.append("")
    lines.append(f"> 自动生成。读取 `fetch_keywords.py` 的 per-keyword CSV。")
    lines.append("")
    lines.append(f"**生成时间**: {today} | "
                 f"**站点数**: {len(stations)} | "
                 f"**关键词总数**: {len(rows)} | "
                 f"**每站**: 20 个热门词")
    lines.append("")
    lines.append("> 选关键词 page 默认加载 20 个该站点的热门词，"
                 f"无需类目选择。详细架构见 SKILL.md。")
    lines.append("")

    # Section 1: per-station overview
    lines.append("---")
    lines.append("")
    lines.append("## 一、各站点概览")
    lines.append("")
    lines.append("| 站点 | 站名 | 关键词数 | 平均 CPC | 最高 CPC | 平均 3 月增长 | 最高 3 月增长 | 平均竞品数 | 均价 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in station_stats:
        lines.append(
            f"| {s['station']} | {s['station_name']} | {s['n']} | "
            f"${s['avg_cpc']:.2f} | ${s['max_cpc']:.2f} | "
            f"{s['avg_growth_3m']:+.1f}% | {s['max_growth_3m']:+.1f}% | "
            f"{s['avg_competitors']:,.0f} | ${s['avg_price']:.0f} |"
        )
    lines.append("")

    # Section 2: top CPC across all stations
    lines.append("---")
    lines.append("")
    lines.append("## 二、全站 CPC Top 15（最贵关键词）")
    lines.append("")
    lines.append("| 站点 | 关键词 | 排名 | 平均价 | 平均分 | 竞品数 | 3 月增长 | CPC Storm |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in top_cpc:
        lines.append(
            f"| {r.get('station','')} | {r.get('name','')} | "
            f"{r.get('rank','')} | ${r.get('avg_price','')} | "
            f"{r.get('avg_score','')} | {r.get('competitor_count','')} | "
            f"{r.get('growth_3m','')}% | ${r.get('cpc_storm','')} |"
        )
    lines.append("")

    # Section 3: top growth
    lines.append("---")
    lines.append("")
    lines.append("## 三、全站 3 月增长 Top 15（最热门）")
    lines.append("")
    lines.append("| 站点 | 关键词 | 3 月增长 | 6 月增长 | 12 月增长 | 竞品数 | 品牌数 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in top_growth:
        lines.append(
            f"| {r.get('station','')} | {r.get('name','')} | "
            f"{r.get('growth_3m','')}% | {r.get('growth_6m','')}% | "
            f"{r.get('growth_12m','')}% | {r.get('competitor_count','')} | "
            f"{r.get('brand_count','')} |"
        )
    lines.append("")

    # Section 4: most competitive
    lines.append("---")
    lines.append("")
    lines.append("## 四、全站竞品数 Top 15（红海）")
    lines.append("")
    lines.append("| 站点 | 关键词 | 竞品数 | 品牌数 | 平均价 | 均价增长率 3 月 |")
    lines.append("|---|---|---|---|---|---|")
    for r in top_comp:
        lines.append(
            f"| {r.get('station','')} | {r.get('name','')} | "
            f"{r.get('competitor_count','')} | {r.get('brand_count','')} | "
            f"${r.get('avg_price','')} | {r.get('growth_3m','')}% |"
        )
    lines.append("")

    # Section 5: cross-station keywords
    lines.append("---")
    lines.append("")
    lines.append("## 五、跨站点共现关键词（同时在多站热门）")
    lines.append("")
    if cross_station:
        lines.append(f"共 **{len(cross_station)}** 个关键词在 2+ 站点同时出现：")
        lines.append("")
        lines.append("| 关键词 | 出现站点数 | 站点列表 |")
        lines.append("|---|---|---|")
        for name, items in cross_station[:30]:
            sts = sorted({r.get("station", "?") for r in items})
            lines.append(f"| {name} | {len(sts)} | {', '.join(sts)} |")
    else:
        lines.append("_无跨站点共现词_")
    lines.append("")

    # Section 6: per-station top 5
    lines.append("---")
    lines.append("")
    lines.append("## 六、各站点 Top 5（按竞品数）")
    lines.append("")
    for st in stations:
        items = by_station[st]
        items_sorted = sorted(
            [r for r in items if to_float(r.get("competitor_count")) is not None],
            key=lambda r: -to_float(r.get("competitor_count"))
        )[:5]
        if not items_sorted:
            continue
        sname = station_name.get(st, st)
        lines.append(f"### {st} {sname}")
        lines.append("")
        lines.append("| 排名 | 关键词 | 竞品数 | 品牌数 | 平均价 | CPC Storm | 3 月增长 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in items_sorted:
            lines.append(
                f"| {r.get('rank','')} | {r.get('name','')} | "
                f"{r.get('competitor_count','')} | {r.get('brand_count','')} | "
                f"${r.get('avg_price','')} | ${r.get('cpc_storm','')} | "
                f"{r.get('growth_3m','')}% |"
            )
        lines.append("")

    # Section 7: notes
    lines.append("---")
    lines.append("")
    lines.append("## 七、数据说明")
    lines.append("")
    lines.append("- **数据源**: `/home/choosekeyword` 页面的 `keywordData.listData` (20 个默认热门词)")
    lines.append("- **每站 20 条**: 默认页面大小，分类页面可显示更多")
    lines.append("- **刷新周期**: sorftime 通常每周更新一次（每周一批次）")
    lines.append("- **不需选类目**: 这是与 brand/seller 页面的关键区别 — keyword 默认就加载")
    lines.append("- **完整字段**: 见 `data/keywords_3sites.csv` 原始数据（24+ 列）")
    lines.append("")

    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote report → {out}")


if __name__ == "__main__":
    main()
