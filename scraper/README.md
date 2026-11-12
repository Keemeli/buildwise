# BuildWise data pipeline

Run all commands from the repository root through one entry point:

```sh
python3 -m scraper --help
```

## Commands

```sh
# Discover Jimms category URLs and collect their product-page prices in one run
python3 -m scraper collect --shop jimms --category gpu --pages 2

# Use an explicit category URL instead of the configured path
python3 -m scraper collect --shop jimms --category gpu --url 'https://www.jimms.fi/fi/Product/List/000-00P/komponentit--naytonohjaimet' --pages 2

# Reuse existing Jimms product URLs; discovery is skipped
python3 -m scraper collect --shop jimms --input scraper/inputs/jimms_urls.json

# Datatronic category-card prices through the same interface
python3 -m scraper collect --shop datatronic --category gpu --pages 2

# Read today's cached category and product HTML without network requests
python3 -m scraper collect --shop jimms --category gpu --pages 2 --offline

# Collect specifications where implemented
python3 -m scraper specs --shop datatronic --category gpu --limit 25
python3 -m scraper specs --shop datatronic --offline

# Transform saved data and publish separately when needed
python3 -m scraper normalise
python3 -m scraper export
python3 -m scraper export --check

# Normal collection -> supported specs -> normalisation -> web export
python3 -m scraper refresh --shops jimms,datatronic --categories gpu --pages 2

# Rebuild and publish saved observations without any collection or spec requests
python3 -m scraper refresh --offline

python3 -m unittest discover -s tests -v
```

`collect` saves observations; `refresh` also normalises and exports. Both
retailers now use CollectionWorker and get displayed prices from category pages.
Only explicit adapter ProductRequests trigger product-page price reads. The two
verified Jimms GPU pages yield 50 products from two category responses, plus any
robots.txt request required for an uncached run; no product-page visits are needed.

`--category` selects configured categories; repeat it for multiple categories.
`--all` uses the selected adapter's configuration (seven categories for Datatronic,
GPU/CPU for Jimms). GPU card prices are verified for Jimms; CPU layout still needs
its own fixture validation. Use `--url` with exactly one category to override an
allowed retailer URL. Use `--input` instead of categories to read product-page
requests; the adapter must declare product-price support. Currently Jimms supports
this, while Datatronic explicitly rejects it. Optional manifest fields
`external_id` and `retailer_sku` are retained through follow-up parsing.

`--force` and `--offline` are mutually exclusive. Offline collection reads today's
HTML cache; missing pages fail explicitly. The worker owns one fetcher for the
entire run, so robots state and request spacing are retained across categories and
follow-ups. Collection writes no new discovery manifests: saved
`data/discovery/` files remain usable as manual inputs and are not deleted.

Refresh uses one collection stage per retailer through the same CLI. `--input`
and `--url` can target a single retailer; `--jimms-input` and
`--jimms-category-url` remain legacy aliases at the refresh boundary. `--offline`
means normalise/export only. `--skip-scrape` alone can still run supported
specification stages. `--cold` forces Datatronic specifications, not price reads.

For isolated runs, collect accepts `--data-dir`. Refresh accepts `--data-dir` and
`--web-output`; normalise accepts `--raw-dir`/`--out`, and export accepts
`--source`/`--target`. Default export still writes `web/data/components.json`.

## Structure

```text
scraper/
  __main__.py            python3 -m scraper entry point
  cli.py                 generic collection options and command dispatch
  config.py              project paths and canonical categories
  common/                requests, robots rules, caching and raw-data models
  retailers/
    contracts.py         configuration, capabilities and typed adapter results
    registry.py          lazy retailer factories
    datatronic.py        Datatronic parser and adapter
    jimms.py             Jimms parser and adapter
    datatronic_specs.py  existing specification parser
  workers/
    collection.py        input validation and shared-worker construction
    collection_worker.py adapter-driven loop, follow-ups and run result
    specifications.py    existing Datatronic specification worker
  pipeline/              component parsing, normalisation, reports and refresh
```

The obsolete DatatronicScraper, JimmsCategoryDiscovery and JimmsPriceScraper
collection implementations and their compatibility helpers have been removed.
Retailer-specific price logic belongs in adapters; collection orchestration has
no retailer-name branches. New collection adapters need only a registry entry,
configuration, parsing implementation and tests. Specification generalisation is
a separate milestone; its CLI currently supports Datatronic only.

CollectionResult records pages/products fetched, unique items found, duplicate
URLs skipped, parser issues, failures and status. Results use the common
`data/raw/scrape_runs.jsonl` log. Earlier successful observations are retained
when later pages/products fail. Failed requests and repeated or empty listing
pages return nonzero, stopping refresh. Parser diagnostics (for example a null
Datatronic listing price) remain explicit without introducing a new missing-price
policy in this milestone. Resolved follow-up issues are still retained as
diagnostics. Broader policy/reporting changes remain milestone 3.

## Validation and current limits

Tests cover offline collection for both retailers, integrated Jimms discovery and
price reads, bad arguments, partial failures, robots/cache behaviour, timestamp
selection, parser/report injection and real offline refresh subprocesses. The
CI export check uses only the standard library; scraping dependencies are loaded
only for collection/specification commands.

Specification extraction is currently implemented for Datatronic only. Component
matching remains category/brand/model based, and different retailer titles can
still produce separate components. Data schemas and parsing rules are unchanged.

## URL input files

Keep manually maintained product manifests under `scraper/inputs/`. Copy the
committed example before editing your local list:

```sh
cp scraper/inputs/jimms_urls.example.json scraper/inputs/jimms_urls.json
python3 -m scraper collect --shop jimms --input scraper/inputs/jimms_urls.json
```

The example URL is a placeholder; replace it with an actual product-page URL.
Local JSON lists are ignored, while `*.example.json` files remain commit-ready.
Generated category manifests and reports belong in `data/discovery/` and are
ignored. The previous root-level GPU discovery files have moved to
`data/discovery/jimms_gpu.json` and `data/discovery/jimms_gpu.report.json`, matching
the collector's normal output. To reuse saved discovered links explicitly:

```sh
python3 -m scraper collect --shop jimms --input data/discovery/jimms_gpu.json
```

Raw product observations in `data/raw/` and the normalised catalogue are unchanged.

## Shared raw price-observation contract (version 2)

Both collection workers write through `common/raw_data.py`: `RawProduct` defines
item fields, `RawDocument` defines the source-response envelope, and
`RawDataWriter` validates and saves it. This contract covers price observations
in `data/raw/*.json`, not discovery manifests, run logs or the specification store.

Every new document has the same keys:

| Field | Meaning |
| --- | --- |
| schema_version | `2` for separate retailer record IDs and SKU fields |
| shop / category | Retailer attribution and canonical component category |
| source_type | `category` or `product`, describing the fetched response |
| source_url | URL of that response |
| fetched_at | UTC timestamp from the cached HTML, preserved on offline replay |
| raw_html | Path relative to `--data-dir`, e.g. `raw/html/jimms/...html` |
| origin | `network`, `cache`, or null when a compatibility caller cannot supply it |
| page | Actual listing page number for category responses; null for product responses |
| site_total_products | Published category total when known; otherwise null |
| item_count | Number of entries in `items` |
| items | Products extracted from that response |

Every new item has `name`, `price_cents`, `url`, `external_id`, `retailer_sku`,
and `extraction`.
Prices are integer euro cents or null; missing retailer IDs stay null.
`extraction` records the parser method (Datatronic listing card or Jimms metadata
selector) and is null when unknown. Retailer-specific extra parser keys are not
persisted outside this common shape.

Both retailers return multiple items from category responses. Explicit product
follow-ups return one item per response. Their envelope/item schemas and field
meanings are identical. Jimms no longer uses a product
counter as a pretend page number. `item_count` replaces the old `items_on_page`.

All new filenames follow
`<shop>_<category>_<source_type>_<source URL hash>_<write timestamp>.json`.
Reruns preserve earlier observations rather than overwrite a daily category file.
The observation timestamp remains independent of the filename's write timestamp.

The 106 historical price-observation files (21 Datatronic, 85 Jimms) have been
migrated to version 1. Their filenames are retained to preserve normalisation
read order; new collections use the filename convention above. Original prices,
names, categories, retailer IDs and observation timestamps are unchanged. All HTML
references now use the data-relative convention. Missing historical snapshots are
not refetched or fabricated; the migration audit records 21 missing HTML files.

A verified local backup and checksums are retained under `data/migrations/`.
Backup ZIP files are ignored by Git; audit/migration reports can be committed.
The normaliser and Datatronic specification URL reader still accept unversioned
files for backward compatibility.


## Specification request and failure policy

The Datatronic specification worker uses the same PageFetcher as price
collection: allowed-host validation, robots rules, sequential request spacing
(including after failures), timeouts and cached HTML reads. Existing specification
cache paths under `data/raw/html/specs/datatronic/<date>/` are retained.

A specification pass returns nonzero when any requested page fails, yields no
supported specification fields, or is missing from an offline cache. Successful
items and coverage reports are still saved so partial work is retained. An offline
cache miss leaves previously collected specifications intact. Cached reads and
status-only runs do not request robots.txt or product pages. `--force` refreshes
HTML but never bypasses robots rules. A failed specification stage stops refresh
before normalisation/export.

## Retailer adapter contract — milestone 1

`retailers/contracts.py` defines immutable RetailerConfig/Capabilities and the
RetailerAdapter protocol. Category paths are relative to each retailer's base
URL. Adapters provide category_url, page_url, parse_category and parse_product.
Unsupported categories/operations raise explicit errors. The lazy default registry
in `retailers/registry.py` resolves retailer keys to fresh adapter instances.

Both adapters return CategoryResult: RawProduct observations, ProductRequest
follow-ups, optional category total and ParseIssue diagnostics. Parsing does not
fetch pages or write files. The worker supplies fetch time, origin and HTML path.
A follow-up request is descriptive; returning it does not perform a request.

DatatronicAdapter wraps its existing parser without changing product data or
pagination. Missing prices remain null observations with explicit issues, and
product-page price extraction is declared unsupported. Existing Datatronic spec
support remains in its separate parser/worker.

JimmsAdapter reads displayed card prices from `.price__amount` and SKUs from
`.product-box-sku`, ignoring analytics prices. Missing, invalid or conflicting
prices produce follow-up requests and diagnostics. Product fallback preserves the
card SKU. No category total is invented from the page's JS placeholder.

Two saved GPU pages (50 products) match independently saved product-page prices,
names and URLs. Other category layouts are not verified by this result.

Milestone 2 now connects the adapters through the shared collection worker.
Existing parser functions remain available for parser compatibility; the separate
retailer-specific collection workers have been removed.


## Identifier correction — milestone 1.1

`external_id` means the retailer's internal product record ID, stored as text.
For Datatronic this remains its `data-id-product` value. For Jimms the adapter
extracts the numeric `/fi/Product/Show/<id>/...` URL segment, for example `209432`.
Jimms's displayed `.product-box-sku` value, for example `PRIME-RTX5070-O12G`, is
stored separately as nullable `retailer_sku`. An unknown SKU stays null. Neither
field is a BuildWise-generated ID or proof of a cross-retailer component match.

ProductRequest carries both identifiers through missing-price follow-ups. Jimms
product parsing derives the ID from the validated URL and rejects a conflicting
request ID. The normaliser preserves `retailer_sku` when supplied; historical
listings without it keep their previous shape and values.

New RawDataWriter documents use schema version 2. Readers still accept version 1
and unversioned input. No historical files have been converted by this correction;
legacy identifier values are not silently reinterpreted. The earlier 106-file
migration remains version 1, and a further historical migration is a separate task.

The corrected adapters are connected to collection in milestone 2. Category-card
IDs and SKUs now flow directly to the shared raw writer. Unknown manifest SKU
values stay null; existing files have not been rewritten.


## Milestone 2 validation

The shared worker is tested with a fake third retailer, complete category results,
follow-ups, URL deduplication, partial failures, writer failures and fetcher cleanup.
Both real adapters have offline worker/CLI integration checks. Jimms's 50 saved
GPU observations match independently saved product-page prices, names and URLs,
and retain record IDs/SKUs without product visits. Datatronic pagination preserves
its existing parser fields and category totals without product visits. Shared raw
schema and mixed-retailer normalisation checks pass. No live scraping, historical
migration, database writes or saved catalogue updates are performed by these tests.
