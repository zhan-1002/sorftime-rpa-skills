# 1688 Image Search — Technical Notes

## Why DOM-driven?

1688's image search page (s.1688.com) has a file upload workflow that cannot be automated via API. The page expects:

1. A file input (`#img-search-upload`) triggered by user click
2. Or a paste event (`ctrl+v`) with image data or URL
3. The search is triggered by clicking a `.search-btn` element

Browser security prevents programmatic file setting on `<input type="file">`. Our workaround:

## Image Upload Method

```
fetch(image_url) → Blob → File → DataTransfer.items.add(file)
  → fileInput.dispatchEvent('change')
  → 1688 page detects the file and shows "搜索图片" button
  → click('.search-btn')
```

The `fetch()` + `DataTransfer` approach bypasses the file dialog. The `change` event triggers 1688's internal upload handler.

## Key DOM Elements

| Selector | Purpose |
|---|---|
| `#img-search-upload` | File input for image upload |
| `.search-btn` | Search trigger button |
| `.search-image-upload-container` | Parent upload area |
| `[class*="offer"]` | Product listing cards (after search) |
| `a[title]` | Product title links |
| `[class*="price"]` | Price elements |
| `[class*="supplier"]` | Supplier name elements |
| `a[href*="offerId="]` | Links containing offer IDs |

## Results Page URL Pattern

After successful search, the URL changes to:
```
https://air.1688.com/kapp/1688-search/pc-image-search/?tab=imageSearch&imageId=<ID>&imageIdList=<LIST>
```

## Product Detail URL

Standard 1688 offer detail page:
```
https://detail.1688.com/offer/{offer_id}.html
```

## Known Limitations

1. **Login required**: Without login, 1688 redirects to `login.taobao.com`. Cookie persists in WebBridge browser profile.
2. **Image search quality**: 1688 matches by color/shape distribution, not product identity. Results may include visually similar but unrelated products.
3. **No text search fallback**: Currently only image search is implemented. Text keyword search would improve precision for exact product matching.
4. **Single image only**: 1688 supports 6 images, but we only upload 1.
5. **WebBridge only**: No standalone API — requires Kimi WebBridge daemon running locally.
6. **Session isolation**: Each search should use a unique WebBridge session to avoid state contamination.

## Price String Parsing

1688 price strings have variable formats:
```
¥7.8运费8元起1800+件2件起批     → 7.8
¥3.8运费5元起3.9万+件2件起批    → 3.8
¥0.15 10~99个 ¥0.14 ≥100个     → 0.15 (first tier)
```
Regex: `[¥￥]\s*(\d+\.?\d*)` — take the first match as lowest tier price.
