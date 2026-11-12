# Proshop GPU source verification — milestone 1

Verified on 2026-11-11 with identified BuildWise requests, two-second delays and
robots checks. Scope: the supplied GPU category, its second page and two supplied
product pages. No adapter, registry entry, collection run, catalogue refresh or
normalisation change is included in this milestone.

## Requests and robots rules

Sources:

- https://www.proshop.fi/robots.txt
- https://www.proshop.fi/Naeytoenohjaimet
- https://www.proshop.fi/Naeytoenohjaimet?pn=2
- https://www.proshop.fi/Naeytoenohjaimet/ASUS-GeForce-RTX-5090-ROG-Astral-OC-32GB-GDDR7-RAM-Naeytoenohjaimet/3331069
- https://www.proshop.fi/Naeytoenohjaimet/GIGABYTE-GeForce-RTX-5070-Ti-WindForce-3-OC-16GB-GDDR7-RAM-Naeytoenohjaimet/3331106

All four HTML sources returned usable server-rendered HTML. No JavaScript,
internal API, browser session or account was needed. This establishes feasibility
for these URLs, not permission to crawl every route or a guaranteed request rate.

The wildcard user-agent group restricts query URLs with `Disallow: /*?*` and
explicitly permits `Allow: /*?pn=`. The captured category/product paths have no
query, and the only queried page fetched here uses `?pn=2`. No prohibited query
examples were requested. No crawl-delay or request-rate was published in this
snapshot; keep the shared delay policy and recheck robots rules on future runs.

**Shared-fetcher gap:** the current `urllib.robotparser` integration returns true
for local checks of both permitted `?pn=2` and restricted examples `?page=2` and
`?sort=price`. Its handling of these wildcard rules must be corrected before
broader Proshop requests. Passing the current checker alone is insufficient.
Keep the robots snapshot as a regression case; never solve this by disabling
robots checks. This milestone does not alter shared fetching behaviour.

## Category collection

- Pagination links use `pn`, not `page`: page 1 has no query, page 2 is `?pn=2`.
- Listings are scoped to `#products > li.site-productlist-item`.
- Name/link: `a.site-product-link` and its `h2`.
- Retailer listing ID: `input[name="productId"]` value, matching the URL suffix.
- Displayed EUR price including VAT: `.priceContainer .site-currency-lg`.
- A second parenthesised amount is shown separately; do not parse it as the
  current consumer price. Do not take the first arbitrary price on the page.
- `#product-count` published 489 products in this snapshot. It is historical data,
  not a constant or an adapter page-ending rule.

The first two pages each contained 25 named, identified and priced cards: 50
unique listing IDs, no overlap. Both supplied products appeared on page 1. Their
category prices independently matched their product JSON-LD offer prices.
The other 48 category prices were checked for parseability, not independently
validated through 48 extra product requests.

Page 1 included two DEMO listings with IDs `3203171d` and `3482347d`. The `d`
suffix, DEMO title and badge are meaningful evidence. Preserve listing IDs as
strings, retain the original title, and never remove a suffix to merge with a
new-product listing. Initial catalogue condition policy must be explicit before
publishing: filtering DEMO items or representing them separately must not be
silent. Milestone 1 records them without changing the existing raw schema.

**Retry gap:** the existing retry worker reconstructs page numbers from `page=`.
Proshop uses `pn=`. The adapter must generate its own pagination URLs, and retry
must retain the exact failed page request or use adapter-owned page context.
Do not append `page=2`, which also falls outside the verified robots allowance.

## Product identity and prices

The two product pages expose JSON-LD `Product` objects and labelled identity rows:

| Retailer ID (`sku`) | Manufacturer part number (`mpn`) | EAN (`gtin13`) |
| --- | --- | --- |
| 3331069 | 90YV0LW0-M0NA00 | 4711387890288 |
| 3331106 | GV-N507TWF3OC-16GD | 4719331355579 |

`external_id` should identify the retailer listing; it is not a BuildWise component
ID, manufacturer part number or cross-retailer matching key. MPN/EAN evidence is
saved in the fixtures for later identity work; do not overload `external_id` or
invent schema changes as part of this source audit.

JSON-LD `offers` contains the current product URL, EUR currency, price, condition
and availability. For product-price verification, scope to that Product object
and confirm its SKU/URL; displayed current price is also available in
`.site-product-stock-price-buy .site-currency-wrapper .site-currency-attention`.
Related variants, accessories and an ex-VAT amount have other prices on the page.
One product's `og:url` exposed a `web8.proshop.fi` host: keep the requested public
`www.proshop.fi` URL or verified offer URL rather than following that metadata.
No additional hosts were requested or approved by this audit.

## Specification layout and mapping candidates

Use `#accordionPanel_specs #specItemsAccordion`. Each specification row has
`.specItemTitle` and `.specItemValue`, with `.sectionTitle` group headings.
Keep the group context: `Muisti / Koko` is memory capacity, not product dimensions.
Identity/general rows are in `#accordionPanel_general`, and must not be mixed with
accessory specifications or shipping measurements.

Verified examples:

| Source field | ASUS 3331069 | GIGABYTE 3331106 | Candidate canonical field |
| --- | --- | --- | --- |
| Muisti / Koko | 32 Gt | 16 Gt | vram_gb |
| Muisti / Tekniikka | GDDR7 SDRAM | GDDR7 SDRAM | memory_type |
| Muisti / Väyläleveys | 512 bittiä | 256-bit | memory_bus_bit |
| Vaadittava virtalähde | 1000 W | 750 W | recommended_psu_w |
| Syvyys | 35.76 cm | 30.4 cm | length_mm: 357.6 / 304 |
| Leveys | 7.6 cm | 5 cm | width_mm: 76 / 50 |
| Korkeus | 14.93 cm | 12.6 cm | height_mm: 149.3 / 126 |

The depth-to-card-length mapping is corroborated by both supplied product summaries.
Do not generalise GPU axis meaning to other component categories. Match labels
exactly so `Lähetyssyvyys` does not become GPU length. A PSU recommendation is not
GPU power consumption/TDP. Missing fields remain null; conflicting evidence is
reported rather than guessed. These are mapping candidates for milestone 3,
not an implemented specification parser.

## Saved evidence and next milestone

`tests/fixtures/proshop/` contains reduced source excerpts, robots rules, source
hashes/capture times and an observation manifest. Full temporary responses are in
`/tmp/buildwise-proshop-m1/cache/` and are not committed. Excerpts omit scripts,
tracking/session tokens, images and marketing descriptions while preserving card
boundaries, VAT/related-price distinctions, DEMO evidence and specification rows.

Milestone 1 verification checks: 25 cards per page; 50 distinct IDs; all 50 prices
parse; two category/product price cross-checks; ID/MPN/EAN extraction; grouped
specification rows; snapshot checksums and absence of form token inputs. No
scraper test suite or catalogue export was run for these source-only changes.

Milestone 2 should add GPU price collection behind the shared adapter contract,
use `pn` URLs, resolve wildcard robots handling, and define DEMO reporting. Retrying
exact category requests must be addressed before Proshop category retries are
advertised. Specifications remain milestone 3; no Proshop CLI command is active yet.


## Milestone 2 follow-up

The source findings above remain historical. The GPU adapter is now registered.
Shared robots matching uses Protego, and category retries preserve exact URLs and
page metadata. DEMO cards are excluded with explicit per-run reporting. GPU
specifications remain milestone 3. These changes are verified offline against the
saved source excerpts; milestone 1's snapshots and checksums are unchanged.


## Milestone 3 follow-up

The grouped GPU specification parser is now available through the shared `specs`
command and refresh planning. The two captured product pages each verify nine
canonical fields, including cm-to-mm dimensions and correctly scoped memory
values. Power consumption, slot width and connectors remain unknown. Shipping
rows and general/accessory sections are excluded from these mappings. Checks use
the existing fixtures and temporary output; the original capture evidence is
unchanged. No additional live requests are part of milestone 3.
