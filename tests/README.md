# Scraper tests

Run from the repository root. Tests use temporary files, saved/synthetic HTML and
mocked requests; they do not require live retailer access or a database.

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p 'test_datatronic*.py' -v
python3 -m unittest discover -s tests -p test_fetching.py -v
```

| File | Responsibility | Tests |
| --- | --- | ---: |
| test_jimms_parser.py | Product metadata and category-link extraction | 4 |
| test_jimms_worker.py | Category prices, manifests, pagination and follow-ups | 5 |
| test_datatronic_parser.py | Listing-card parsing | 1 |
| test_datatronic_worker.py | Collection output, pagination and failure handling | 3 |
| test_datatronic_specifications.py | Specification filtering, parsing, cache and failure policy | 11 |
| test_fetching.py | Shared robots checks, throttling and cache behaviour | 3 |
| test_prices.py | Exact price conversion | 1 |
| test_raw_data.py | Shared observation schema and mixed-source compatibility | 7 |
| test_normalisation.py | Component parsing, multi-shop merging and newest prices | 4 |
| test_refresh.py | Stage planning, category selection and stopping on failure | 3 |
| test_cli.py | Unified commands and offline end-to-end workflows | 7 |
| test_export.py | Complete-content export drift checks | 1 |
| test_reports.py | Specification report field configuration | 1 |
| test_configuration.py | Project paths and isolated parser configuration | 2 |
| test_retailer_adapters.py | Shared contract, registry and offline adapter parity | 13 |
| test_collection_worker.py | Generic orchestration, third-adapter integration and cleanup | 10 |
| test_collection_policy.py | Checkpoint 2 null-preservation and reporting implementation checks | 4 |
| test_collection_policy_matrix.py | Cross-retailer outcomes, counters, failures and CLI policy | 26 |
| test_pending_work.py | Pending identity, evidence, eligibility and atomic persistence | 8 |
| test_retry.py | Explicit retry recovery, filtering, attempts and resolution | 11 |
| test_listing_prices.py | Current/null/history selection, timestamp ties and conflict evidence | 6 |
| test_price_workflow.py | Collection/null/retry/normalisation and mixed-format integration | 2 |
| test_jimms_specifications.py | Saved Jimms markup, canonical fields and conservative parsing | 5 |
| test_specifications_shared.py | Cross-retailer specification CLI, policy, persistence and normalisation | 7 |
| **Total** | | **145** |

Tests are grouped by the responsibility they verify. A shared fetching test may
use a Jimms URL as a fixture, but its behaviour applies to both retailers. CLI and
raw-data integration tests deliberately exercise multiple layers. Cross-retailer
parser configuration belongs in test_configuration.py.

This reorganisation preserves all 49 existing test methods, assertions and class
fixtures. Existing overlapping coverage has not been removed or consolidated;
that requires a separate review. No new test framework or dependency was added.

Adapter fixtures under `fixtures/jimms/` verify 50 saved GPU category prices against
independent product-page observations without network requests.

Identifier regression tests distinguish retailer record IDs from displayed SKUs,
check all 50 saved Jimms cards, preserve follow-up identifiers, and verify mixed
legacy/version-1/version-2 normalisation without rewriting old data.

Milestone 2 replaces obsolete worker-specific execution tests with shared-worker
integration tests. Jimms category collection explicitly asserts zero product-page
requests for 50 saved products; Datatronic tests preserve listing fields/totals
across pages. Command tests continue to verify offline collection for both.

Milestone 3 checkpoint 2 adds four focused implementation checks. Checkpoint 3
adds 26 matrix tests using real adapters and the shared fetcher with cached HTML
and mocked network responses; no live retailer requests are made. The matrix
checks both retailers, success/partial/failure exits, null-price preservation,
recovery, HTTP/connection/robots failures, empty/repeated pages, overlapping
categories, malformed cards, atomic writes, run IDs and refresh stopping before
publication after partial collection. Jimms-specific follow-ups also cover
offline misses, blocked product requests and missing identity.

Milestone 3.1 checkpoint 1 adds six pending-store tests and checks that collection
links its persisted outcome and original source context to the run.

Milestone 3.1 checkpoint 2 uses focused offline retry tests for both retailers;
the full suite is reserved for milestone completion.

Milestone 3.1 checkpoint 3 verifies interrupted attempts, stale resolution guards,
retry-command locking, robots blocking and HTTP 429 classification/counters. All
checks use temporary data and cached or mocked responses, with no live scraping.

Review regressions check batch-wide robots caching, crawl-delay spacing and
session cleanup, plus missing versus malformed Datatronic price classification.

Milestone 4 checkpoint 2 adds six focused price-selection checks and runs the
existing normalisation/report checks. Verification writes only temporary output;
full milestone verification remains checkpoint 3.

Milestone 4 checkpoint 3 verifies both retailers through offline collection, null
observations, pending resolution, normalisation and temporary export. Older-cache
reparsing retains source times, original raw observations remain unchanged, and
mixed legacy/versioned conflicts stay isolated by retailer.

Milestone 5 preserves the 11 Datatronic specification checks and adds 12 focused
checks for Jimms parsing and shared orchestration. Tests reuse cached/fixture HTML
or mock responses, preserve source timestamps, check both retailers in one store,
and verify normaliser compatibility without writing real catalogue files. Refresh
planning now expects both supported specification stages.
