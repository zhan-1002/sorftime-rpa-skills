---
name: sorftime-1688-compare
description: Amazon-to-1688 price comparison pipeline. Given an Amazon ASIN or product image URL, searches 1688.com via image search for matching suppliers, extracts pricing/supplier info, and computes FBA profit estimates. US station only.
---

# sorftime-1688-compare

Amazon → 1688 supplier comparison skill. Finds 1688 suppliers for Amazon products via image-based reverse search.

## Workflow

1. `check_login(session)` — verify 1688 is logged in, prompt user if not
2. `ensure_1688_page(session)` — navigate to `s.1688.com`
3. `upload_image(image_url, session)` — download image, inject via DataTransfer into file input
4. `click_search(session)` — click `.search-btn` to trigger image search
5. `extract_products(session, max_items)` — parse product cards for title/price/supplier/offerId
6. `write_csv(path, rows)` — save to CSV with detail links

## Quick start

```bash
# Search by Amazon image URL
python scripts/fetch_1688.py --image-url "https://m.media-amazon.com/images/I/XXXXX.jpg" --out data/1688_results.csv

# Generate supplier comparison with FBA profit
python scripts/analyze.py --results data/1688_results.csv --amz-price 8.99 --out-md reports/1688_report.md
```

## Requirements

- **Kimi WebBridge daemon** running and extension connected
- **1688.com login** in the same browser profile (manual, one-time)
- Python 3.10+ (no third-party packages)

## Output

Each CSV row = one 1688 supplier listing:

| Field | Description |
|---|---|
| `title` | Product title from 1688 listing |
| `price` | Wholesale price with tier info |
| `supplier` | Supplier/company name |
| `offer_id` | 1688 offer ID |
| `detail_url` | Constructed detail page link |
| `image_url` | Amazon image URL used for search |

## CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--image-url` | required (or --asin) | Amazon product image URL |
| `--out` | required | CSV output path |
| `--sleep` | 10.0s | Wait after page load |
| `--max-items` | 10 | Max results to extract |

## Architecture note

1688 image search requires manual login (one-time). The `check_login()` guard detects redirects to `login.taobao.com` and prompts the user. The login cookie persists in the WebBridge browser profile across sessions.

Image upload uses `fetch()` → `File()` → `DataTransfer` → `fileInput.dispatchEvent('change')` pattern, bypassing the file system dialog.

## See also

- `scripts/common.py` — WebBridge helpers, login check, page interaction
- `scripts/fetch_1688.py` — main CLI pipeline
- `scripts/analyze.py` — supplier comparison + FBA profit report
- `references/api_notes.md` — DOM structure, known selectors, limitations
