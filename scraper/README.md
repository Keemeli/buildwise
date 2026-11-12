# BuildWise data pipeline

Run all commands from the repository root through one entry point:

```sh
python3 -m scraper --help
```

## Commands

```sh
# Collect displayed Jimms category prices
python3 -m scraper collect --shop jimms --category gpu --pages 2

# Use an explicit category URL instead of the configured path
python3 -m scraper collect --shop jimms --category gpu --url 'https://www.jimms.fi/fi/Product/List/000-00P/komponentit--naytonohjaimet' --pages 2

# Reuse existing Jimms product URLs; discovery is skipped
python3 -m scraper collect --shop jimms --input scraper/inputs/jimms_urls.json

# Datatronic category-card prices through the same interface
python3 -m scraper collect --shop datatronic --category gpu --pages 2

# Read today's cached category and product HTML without network requests
python3 -m scraper collect --shop jimms --category gpu --pages 2 --offline

# Collect specifications through the same worker for either retailer
python3 -m scraper specs --shop datatronic --category gpu --limit 25
python3 -m scraper specs --shop jimms --category gpu --limit 25
python3 -m scraper specs --shop datatronic --offline
python3 -m scraper specs --shop jimms --offline

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
specification stages. `--cold` forces specification refreshes for each selected retailer, not price reads.

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
    datatronic_specs.py  Datatronic labels and data-sheet extraction
    jimms_specs.py       Jimms labels and product-description extraction
  workers/
    collection.py        input validation and shared-worker construction
    collection_worker.py adapter-driven loop, follow-ups and run result
    specifications.py    shared specification collection and checkpoints
  pipeline/              component parsing, normalisation, reports and refresh
```

The obsolete DatatronicScraper, JimmsCategoryDiscovery and JimmsPriceScraper
collection implementations and their compatibility helpers have been removed.
Retailer-specific price logic belongs in adapters; collection orchestration has
no retailer-name branches. New collection adapters need only a registry entry,
configuration, parsing implementation and tests. Specification support uses the
adapter specification-parser factory and capability flag.

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

Specification extraction supports both retailers. Jimms GPU parsing is verified
against saved pages; CPU label conversion has unit coverage but needs real CPU
product-page fixture validation. Component
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
The normaliser and shared specification URL reader still accept unversioned
files for backward compatibility.


## Specification request and failure policy

The shared specification worker uses the same PageFetcher as price
collection: allowed-host validation, robots rules, sequential request spacing
(including after failures), timeouts and cached HTML reads. Existing specification
cache paths under `data/raw/html/specs/datatronic/<date>/` remain readable without
migration. New specification reads reuse the collection cache under
`data/raw/html/<retailer>/<date>/`.

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

## Milestone 3 policy — checkpoint 2 implementation

Identified products with unresolved prices are saved with `price_cents: null`.
When a category adapter requests a product fallback, the worker retains that
category observation in memory until the fallback finishes. Successful recovery
saves the priced product response only. If recovery fails, the null observation
is saved against the original category HTML and its observation timestamp. A
manual product response with readable identity but missing/ambiguous metadata is
also saved with a null price; identity is never invented for failed requests.

A run is `ok`/exit 0 when requested work is resolved, `partial`/exit 1 when some
observations were saved but outcomes remain unresolved, or `failed`/exit 1 when
nothing was saved and work is unresolved. All-null runs are partial. An explicitly
confirmed empty category is successful even when it contains no observations.
Category failures do not prevent other selected categories from being attempted.

CategoryResult can confirm an ending only with `end_of_category=True` and a
nonempty `end_reason`. The Datatronic adapter recognises a published zero total
with its actual listing container. No Jimms ending is guessed from JS placeholders.
Empty pages without evidence and repeated pages stop that category as unresolved.
Coverage records distinguish requested `page_limit`, `confirmed_end` and
`unresolved` stops; a page limit does not claim complete catalogue coverage.

Every collection run has a UUID run_id. Its summary, unresolved/recovered outcomes
and saved raw envelopes carry that ID. Raw schema version 2 accepts this additive
nullable metadata; old files remain readable and are not rewritten. Cached HTML
mtime still determines fetched_at, independently of processing time and run ID.
Raw observation files are written through a temporary file and atomically renamed
so failed writes do not expose partially written JSON to readers.

Run records use report_version 2 in `data/raw/scrape_runs.jsonl`. `failures` contains
unresolved work, not just HTTP exceptions; `recovered` contains previously
unresolved product work resolved during this run. Each record retains run ID,
retailer, category, stage, work URL, source URL, known retailer ID/SKU, reason and
retry classification. Replacing an initial missing-price outcome with its failed
fallback outcome avoids counting the same product twice. Raw parser `issues`
remain diagnostic context and do not add another unresolved work item.

Retry classifications are descriptive only:

- `retryable`: connection/timeout failures, HTTP 429/5xx, missing prices and missing
  offline cache entries;
- `inspect`: ambiguous/invalid prices, missing markup, repeated/unexplained empty
  pages and other errors requiring inspection;
- `blocked`: robots disallow or unsupported extraction operations;
- `unavailable`: HTTP 404/410, with no automatic retry.

Invalid command arguments are still rejected before collection. Network-free
cache reads do not re-request robots rules. Unavailable robots rules retain their
underlying status/cause for classification; they never allow requests by default.

### Counter definitions

- category_pages_planned: selected unique categories multiplied by the requested
  maximum pages, before confirmed early endings;
- category_pages_attempted: category fetch calls, including blocked/cache misses;
- category_pages_processed: category responses accepted after parsing and
  empty/repetition checks, including a confirmed empty ending;
- product_followups_attempted: product fetch calls, including manifests;
- source_responses: cached HTML reads plus final source responses delivered to
  the worker (successful HTML or HTTP errors);
- cache_hits / network_responses: source-response origins; HTTP error responses
  count as network responses, while connection failures have no response. These
  counters exclude robots.txt housekeeping requests and intermediate redirects;
- source_failures: distinct attempted source work with fetch/parse/write failure;
  a valid source with an unresolved price alone is counted in unresolved outcomes;
- unique_products_identified: distinct product URLs identified by category parsing
  or product-page parsing; an unfetched manifest URL alone is not proof of identity;
- observations_saved: product entries successfully persisted, split into
  priced_observations and null_price_observations;
- duplicates_skipped: redundant category/product URLs or observation candidates;
- recovered_issues / unresolved_outcomes: unique product/page work items, avoiding
  double-counting missing-price and fallback errors for the same product.

The existing pages_fetched/products_fetched fields count successful HTML reads;
items_found counts unique products successfully saved. Observations and unique
products differ if a future adapter legitimately produces multiple observations.

Explicit retries, attempt tracking and resolution are described below. Checkpoint 3 verifies the
policy with cached HTML and mocked responses for both retailers, including CLI
exit codes and stopping refresh before publication when collection is partial.
The verification makes no live retailer requests.


### Pending collection work (milestone 3.1, checkpoint 1)

Collection persists unresolved outcomes to `data/pending/collection.json`, a local
operational store separate from raw observations. All classifications are retained;
only `retryable` outcomes have `retry_eligible: true`. Nothing is retried automatically.

Identity is retailer + work kind + URL, with category included for category-page
work. Products appearing in multiple categories or runs share one entry. Each
entry keeps its first/latest run, latest outcome, and per-run sightings containing
identifiers, classification, stage, category and source URLs. Deferred null products
also retain the original cached HTML reference and page context. Recording the
same run twice does not duplicate its sighting. Sightings are not retry attempts.

Updates lock the store and atomically replace its JSON. Invalid/unsupported stores
are rejected without overwriting them; persistence errors fail the command rather
than claiming pending work was saved. Earlier raw observations remain intact. An ordinary
successful collection does not resolve or delete pending entries. Explicit retries
can resolve entries as described below. The file lock uses
the standard Unix `fcntl` module (macOS/Linux).


### Retry pending work (milestone 3.1, checkpoint 2)

```sh
# Retry at most 25 eligible entries using the normal cache/network policy
python3 -m scraper retry --shop jimms --limit 25
python3 -m scraper retry --shop datatronic --limit 25

# Reparse today's cache without network requests
python3 -m scraper retry --shop jimms --offline

# Fetch fresh pages instead of reusing today's cached missing prices
python3 -m scraper retry --shop datatronic --force --limit 5
```

Retries are explicit and sequential. Each selected pending entry gets one attempt
per command; `--limit` counts entries, not HTTP requests. Blocked, unavailable,
inspection-required and resolved entries are excluded. The shared fetcher retains
robots checks, delays, allowed hosts and caching; `--delay` defaults to one second.

Jimms product work revisits the product URL. Datatronic product work reparses the
original category page and resolves only if the target URL has a saved price.
Category work revisits that exact page, including its page number. A recovered
category can produce new pending product work; the command still exits 1 if its
collection has unresolved outcomes. Successful retries append raw observations;
earlier observations and sightings are retained.

Attempts retain an ID, timestamps, run ID, result and resolution status. Resolved
entries stay in the store and are skipped on later retries. New collection failures
reopen the same entry without removing attempt history. A newer collection failure
prevents an older retry from resolving it. A local command lock prevents concurrent
retry commands. If interrupted, the running attempt remains visible and is marked
interrupted when the entry is retried again. No automatic retry loop or scheduler
is installed. Exit 0 means selected work resolved (or no eligible entries); it does
not claim every pending entry or retailer category is complete.

Checkpoint 3 verifies retry interruption history, newer-failure resolution guards,
command locking, robots blocking and HTTP 429 reporting alongside offline
recovery for both retailers. Verification uses temporary data and mocked requests.

Retry batches share one fetcher/session, retaining robots rules and request timing
between entries. Datatronic distinguishes absent/empty prices (`missing_price`,
retryable) from displayed malformed values (`invalid_price`, inspect). Both retain
null-price observations.


### Normalised listing prices (milestone 4)

Each retailer listing selects observations by their source fetch timestamp, not
filename, processing time or retry time. Timestamp offsets are compared as actual
UTC instants. Legacy date-only/naive times are treated as UTC; absent times remain
unknown and sort before dated observations. Invalid timestamp text is rejected.

- `price_cents` is the latest observed price, including null.
- `price_status` is `available`, `unknown` or `conflict`.
- `last_known_price_cents` and `last_known_price_fetched_at` retain the newest
  unambiguous valid price, including the current price when available. They remain
  null if none exists; conflicting timestamp groups are skipped.
- `last_known_price_source` identifies that price's observation.
- `price_observations` retains the latest timestamp group's evidence, including
  source file, run, source URL, HTML reference and extraction method where present.

At equal instants a valid price takes precedence over null; different valid prices
produce a null current price and an inspection entry in the normalisation report.
A stable metadata tie-break makes this independent of file order. Listings are
kept separate by retailer and URL. Retailer IDs/SKUs are retained; when missing in
the selected observation, earlier identifiers retain their evidence in
`identifier_sources`. Earlier prices are never substituted into `price_cents`.

These fields are additive. No raw schema migration or database change is required.
Checkpoint 3 verifies the complete collection/null/retry/normalisation workflow
for both retailers, plus mixed-format timestamp conflicts and temporary export.
All output is temporary; the existing catalogue and web copy are unchanged.


## Shared specifications (milestone 5)

Both commands read the selected retailer's saved product URLs and write the same
URL-keyed `data/normalised/specs.json`. Use `--raw-dir` and `--out` for isolated
runs, `--limit` to bound products, `--offline` to reparse today's cached HTML,
`--force` to fetch fresh HTML, and `--status` to inspect the selected retailer.
Unknown supported fields are null; unknown labels are reported, not inferred.
`spec_count` counts parsed values rather than nullable field slots.

Adapters supply a specification-parser factory and advertise the capability.
Retailer modules own labels and HTML. Canonical units and field mapping live in
`common/specifications.py`; the shared worker owns fetch policy, checkpoints,
status and storage. The old Datatronic extractor class is a thin compatibility
entry point, with no separate collection implementation.

Jimms reads labelled technical descriptions and description tables/definition
lists. It excludes marketing text before an explicit technical section. Dimensions
are interpreted only with published axis order; contradictory aliases remain
unknown and are reported. Saved cooler pages do not become CPU specifications
from compatibility text. GPU fixtures include original description excerpts; CPU
conversion tests are synthetic and do not claim verified real CPU markup.

Cached HTML mtime determines `fetched_at`; `processed_at` records parsing time.
Entries retain retailer ID/SKU, category, extraction method, origin and HTML
reference. Successful prior specifications survive request/parser/empty failures,
with the failed attempt recorded separately as `last_attempt`. Offline misses
leave existing entries untouched. Failed passes return nonzero and stop refresh.
The normaliser skips null fields when combining retailer data sheets, so one
retailer's unknown values cannot erase another's parsed values.

The shared store is replaced atomically. Corrupt stores are rejected without
overwriting them, and a command lock prevents concurrent passes from losing each
other's updates. Commands preserve the other retailer's entries. Refresh schedules
specification stages for both retailers using the same options. No catalogue
refresh, database work or live requests are part of this milestone's verification.

A read-only audit of 53 locally cached GPU-labelled Jimms pages parsed supported
specifications from 50 pages. The other three were GPU water blocks rather than
graphics cards and remained empty. No live retailer requests were made.
