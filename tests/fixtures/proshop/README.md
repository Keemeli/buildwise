# Proshop GPU source fixtures

Captured on 2026-11-11 for source verification, before adding an adapter.
See `scraper/docs/proshop-source-verification.md` for selectors, robots limitations,
pagination, condition policy and specification mapping candidates.

- `gpu_page_1.html`, `gpu_page_2.html`: reduced category markup, 25 cards each.
- `product_3331069.html`, `product_3331106.html`: identity, current/related price
  markup, reduced JSON-LD and grouped technical rows from the supplied products.
- `robots.txt`: the published rules snapshot, retained for wildcard/query checks.
- `sources.json`: URLs, capture timestamps and original/excerpt SHA-256 hashes.
- `observations.json`: the audit's card and product observations, not a new raw
  schema, independent price oracle or implementation test result. Only the two
  supplied product prices were independently cross-checked against their cards.

Images, marketing descriptions and request tokens are omitted. The fixtures
retain DEMO cards and separate ex-VAT/related prices intentionally. Their prices,
availability and product totals are historical snapshots, not current guarantees.
Full source responses remain in the temporary audit cache, outside the repository.
No requests to Proshop are required to inspect these files.

Milestone 4 adds product_3331067.html, product_3395203.html and
product_3371545.html from the user's five-product run. These preserve only title
and primary data-sheet markup. specification_samples.json records their sources,
fetch times and original/excerpt checksums; the milestone 1 snapshots are intact.
