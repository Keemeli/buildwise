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
| test_jimms_worker.py | Collection output, manifests and pagination | 4 |
| test_datatronic_parser.py | Listing-card parsing | 1 |
| test_datatronic_worker.py | Collection output and failure handling | 2 |
| test_datatronic_specifications.py | Specification filtering, parsing, cache and failure policy | 11 |
| test_fetching.py | Shared robots checks, throttling and cache behaviour | 3 |
| test_prices.py | Exact price conversion | 1 |
| test_raw_data.py | Shared observation schema and mixed-source compatibility | 6 |
| test_normalisation.py | Component parsing, multi-shop merging and newest prices | 3 |
| test_refresh.py | Stage planning, category selection and stopping on failure | 3 |
| test_cli.py | Unified commands and offline end-to-end workflows | 7 |
| test_export.py | Complete-content export drift checks | 1 |
| test_reports.py | Specification report field configuration | 1 |
| test_configuration.py | Project paths and isolated parser configuration | 2 |
| test_retailer_adapters.py | Shared contract, registry and offline adapter parity | 11 |
| **Total** | | **60** |

Tests are grouped by the responsibility they verify. A shared fetching test may
use a Jimms URL as a fixture, but its behaviour applies to both retailers. CLI and
raw-data integration tests deliberately exercise multiple layers. Cross-retailer
parser configuration belongs in test_configuration.py.

This reorganisation preserves all 49 existing test methods, assertions and class
fixtures. Existing overlapping coverage has not been removed or consolidated;
that requires a separate review. No new test framework or dependency was added.

Adapter fixtures under `fixtures/jimms/` verify 50 saved GPU category prices against
independent product-page observations without network requests.
