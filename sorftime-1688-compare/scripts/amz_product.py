"""Amazon product page helpers.

DOM-driven extraction of Amazon product info without API keys.
Given an ASIN, navigates to the product page and extracts:
  - Main image URL (for 1688 image search)
  - Product title
  - Price
  - Rating / Reviews count
  - BSR (Best Sellers Rank) if visible
"""
import time

AMAZON_URL = "https://www.amazon.com/dp/{}"


def extract_product(session, asin, sleep_after=8.0):
    """Navigate to an Amazon product page and extract key fields.

    Args:
        session: WebBridge session name
        asin: Amazon ASIN (e.g. B0FGD65LMN)
        sleep_after: seconds to wait for page load

    Returns:
        dict with keys: asin, title, price, rating, reviews, image_url
        or dict with 'error' key on failure
    """
    # Lazy import to avoid circular dependency
    from common import navigate, evaluate

    url = AMAZON_URL.format(asin)
    navigate(url, session)
    time.sleep(sleep_after)

    # Check we landed on a product page
    page_url = evaluate("window.location.href", session)
    if isinstance(page_url, str) and ("captcha" in page_url.lower() or "404" in page_url):
        return {"error": "Amazon blocked or page not found",
                "url": page_url}

    code = """
(function(){
    var result = {};

    // Main image - try multiple selectors
    var imgSelectors = [
        '#landingImage',           // classic
        '#imgTagWrapperId img',    // newer layout
        '.imgTagWrapper img',
        '[data-old-hires]',        // hi-res fallback
        '#main-image-container img',
        '.image-container img'
    ];
    for (var i = 0; i < imgSelectors.length; i++) {
        var el = document.querySelector(imgSelectors[i]);
        if (el) {
            // Prefer hi-res version
            result.image_url = el.getAttribute('data-old-hires') ||
                               el.getAttribute('src') ||
                               el.getAttribute('data-a-dynamic-image');
            if (result.image_url) {
                // data-a-dynamic-image is a JSON map of URL:dimensions
                if (result.image_url.indexOf('{') === 0) {
                    try {
                        var map = JSON.parse(result.image_url);
                        var keys = Object.keys(map);
                        // Pick largest resolution
                        result.image_url = keys[keys.length - 1];
                    } catch(e) { result.image_url = ''; }
                }
            }
            if (result.image_url) break;
        }
    }

    // Title
    var titleEl = document.querySelector('#productTitle, #title, h1[class*=\"title\"]');
    result.title = titleEl ? titleEl.textContent.trim().substring(0, 200) : '';

    // Price
    var priceSelectors = [
        '.a-price .a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        '.a-price-whole',
        '[data-a-size=\"xl\"] .a-price .a-offscreen',
        '.apexPriceToPay .a-offscreen'
    ];
    for (var j = 0; j < priceSelectors.length; j++) {
        var pEl = document.querySelector(priceSelectors[j]);
        if (pEl) {
            var txt = pEl.textContent.trim();
            // Convert "$29.99" to float
            var m = txt.match(/[\\d.]+/);
            if (m) { result.price = parseFloat(m[0]); break; }
        }
    }

    // Rating
    var ratingEl = document.querySelector('#acrPopover .a-icon-alt, .a-icon-alt, [data-hook=\"rating-out-of-text\"]');
    if (ratingEl) {
        var rt = ratingEl.textContent.trim();
        var rm = rt.match(/([\\d.]+)\\s*out/);
        if (rm) result.rating = parseFloat(rm[1]);
    }

    // Reviews count
    var revEl = document.querySelector('#acrCustomerReviewText, [data-hook=\"total-review-count\"]');
    if (revEl) {
        var rv = revEl.textContent.trim().replace(/[^\\d]/g, '');
        if (rv) result.reviews = parseInt(rv);
    }

    result.asin = '""" + asin + """';
    return JSON.stringify(result);
})()
"""
    result = evaluate(code, session)

    if isinstance(result, dict) and result.get("_error"):
        return {"error": str(result["_error"])}

    return result if isinstance(result, dict) else {"error": "failed to parse", "raw": str(result)[:200]}
