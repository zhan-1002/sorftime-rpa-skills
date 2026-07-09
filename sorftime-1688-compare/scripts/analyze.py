"""Analyze 1688 search results: supplier comparison + FBA profit estimate.

Usage:
    python analyze.py --results data/1688_results.csv --amz-price 8.99 --out-md reports/compare.md

FBA profit formula (from FBA选品利润计算表):
    profit_per_unit = price*(1 - commission%) - fba_fee - (purchase_cost + shipping) / fx_rate
    margin = profit_per_unit / price * 100
    roi = profit_per_unit * fx_rate / (purchase_cost + shipping) * 100
"""
import argparse
import csv
import sys
from pathlib import Path


# Default FBA parameters (configurable via CLI)
DEFAULTS = {
    "commission": 15,      # Amazon commission %
    "fba_fee": 3.90,       # FBA delivery fee $
    "shipping": 4.00,      # First-mile shipping ¥
    "fx_rate": 6.8,        # USD/CNY exchange rate
    "cpc": 0.65,           # Ad CPC $
    "conv_rate": 15,       # Conversion rate %
    "daily_ad_budget": 8,  # Daily ad budget $
}


def load_results(csv_path):
    """Load 1688 search results from CSV."""
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def parse_price(price_str):
    """Extract the lowest tier price from a 1688 price string.

    Examples: '¥7.8运费8元起1800+件2件起批' -> 7.8
              '¥3.8运费5元起3.9万+件2件起批' -> 3.8
              '¥5.2运费4.35元起2件起批' -> 5.2
    """
    import re
    # Match the first ¥ price number
    m = re.search(r'[¥￥]\s*(\d+\.?\d*)', str(price_str))
    if m:
        return float(m.group(1))
    return None


def calculate_profit(purchase_cost, selling_price, params):
    """Calculate FBA profit metrics.

    Returns dict with: profit_per_unit_cny, profit_per_unit_usd,
                       margin_pct, roi_pct, monthly_profit_cny, monthly_profit_usd.
    """
    commission = params["commission"] / 100
    fx = params["fx_rate"]

    # Profit per unit (from spreadsheet formula B13)
    # = (price - price*commission) - fba_fee - (purchase + shipping) / fx_rate
    discounted = selling_price * (1 - commission)
    cost_usd = (purchase_cost + params["shipping"]) / fx
    profit_usd = discounted - params["fba_fee"] - cost_usd
    profit_cny = profit_usd * fx

    # Margin (B18)
    margin_pct = (profit_usd / selling_price) * 100 if selling_price > 0 else 0

    # ROI (B17)
    total_cost_cny = purchase_cost + params["shipping"]
    roi_pct = (profit_cny / total_cost_cny) * 100 if total_cost_cny > 0 else 0

    # Monthly estimate: ~10 units/day * 30 days
    daily_orders = 10  # conservative estimate
    monthly_profit_usd = profit_usd * daily_orders * 30
    monthly_profit_cny = monthly_profit_usd * fx

    return {
        "profit_per_unit_cny": round(profit_cny, 2),
        "profit_per_unit_usd": round(profit_usd, 2),
        "margin_pct": round(margin_pct, 1),
        "roi_pct": round(roi_pct, 1),
        "monthly_profit_cny": round(monthly_profit_cny, 0),
        "monthly_profit_usd": round(monthly_profit_usd, 0),
    }


def score_supplier(row):
    """Score a supplier by reputation signals embedded in the listing text.

    Signals extracted from price string and title:
      - Repurchase rate (回头率 XX%)
      - Years in business (开店 X年 / 入驻X年)
      - Sales volume (XX件 / XX万+件)
      - Price tier count (more tiers = established seller)

    Returns a score from 0-100. Higher = better.
    """
    score = 50  # baseline
    text = (row.get("price", "") + " " + row.get("supplier", "") +
            " " + row.get("title", ""))
    import re

    # Repurchase rate (回头率)
    rr = re.search(r'回头率\s*(\d+)', text)
    if rr:
        rate = int(rr.group(1))
        score += min(rate // 10, 5)  # +0 to +5 for 0-50%+

    # Years in business
    yrs = re.search(r'(?:开店|入驻)\s*(\d+)\s*年', text)
    if yrs:
        y = int(yrs.group(1))
        score += min(y * 2, 10)  # +2 per year, max +10

    # Sales volume tier
    sales = re.search(r'(\d+\.?\d*)\s*万\+?\s*件', text)
    if sales:
        vol = float(sales.group(1))
        if vol >= 1:
            score += 8   # 1万+ sales
        if vol >= 5:
            score += 5   # 5万+ sales
    else:
        sales2 = re.search(r'(\d+)\+?\s*件', text)
        if sales2:
            vol2 = int(sales2.group(1))
            if vol2 >= 500:
                score += 3
            if vol2 >= 1800:
                score += 5

    # Price has tier info (阶梯价格) = professional seller
    if '≥' in text or '~' in text:
        score += 3

    # Has "先采后付" (buy now pay later) = verified
    if '先采后付' in text:
        score += 3

    # Has "退货包运费" (free returns) = quality assurance
    if '退货包运费' in text:
        score += 2

    return min(score, 100)


def generate_report(rows, selling_price, params):
    """Generate markdown comparison report."""
    lines = []
    lines.append("# 1688 Supplier Comparison & FBA Profit Analysis")
    lines.append("")
    lines.append(f"**Amazon Selling Price**: ${selling_price:.2f}")
    lines.append(f"**FBA Fee**: ${params['fba_fee']:.2f} | "
                 f"**Commission**: {params['commission']}% | "
                 f"**Exchange Rate**: {params['fx_rate']}")
    lines.append("")
    lines.append("## Supplier Rankings")
    lines.append("")
    lines.append("| # | Supplier | 1688 Price | Profit/Unit (¥) | Margin | ROI | Monthly (¥) | Score | Link |")
    lines.append("|---|----------|------------|-----------------|--------|-----|-------------|-------|------|")

    results = []
    for row in rows:
        price_raw = row.get("price", "")
        purchase = parse_price(price_raw)
        if purchase is None:
            continue
        profit = calculate_profit(purchase, selling_price, params)
        rep_score = score_supplier(row)
        results.append({
            "supplier": row.get("supplier", "?"),
            "title": row.get("title", "?"),
            "purchase_price": purchase,
            "offer_id": row.get("offer_id", ""),
            "detail_url": row.get("detail_url", ""),
            "score": rep_score,
            **profit
        })

    # Sort by combined score: profit margin (60%) + reputation (40%)
    results.sort(key=lambda r: r["margin_pct"] * 0.6 + r["score"] * 0.4, reverse=True)

    for i, r in enumerate(results, 1):
        link = r["detail_url"] or f"https://detail.1688.com/offer/{r['offer_id']}.html"
        score_str = f"🟢{r['score']}" if r['score'] >= 70 else (f"🟡{r['score']}" if r['score'] >= 50 else f"🔴{r['score']}")
        lines.append(
            f"| {i} | {r['supplier'][:20]} | ¥{r['purchase_price']:.2f} | "
            f"¥{r['profit_per_unit_cny']:.2f} | "
            f"{r['margin_pct']}% | {r['roi_pct']}% | "
            f"¥{r['monthly_profit_cny']:.0f} | "
            f"{score_str} | "
            f"[link]({link}) |"
        )

    lines.append("")
    lines.append("## Best Candidate")
    if results:
        best = results[0]
        lines.append(f"**{best['supplier']}** — {best['title'][:60]}")
        lines.append("")
        lines.append(f"- Purchase: ¥{best['purchase_price']:.2f}/unit")
        lines.append(f"- Profit: ¥{best['profit_per_unit_cny']:.2f}/unit (${best['profit_per_unit_usd']:.2f})")
        lines.append(f"- Margin: {best['margin_pct']}%")
        lines.append(f"- ROI: {best['roi_pct']}%")
        lines.append(f"- Est. Monthly: ¥{best['monthly_profit_cny']:.0f} (${best['monthly_profit_usd']:.0f})")
        lines.append(f"- Link: {best['detail_url']}")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by sorftime-1688-compare*")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(
        description="Analyze 1688 results with FBA profit calculation")
    p.add_argument("--results", required=True,
                   help="CSV from fetch_1688.py")
    p.add_argument("--amz-price", type=float, required=True,
                   help="Amazon selling price in USD")
    p.add_argument("--out-md", required=True,
                   help="Markdown report output path")
    p.add_argument("--commission", type=float, default=DEFAULTS["commission"],
                   help=f"Amazon commission % (default: {DEFAULTS['commission']})")
    p.add_argument("--fba-fee", type=float, default=DEFAULTS["fba_fee"],
                   help=f"FBA delivery fee $ (default: {DEFAULTS['fba_fee']})")
    p.add_argument("--shipping", type=float, default=DEFAULTS["shipping"],
                   help=f"First-mile shipping ¥ (default: {DEFAULTS['shipping']})")
    p.add_argument("--fx-rate", type=float, default=DEFAULTS["fx_rate"],
                   help=f"Exchange rate (default: {DEFAULTS['fx_rate']})")

    args = p.parse_args()

    rows = load_results(args.results)
    if not rows:
        print(f"No data found in {args.results}", file=sys.stderr)
        sys.exit(1)

    params = {
        "commission": args.commission,
        "fba_fee": args.fba_fee,
        "shipping": args.shipping,
        "fx_rate": args.fx_rate,
    }

    report = generate_report(rows, args.amz_price, params)

    out_path = Path(args.out_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print(f"Report written to {out_path}")
    print(report)


if __name__ == "__main__":
    main()
