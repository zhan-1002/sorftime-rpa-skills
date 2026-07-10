"""
Category filter based on sample-calibrated criteria.

Hard filters (must pass ALL):
  M1: Parent class in allowlist
  M2: Price $12-$50
  M3: Monthly sales > 3000
  M4: Avg reviews < 500
  M5: FBA+self ratio < 40%

Scoring (passed categories only):
  S1: Review barrier (35%) - lower reviews = better
  S2: FBA vacuum    (25%) - lower FBA = better
  S3: New product   (20%) - higher new% = better
  S4: Head concentr (10%) - lower TOP10% = better
  S5: Price profit  (10%) - $20-35 sweetspot

Seasonal products are NOT excluded; they get flagged separately.
"""
import csv, json, sys, io, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ---- CONFIG ----

# Target parent classes (from sample analysis)
PARENT_ALLOWLIST = [
    "Home & Kitchen",
    "Kitchen & Dining",
    "Health & Household",
    "Office Products",
    "Sports & Outdoors",
    "Patio, Lawn & Garden",
]

# Hard filters
HARD_FILTERS = {
    "price_min": 12.0,
    "price_max": 50.0,
    "sales_min": 3000,
    "reviews_max": 500,
    "fba_max": 40.0,      # FBA + self %
}

# Scoring weights
WEIGHTS = {
    "review_barrier": 0.35,
    "fba_vacuum": 0.25,
    "new_product": 0.20,
    "head_conc": 0.10,
    "price_sweetspot": 0.10,
}


def parse_num(val):
    """Parse a numeric value from sorftime string, handling '--' and commas."""
    if val is None or val == '--' or val == '':
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').replace('¥', '').strip())
    except:
        return None


def parse_new_product_ratio(ratio_str):
    """Parse '0.34% / 9.27% / 28.04%' -> (1M%, 3M%, 6M%)."""
    if not ratio_str or ratio_str == '--':
        return None, None, None
    import re
    nums = re.findall(r'(\d+\.?\d*)%', ratio_str)
    if len(nums) >= 3:
        return float(nums[0]), float(nums[1]), float(nums[2])
    return None, None, None


def parse_head_sales(ratio_str):
    """Parse '30.63% / 36.62% / 43.61%' -> (TOP10%, TOP50%, TOP100%)."""
    if not ratio_str or ratio_str == '--':
        return None, None, None
    import re
    nums = re.findall(r'(\d+\.?\d*)%', ratio_str)
    if len(nums) >= 2:
        # First is TOP10
        return float(nums[0]), float(nums[1]) if len(nums) > 1 else None, float(nums[2]) if len(nums) > 2 else None
    return None, None, None


def score_review_barrier(avg_reviews):
    """0-100: lower reviews = higher score."""
    if avg_reviews is None:
        return 50  # unknown
    if avg_reviews <= 50:
        return 100
    if avg_reviews <= 100:
        return 85
    if avg_reviews <= 200:
        return 60
    if avg_reviews <= 500:
        return 30
    return 0


def score_fba_vacuum(fba_pct):
    """0-100: lower FBA = higher score."""
    if fba_pct is None:
        return 50
    # fba_pct is e.g. 13.54 (meaning 13.54%)
    if fba_pct <= 10:
        return 100
    if fba_pct <= 20:
        return 80
    if fba_pct <= 30:
        return 50
    if fba_pct <= 40:
        return 20
    return 0


def score_new_product(new_6m_pct):
    """0-100: higher new product % = higher score."""
    if new_6m_pct is None:
        return 50
    if new_6m_pct >= 25:
        return 100
    if new_6m_pct >= 15:
        return 80
    if new_6m_pct >= 8:
        return 50
    if new_6m_pct >= 3:
        return 20
    return 0


def score_head_conc(top10_pct):
    """0-100: lower TOP10 concentration = higher score."""
    if top10_pct is None:
        return 50
    if top10_pct <= 25:
        return 100
    if top10_pct <= 35:
        return 80
    if top10_pct <= 45:
        return 50
    if top10_pct <= 55:
        return 20
    return 0


def score_price(avg_price):
    """0-100: $20-35 sweetspot."""
    if avg_price is None:
        return 50
    if 20 <= avg_price <= 35:
        return 100
    if 15 <= avg_price < 20 or 35 < avg_price <= 45:
        return 60
    if 12 <= avg_price < 15:
        return 30
    return 10


def is_seasonal_check(distribution_str):
    """Detect seasonal pattern from sales distribution string."""
    if not distribution_str or distribution_str == '--':
        return False
    # If sales concentrated in 2-3 consecutive months, it's seasonal
    import re
    months = re.findall(r'(\d+)月', distribution_str)
    if len(months) <= 4:
        return True
    return False


def filter_and_score(categories):
    """Apply hard filters then score each category.

    Args:
        categories: list of dicts with sorftime-market fields (251 fields)

    Returns:
        dict with 'passed', 'rejected', 'seasonal', 'year_round'
    """
    # Deduplicate by (Name, parent_category)
    seen = set()
    deduped = []
    for cat in categories:
        key = (cat.get('Name', ''), cat.get('parent_category', ''))
        if key not in seen:
            seen.add(key)
            deduped.append(cat)
    categories = deduped

    passed = []
    rejected = []

    for cat in categories:
        name = cat.get('Name', '?')
        parent = cat.get('parent_category', cat.get('ParentCategory', 'Other'))

        # M1: Parent class
        if parent not in PARENT_ALLOWLIST:
            rejected.append(('M1_parent', cat))
            continue

        # M2: Price range
        price = parse_num(cat.get('AveragePrice', ''))
        if price is None or price < HARD_FILTERS['price_min'] or price > HARD_FILTERS['price_max']:
            rejected.append(('M2_price', cat))
            continue

        # M3: Sales
        sales = parse_num(cat.get('SaleCount', cat.get('monthly_sales', '')))
        if sales is None or sales < HARD_FILTERS['sales_min']:
            rejected.append(('M3_sales', cat))
            continue

        # M4: Reviews
        reviews = parse_num(cat.get('AvgComentCount', cat.get('avg_reviews', '')))
        if reviews is not None and reviews > HARD_FILTERS['reviews_max']:
            rejected.append(('M4_reviews', cat))
            continue

        # M5: FBA
        fba = parse_num(cat.get('AmzFbaRate', cat.get('fba_self_ratio', '')))
        if fba is not None and fba > HARD_FILTERS['fba_max']:
            rejected.append(('M5_fba', cat))
            continue

        # ---- PASSED: compute scores ----
        _, _, new_6m = parse_new_product_ratio(
            cat.get('NewProductCount', cat.get('new_product_ratio', '')))
        top10, _, _ = parse_head_sales(
            cat.get('head_sales_ratio', ''))

        s1 = score_review_barrier(reviews)
        s2 = score_fba_vacuum(fba)
        s3 = score_new_product(new_6m)
        s4 = score_head_conc(top10)
        s5 = score_price(price)

        total = (s1 * WEIGHTS['review_barrier'] +
                 s2 * WEIGHTS['fba_vacuum'] +
                 s3 * WEIGHTS['new_product'] +
                 s4 * WEIGHTS['head_conc'] +
                 s5 * WEIGHTS['price_sweetspot'])

        is_seasonal = is_seasonal_check(cat.get('sales_distribution', ''))

        cat['_score'] = round(total, 1)
        cat['_scores'] = {'reviews': s1, 'fba': s2, 'new': s3, 'head': s4, 'price': s5}
        cat['_seasonal'] = is_seasonal
        cat['_price'] = price
        cat['_sales'] = sales
        cat['_reviews'] = reviews
        cat['_fba_pct'] = fba
        cat['_new_6m'] = new_6m
        cat['_top10'] = top10

        passed.append(cat)

    # Sort by score descending
    passed.sort(key=lambda c: c['_score'], reverse=True)

    seasonal = [c for c in passed if c['_seasonal']]
    year_round = [c for c in passed if not c['_seasonal']]

    return {
        'passed': passed,
        'rejected': rejected,
        'seasonal': seasonal,
        'year_round': year_round,
        'reject_counts': {}
    }


def print_report(result):
    """Print filter results."""
    print(f"\n{'='*70}")
    print(f"  FILTER RESULTS")
    print(f"{'='*70}")

    # Reject summary
    from collections import Counter
    reject_reasons = Counter(r[0] for r in result['rejected'])
    print(f"\n  Rejected: {len(result['rejected'])} categories")
    for reason, count in reject_reasons.most_common():
        print(f"    {reason}: {count}")

    print(f"\n  Passed: {len(result['passed'])} categories")
    print(f"    Seasonal:  {len(result['seasonal'])}")
    print(f"    Year-round: {len(result['year_round'])}")

    # Top seasonal
    if result['seasonal']:
        print(f"\n{'='*70}")
        print(f"  TOP SEASONAL CATEGORIES")
        print(f"{'='*70}")
        for i, c in enumerate(result['seasonal'][:10], 1):
            print(f"  {i:2d}. [{c['_score']:.0f}] {c.get('Name','?')[:45]}")
            print(f"       Parent: {c.get('parent_category','?')} | Price: ${c.get('_price','?')} | "
                  f"Sales: {c.get('_sales','?')} | Reviews: {c.get('_reviews','?')} | FBA: {c.get('_fba_pct','?')}%")

    # Top year-round
    if result['year_round']:
        print(f"\n{'='*70}")
        print(f"  TOP YEAR-ROUND CATEGORIES")
        print(f"{'='*70}")
        for i, c in enumerate(result['year_round'][:10], 1):
            print(f"  {i:2d}. [{c['_score']:.0f}] {c.get('Name','?')[:45]}")
            print(f"       Parent: {c.get('parent_category','?')} | Price: ${c.get('_price','?')} | "
                  f"Sales: {c.get('_sales','?')} | Reviews: {c.get('_reviews','?')} | FBA: {c.get('_fba_pct','?')}%")
    print()


if __name__ == "__main__":
    # Quick self-test with dummy data
    print("Category filter ready.")
    print(f"  Target parents: {PARENT_ALLOWLIST}")
    print(f"  Hard filters: {HARD_FILTERS}")
    print(f"  Weights: {WEIGHTS}")
