# Jimms GPU category regression fixtures

These are reduced, public product-card excerpts from the two GPU category HTML
responses saved on 2026-11-05. Product title, link, SKU, displayed-price markup and
analytics attributes are retained; navigation, pictures, scripts and cart widgets
are omitted. They contain 25 cards per page, 50 distinct products total.

Source URLs:

- https://www.jimms.fi/fi/Product/List/000-00P/komponentit--naytonohjaimet?page=1
- https://www.jimms.fi/fi/Product/List/000-00P/komponentit--naytonohjaimet?page=2

`expected_products.json` uses names, URLs and integer-cent prices from the
independently saved product-page observations. Numeric `external_id` values come from the product URL record ID.
`retailer_sku` values come from the category cards' `.product-box-sku` elements. This cross-check catches use of analytics
prices, which differ from displayed `.price__amount` prices in these responses.

These are historical offline fixtures, not claims about current prices or all
Jimms categories. GPU card parsing is verified; CPU card parsing still needs a
separate fixture check. Tests make no live retailer requests.

Product identity milestone 1 adds product_identity.html and its source manifest.
This reduced GPU metadata block preserves explicit GTIN/MPN and retailer-ID
markup; it does not infer manufacturer identifiers from the displayed SKU.
