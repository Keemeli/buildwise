# Scraper tests

Run from the repository root with the scraper dependencies installed. Tests use
saved/synthetic HTML, temporary output and mocked requests. They need no retailer
access or database and do not update the real catalogue.

```sh
# Full suite at a milestone or commit boundary
python3 -m unittest discover -s tests

# Focused checks while changing one responsibility
python3 -m unittest tests.test_collection_worker
python3 -m unittest tests.test_collection_policy
python3 -m unittest tests.test_specifications

# One retailer's adapter or specification parser
python3 -m unittest tests.test_adapters.ProshopAdapterTests
python3 -m unittest tests.test_specification_parsers.ProshopSpecificationTests
```

## Layout

| Module | Responsibility | Checks |
| --- | --- | ---: |
| test_adapters.py | Contracts, registry, retailer price parsing and parser configuration | 27 |
| test_collection_worker.py | Controlled orchestration, follow-ups, deduplication and cleanup | 10 |
| test_collection_policy.py | Real-adapter outcome policy, counters, provenance and failure handling | 26 |
| test_collection_integration.py | Saved retailer pages, CLI collection, exclusions and exact-page retries | 13 |
| test_specification_parsers.py | Retailer labels, units, scoped fields and ambiguous values | 14 |
| test_specifications.py | Shared collection, compatibility, storage, reporting and normalisation | 22 |
| test_fetching.py | Robots matching, request failures, throttling and caching | 5 |
| test_raw_data.py | Shared observations, IDs, immutable writes, legacy formats and exact cents | 8 |
| test_normalisation.py | Component parsing, price history/conflicts and end-to-end recovery and GPU vocabulary | 16 |
| test_pending_work.py | Work identity, evidence, classification and atomic persistence | 8 |
| test_retry.py | Selection, limits, attempts, recovery, locks and request spacing | 11 |
| test_cli.py | Arguments, help, offline subprocesses, export and drift checks | 8 |
| test_refresh.py | Stage planning, category selection and stopping on failure | 3 |
| test_product_identity.py | GTIN/MPN validation, bound source extraction, evidence preservation, match decisions and verified grouping | 19 |
| **Total** | | **190** |

`support.py` contains reusable synthetic HTML builders, HTTP responses and the
repository path. It contains no test cases. Import shared helpers from there,
rather than importing a `test_*.py` module. Helpers used by only one module stay
beside their tests.

## Coverage and fixtures

- Unit checks use controlled inputs; integration checks exercise real adapters
  and the shared commands. Keep these distinct even when they cover the same
  feature at different boundaries.
- `fixtures/jimms/` preserves 50 independent saved price observations and GPU
  specification layouts, including a misfiled cooler rejection case.
- `fixtures/proshop/` preserves category cards, DEMO listings, robots rules,
  identity evidence and five GPU specification layouts with source manifests.
- Fixture files and production code are unchanged by this test consolidation.
- The four early null-price/fallback/empty-ending tests were consolidated into
  the richer collection policy checks. Their pending-store assertions and cached
  timestamps remain covered, and failed fallback coverage includes timeouts.
- Retained checks include Datatronic's compatibility extractor, unknown fields,
  preservation of successful data, all three registered adapters and the export
  command's ability to run with only the Python standard library.

When adding a retailer, extend adapter and specification-parser cases, then add
integration coverage where its request or failure behaviour differs. Reuse shared
policy checks; avoid creating milestone-specific test files or repeating generic
worker checks under each retailer's name.

Identity evidence checks use saved Jimms/Proshop/Datatronic metadata and temporary stores.
They verify checksum/leading-zero handling, raw round trips, source binding,
cache reuse and conservative cross-retailer grouping. Unknown listings stay separate.

Matching checks cover different titles for the same identifiers, identical titles
without identifiers, category/GTIN/MPN/brand/variant conflicts, retained historical
conflicts and special offers. The saved Datatronic/Proshop pair confirms the
verified cross-retailer group. Additional cases cover incomplete match chains,
duplicate shop offers, input ordering and per-shop price/specification provenance.

Datatronic GPU parser checks use its saved primary product JSON and rendered
fallback. They distinguish PCIe from memory width, vendor from model, and card
from package dimensions; alias conflicts and ambiguous measurements stay unknown.

GPU value checks cover chipset suffixes, connector quantities/configurations,
PCIe generations and lane counts, unknown wording and deterministic source
provenance. They verify that normalisation does not rewrite saved specifications.
