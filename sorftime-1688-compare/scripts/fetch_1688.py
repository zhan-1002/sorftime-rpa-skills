"""Fetch 1688 suppliers for an Amazon product via image search.

Usage:
    python fetch_1688.py --image-url "https://m.media-amazon.com/.../XXXXX.jpg" --out data/results.csv
"""
import argparse
import io
import sys
import time
from pathlib import Path

# Fix GBK encoding issues on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Allow running from skill dir or cwd
try:
    from common import (
        ensure_1688_page, upload_image, check_upload_state,
        click_search, extract_products, write_csv, DEFAULT_SESSION
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import (
        ensure_1688_page, upload_image, check_upload_state,
        click_search, extract_products, write_csv, DEFAULT_SESSION
    )


def search(image_url, session=None, sleep_after=10.0, max_items=10):
    """Run the full 1688 image search pipeline.

    Args:
        image_url: Amazon product image URL
        session: WebBridge session name
        sleep_after: seconds to wait after page load
        max_items: max results to extract

    Returns:
        list of product dicts, or dict with 'error' key
    """
    if session is None:
        session = DEFAULT_SESSION

    # Step 1: Navigate
    print(f"[1/4] Opening 1688 image search...")
    login_state = ensure_1688_page(session, sleep_after=sleep_after)

    if not login_state.get("logged_in"):
        print(f"ERROR: {login_state.get('error', 'Login required')}")
        return login_state

    # Step 2: Upload image
    print(f"[2/4] Uploading image: {image_url[:80]}...")
    upload_result = upload_image(image_url, session)

    if isinstance(upload_result, dict) and upload_result.get("err"):
        return {"error": f"Image upload failed: {upload_result['err']}"}
    if isinstance(upload_result, dict) and upload_result.get("_error"):
        return {"error": f"WebBridge error during upload: {upload_result['_error']}"}

    file_size = upload_result.get("fileSize", "?")
    print(f"      Image injected ({file_size} bytes)")
    time.sleep(6)

    # Check upload state
    state = check_upload_state(session)
    if not (isinstance(state, dict) and state.get("uploaded")):
        return {"error": "Image upload not detected by 1688 page",
                "state": state}

    # Step 3: Click search
    print(f"[3/4] Triggering image search...")
    click_result = click_search(session)
    print(f"      Clicked: {click_result.get('clicked', 'unknown')}")
    time.sleep(12)

    # Step 4: Extract results
    print(f"[4/4] Extracting product listings...")
    products = extract_products(session, max_items=max_items)
    print(f"      Found: {len(products)} products")

    return products


def main():
    p = argparse.ArgumentParser(
        description="Search 1688 for Amazon product suppliers via image search")
    p.add_argument("--image-url", required=True,
                   help="Amazon product image URL")
    p.add_argument("--out", required=True,
                   help="CSV output path")
    p.add_argument("--session", default=DEFAULT_SESSION,
                   help="WebBridge session name")
    p.add_argument("--sleep", type=float, default=10.0,
                   help="Seconds to wait after page load (default: 10)")
    p.add_argument("--max-items", type=int, default=10,
                   help="Max products to extract (default: 10)")

    args = p.parse_args()

    products = search(
        image_url=args.image_url,
        session=args.session,
        sleep_after=args.sleep,
        max_items=args.max_items
    )

    if isinstance(products, dict) and products.get("error"):
        print(f"FATAL: {products['error']}", file=sys.stderr)
        sys.exit(1)

    if not products:
        print("No products found. Check image URL or 1688 page state.")
        sys.exit(1)

    out_path = write_csv(args.out, products, image_url=args.image_url)
    print(f"\nSaved {len(products)} rows to {out_path}")

    # Print summary
    print(f"\n{'#':<3} {'Price':<22} {'Supplier':<25} {'OfferID':<14}")
    print("-" * 68)
    seen = set()
    for i, p in enumerate(products, 1):
        title = p.get("title", "")
        if title in seen:
            continue
        seen.add(title)
        print(f"{i:<3} {p.get('price', '?')[:20]:<22} "
              f"{p.get('supplier', '?')[:23]:<25} "
              f"{p.get('offer_id', ''):<14}")
        print(f"     {title[:70]}")
        oid = p.get('offer_id', '')
        if oid:
            print(f"     https://detail.1688.com/offer/{oid}.html")


if __name__ == "__main__":
    main()
