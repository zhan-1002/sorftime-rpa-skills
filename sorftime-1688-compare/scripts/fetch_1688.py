"""Fetch 1688 suppliers for an Amazon product via image or text search.

Usage:
    # By Amazon image URL (image search only)
    python fetch_1688.py --image-url "https://m.media-amazon.com/.../XXXXX.jpg" --out data/results.csv

    # By ASIN (auto-extracts image, then image search)
    python fetch_1688.py --asin B0FGD65LMN --out data/results.csv

    # By ASIN with text keywords (combined search)
    python fetch_1688.py --asin B0FGD65LMN --keywords "窗户贴纸,静电贴" --out data/results.csv

    # Text search only
    python fetch_1688.py --keywords "万圣节窗户贴纸" --out data/results.csv
"""
import argparse
import sys
import time
from pathlib import Path

try:
    from common import (
        ensure_1688_page, upload_image, check_upload_state,
        click_search, extract_products, write_csv, DEFAULT_SESSION,
        combined_search
    )
    from amz_product import extract_product
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import (
        ensure_1688_page, upload_image, check_upload_state,
        click_search, extract_products, write_csv, DEFAULT_SESSION,
        combined_search
    )
    from amz_product import extract_product


def search_by_image(image_url, session, sleep_after=10.0, max_items=10):
    """Run image-only search pipeline.

    Returns list of product dicts, or dict with 'error'.
    """
    print(f"[1/4] Opening 1688 image search...")
    login_state = ensure_1688_page(session, sleep_after=sleep_after)

    if not login_state.get("logged_in"):
        return login_state

    print(f"[2/4] Uploading image: {image_url[:80]}...")
    upload_result = upload_image(image_url, session)

    if isinstance(upload_result, dict) and upload_result.get("err"):
        return {"error": f"Image upload failed: {upload_result['err']}"}
    if isinstance(upload_result, dict) and upload_result.get("_error"):
        return {"error": f"WebBridge error during upload: {upload_result['_error']}"}

    print(f"      Image injected ({upload_result.get('fileSize', '?')} bytes)")
    time.sleep(6)

    state = check_upload_state(session)
    if not (isinstance(state, dict) and state.get("uploaded")):
        return {"error": "Image upload not detected by 1688 page", "state": state}

    print(f"[3/4] Triggering image search...")
    click_result = click_search(session)
    print(f"      Clicked: {click_result.get('clicked', 'unknown')}")
    time.sleep(12)

    print(f"[4/4] Extracting product listings...")
    products = extract_products(session, max_items=max_items)
    for p in products:
        p["search_mode"] = "image"
    print(f"      Found: {len(products)} products")

    return products


def main():
    p = argparse.ArgumentParser(
        description="Search 1688 for Amazon product suppliers")
    # Input: --asin and --image-url are mutually exclusive
    input_group = p.add_mutually_exclusive_group()
    input_group.add_argument("--asin", help="Amazon ASIN (auto-extracts image)")
    input_group.add_argument("--image-url", help="Amazon product image URL")
    # --keywords is always optional (can combine with --asin or stand alone)
    p.add_argument("--keywords", help="Text keywords for 1688 search (comma-separated)")
    p.add_argument("--keywords-file", help="File containing keywords (one per line, UTF-8)")

    # Options
    p.add_argument("--search-mode", default="image",
                   choices=["image", "text", "combined"],
                   help="Search mode: image, text, or combined (default: image)")
    p.add_argument("--out", required=True, help="CSV output path")
    p.add_argument("--session", default=DEFAULT_SESSION,
                   help="WebBridge session name")
    p.add_argument("--sleep", type=float, default=10.0,
                   help="Seconds to wait after page load")
    p.add_argument("--max-items", type=int, default=10,
                   help="Max results per search mode")

    args = p.parse_args()

    # Validate: need at least one input source
    if not args.asin and not args.image_url and not args.keywords:
        p.error("At least one of --asin, --image-url, or --keywords is required")

    # Resolve image_url from --asin if needed
    image_url = args.image_url
    product_info = None

    if args.asin:
        print(f"Extracting product info for ASIN: {args.asin}...")
        prod_session = f"{args.session}_amz"
        product_info = extract_product(prod_session, args.asin, sleep_after=args.sleep)
        if isinstance(product_info, dict) and product_info.get("error"):
            print(f"ERROR extracting product: {product_info['error']}")
            sys.exit(1)

        image_url = product_info.get("image_url", "")
        print(f"  Title: {product_info.get('title', '?')[:80]}")
        print(f"  Price: ${product_info.get('price', '?')}")
        print(f"  Image: {image_url[:80]}...")

    # Keyword processing
    kw_list = []
    if args.keywords_file:
        try:
            with open(args.keywords_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        kw_list.append(line)
        except FileNotFoundError:
            print(f"WARNING: keywords file not found: {args.keywords_file}", file=sys.stderr)
    if args.keywords:
        # Handle possible encoding issues from CLI: try to decode if needed
        raw = args.keywords
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        kw_list.extend([k.strip() for k in raw.split(",") if k.strip()])
    if not kw_list and product_info and product_info.get("title"):
        # Auto-generate keywords from product title
        title = product_info.get("title", "")
        words = [w for w in title.replace(",", " ").split() if len(w) > 2 and w.lower()
                 not in ("and", "the", "for", "with", "set", "pack", "inch", "new")]
        kw_list = [" ".join(words[:4])]

    # Run search
    if args.search_mode == "text" or (not image_url and kw_list):
        # Text-only
        if not kw_list:
            print("ERROR: --keywords required for text search mode")
            sys.exit(1)
        print(f"Text search: {kw_list}")
        results = combined_search(
            image_url="", keywords=kw_list,
            session=args.session, sleep_after=args.sleep,
            max_items=args.max_items
        )
        products = results.get("text_results", [])

    elif args.search_mode == "combined" and image_url and kw_list:
        # Combined: image + text
        print(f"Combined search: image + keywords {kw_list}")
        results = combined_search(
            image_url=image_url, keywords=kw_list,
            session=args.session, sleep_after=args.sleep,
            max_items=args.max_items
        )
        products = results.get("merged", [])

    else:
        # Image-only (default)
        if not image_url:
            print("ERROR: --image-url or --asin required for image search")
            sys.exit(1)
        products = search_by_image(
            image_url=image_url, session=args.session,
            sleep_after=args.sleep, max_items=args.max_items
        )

    if isinstance(products, dict) and products.get("error"):
        print(f"FATAL: {products['error']}", file=sys.stderr)
        sys.exit(1)

    if not products:
        print("No products found.")
        sys.exit(1)

    out_path = write_csv(args.out, products, image_url=image_url or "")
    print(f"\nSaved {len(products)} rows to {out_path}")

    # Summary (ASCII-safe to avoid GBK encoding crashes on Windows terminals)
    def safe(s, n):
        """Truncate to n chars, replace non-ASCII for safe terminal printing."""
        t = str(s)[:n]
        return t.encode('ascii', errors='replace').decode('ascii')

    print(f"\n{'#':<3} {'Mode':<10} {'Price':<22} {'Supplier':<25} {'OfferID':<14}")
    print("-" * 78)
    seen = set()
    for i, prod in enumerate(products, 1):
        title = prod.get("title", "")
        if title in seen:
            continue
        seen.add(title)
        mode = prod.get("search_mode", "?")[:8]
        print(f"{i:<3} {mode:<10} {safe(prod.get('price', '?'), 20):<22} "
              f"{safe(prod.get('supplier', '?'), 23):<25} "
              f"{prod.get('offer_id', ''):<14}")
        print(f"     {safe(title, 70)}")
        oid = prod.get('offer_id', '')
        if oid:
            print(f"     https://detail.1688.com/offer/{oid}.html")


if __name__ == "__main__":
    main()
