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

`collect` only saves observations; `refresh` also normalises and exports. Jimms
discovery runs internally and saves its manifest/report under
`data/discovery/jimms_<category>.json` and `.report.json`. Category and product
requests share one fetcher, preserving robots state and request spacing between
phases. Failure in discovery stops collection before product requests and leaves
an existing manifest intact for the failed category.

Jimms has verified category paths configured for GPU and CPU. For another
category, specify one `--category` with its actual `--url`. `--all` means all
configured categories (GPU/CPU for Jimms; all seven for Datatronic). Repeat
`--category` to select multiple configured categories. `--input` accepts the
existing category/url product manifest instead of categories. `--force` and
`--offline` are mutually exclusive. Cached observations retain their original
cache timestamp.

Refresh retains `--skip-scrape`, `--skip-specs`, `--cold`, `--jimms-input` and
`--jimms-category-url`. Choose `--categories gpu` or `gpu,cpu` when using configured
Jimms discovery; an explicit Jimms URL override requires one category. `--offline`
means normalise/export only; `--skip-scrape` alone can still run Datatronic specs.
`--cold` forces Datatronic specification requests, not Jimms prices.

For isolated runs, collect accepts `--data-dir`. Refresh accepts `--data-dir` and
`--web-output`; normalise accepts `--raw-dir`/`--out`, and export accepts
`--source`/`--target`. The default export still writes the repository's
`web/data/components.json`, which must be committed to reach the deployed site.

## Structure

```text
scraper/
  __main__.py            python3 -m scraper entry point
  cli.py                 command arguments and dispatch
  config.py              project paths and canonical categories
  inputs/                maintained URL manifests and committed examples
  common/                HTTP, robots rules, cache and exact price conversion
  retailers/             retailer selectors, category paths and spec field maps
  workers/
    collection.py        unified retailer collection service
    jimms.py             internal discovery and product-price workers
    datatronic.py        category-price worker
    specifications.py    Datatronic specification collection and checkpoints
  pipeline/              component parsing, normalisation, reports, refresh/export
```

The seven old top-level command scripts have been removed. Implementations remain
in the worker/pipeline packages; import classes from those canonical paths.
Discovery is an internal Jimms phase, not a separate CLI command. Specification
collection remains separate from price collection behind `specs --shop ...`.
Retailer strategies compose the shared PageFetcher; no artificial inheritance
hierarchy or generic selector language is introduced.

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

## Shared raw price-observation contract (version 1)

Both collection workers write through `common/raw_data.py`: `RawProduct` defines
item fields, `RawDocument` defines the source-response envelope, and
`RawDataWriter` validates and saves it. This contract covers price observations
in `data/raw/*.json`, not discovery manifests, run logs or the specification store.

Every new document has the same keys:

| Field | Meaning |
| --- | --- |
| schema_version | `1` for the shared versioned contract |
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

Every item has exactly `name`, `price_cents`, `url`, `external_id`, `extraction`.
Prices are integer euro cents or null; missing retailer IDs stay null.
`extraction` records the parser method (Datatronic listing card or Jimms metadata
selector) and is null when unknown. Retailer-specific extra parser keys are not
persisted outside this common shape.

Datatronic may return many items in one category response. Jimms returns one item
per product response. Their grouping differs naturally, but their envelope/item
schemas and field meanings are now identical. Jimms no longer uses a product
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

This milestone is additive: existing parser functions, CLI behaviour and collection
workers remain unchanged. The CLI still uses the previous Jimms discovery/product
workflow until milestone 2 replaces worker branching with the adapter-driven loop.
