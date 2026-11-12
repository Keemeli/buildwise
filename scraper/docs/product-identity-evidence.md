# Product identity evidence — milestone 1

Purpose: preserve trustworthy identifiers before changing cross-retailer product
matching. Milestone 1 preserved evidence; milestone 2 introduced pair decisions.
Milestone 3 now applies verified groups, as described below. No BuildWise database
IDs, fuzzy matching or historical-data migration are introduced.

## Shared model

New raw product observations can contain an optional `identity` object. Product
specification entries retain the same shape from their already-fetched response:

- `gtin`: checksum-validated text, represented with 14 digits. GTIN-8, UPC/GTIN-12,
  EAN/GTIN-13 and GTIN-14 are accepted; shorter formats are left-padded with zeroes.
- `manufacturer_part_number`: explicit manufacturer identifier, with case,
  punctuation and separators preserved; whitespace is cleaned.
- `brand`: explicitly published product brand where present. It is not inferred
  from a retailer name and is not silently relabelled as a legal manufacturer.
- `evidence`: each field's original value, canonical value, selector/JSON-LD
  property and validation error, if any.
- `issues`: invalid, conflicting or mismatched-source identifiers for review.

GTIN input must be text; numeric JSON values are rejected because lost leading
zeroes cannot be recovered safely. Invalid lengths, characters, check digits and
all-zero placeholders stay unknown. A check digit validates structure only; it
is not a GS1 assignment lookup or proof that two listings should be merged.
Different valid values for one field yield null rather than a first-value choice.

The retailer's `external_id` and `retailer_sku` retain their previous meanings.
Neither is automatically promoted into a manufacturer identifier. Old raw files
without `identity` remain readable. This is additive metadata under schema 2;
existing raw observations are not rewritten.

References:

- https://support.gs1.org/support/solutions/articles/43000734386-are-all-gtins-unique-numbers-
- https://gs1.se/en/support/how-many-digits-should-a-gtin-contain/
- https://www.schema.org/Product

## Retailer sources

| Retailer | Initial evidence | Verification boundary |
| --- | --- | --- |
| Jimms | Bound product metadata `itemprop=gtin13` and `itemprop=mpn` | A reduced saved GPU metadata block includes its retailer SKU for URL-ID agreement |
| Proshop | Product JSON-LD GTIN/MPN/brand properties | The two saved product pages provide these fields; Product SKU/URL must agree with the requested listing |
| Datatronic | Primary product JSON, scoped GTIN metadata and Tuotekoodi reference | One user-saved GPU page verifies internal ID, EAN and manufacturer reference; recommendation IDs are ignored |

JSON-LD processing examines root Product nodes and graph Product nodes, ignoring
unrelated recommendations and accessories. A node must bind to the requested
URL or retailer ID; contradictory identifiers are rejected. Jimms metadata is
scoped to its product identity container and must agree with the URL's product
record ID. Datatronic binds its primary details to the requested URL and internal
ID; its displayed SKU is a manufacturer reference, not the numeric retailer ID.
Generic page-wide GTIN searches are not used.

## Workflow and provenance

Adapters expose one pure `extract_identity` operation. The shared specification
worker calls it on the product response it already has. Jimms product-price
collection also preserves identity from that same response. Category prices do
not trigger extra product-page requests for identity, and no full-category scan
or manual identification is introduced.

The raw envelope/specification entry supplies source URL, cached HTML reference
and source fetch time. The normaliser attaches `identity_observations` to each
listing, including raw observations and primary/retained failed-attempt product
responses. These remain source observations, not a selected matching decision.
Historical raw files remain the source of earlier observations. No identity is
silently chosen across conflicting sources or different observation times.

Identifier diagnostics do not make a successful price/specification extraction
fail and do not schedule retry requests. Identity evidence can survive an empty
specification refresh. The specification report shows identifier coverage and
issues for inspected saved pages.

To extract identifiers from today's saved product responses, use the existing
specification command with `--offline`, for example:

```sh
python3 -m scraper specs --shop proshop --category gpu --limit 5 --offline
python3 -m scraper specs --shop jimms --category gpu --limit 5 --offline
```

Missing cached pages are still reported as offline misses. Development verification uses saved fixtures and temporary stores; it does not
refresh the actual catalogue or rewrite existing observations.

Milestone 1 did not change grouping. The rules and activation below build on its
source evidence without rewriting historical observations.


## Milestone 2: reviewable match decisions

Normalisation also writes `identity_matches.json` alongside its usual outputs.
Milestone 2 initially produced an audit report without changing title grouping.
Milestone 3 extends the same report with the applied conservative grouping plan.

The report reconciles observations per shop and URL before any cross-shop grouping.
It retains source evidence, uses available saved product-page specifications,
and lists pair decisions by indices into `listings`:

- `match`: equal validated GTINs, or equal explicit brand and manufacturer part
  number when GTIN is missing on at least one side. Brand comparison ignores
  letter case; part numbers retain punctuation and case. No brand aliases apply.
- `conflict`: a shared candidate identifier is contradicted by category, another
  published identifier, or known variant specification values.
- `review`: invalid/conflicting evidence, suspect categories or known special-offer
  wording prevent a confident decision. Bundles, DEMO, used/refurbished and tray
  wording are conservative review triggers, not a complete offer classifier.
- Listings without a shared GTIN or brand/part-number candidate stay unlinked;
  `counts.without_candidates` reports their number. Names and retailer record IDs
  do not establish a match. Pair counts count decisions, not products.

All retained observation times participate: conflicting old/new identifiers stay
unknown and require review rather than silently choosing the newest value.
Candidate indexing avoids all-pairs title comparisons. Decisions are deterministic
pairs, never transitive component groups. A match is evidence for review, not a
claim of verified manufacturer registration or permission to merge a bundle.

Run the existing normalisation command against an isolated output directory that
contains the desired `specs.json` to inspect decisions without replacing the main
catalogue. This milestone performs no network fetch, database migration or
historical-data rewrite. Milestone 3 activates the grouping policy below.


## Milestone 3: verified catalogue grouping

Normalisation now applies identity decisions instead of title-based merging:

1. Collapse repeated snapshots by retailer and product URL, retaining per-shop
   current/last-known prices, nulls, ties and source identity observations.
2. Find candidate matches using the milestone 2 rules. Category and known variant
   conflicts veto matches; names and retailer IDs are never matching keys.
3. Group a connected set only when **every pair** is a confirmed match. Distinct
   URLs from one shop cannot confirm each other. A missing-identifier bridge or
   duplicate shop offers therefore withhold the entire ambiguous connected set.
4. Keep all other listings separate with `unresolved`, `review` or `conflict`
   status. Unknown identity never borrows another shop's specifications.

The report has `policy_version: 2`, `mode: verified_grouping` and `groups` with
listing indices, statuses and reasons. Pair decisions remain visible even when
an ambiguous group prevents applying them. Counters distinguish verified groups,
separate listings and withheld ambiguous connected groups. A source assigning
one retailer URL to different categories stays split by category in the catalogue.

Each catalogue component has `identity_match` status/reasons; the payload records
`identity_policy_version`. Its existing component/listing fields remain readable
by the exporter and web app. Evidence-free historical observations remain valid
individual listings; counts can increase until product-page identity is collected.
No title fallback is used. Group membership is deterministic for the same inputs;
it is not a permanent database component ID.

Already saved product-page specifications help guard matches. After grouping,
contradictory specification values from different product pages become null,
with all values, shop/URL and source time retained in `spec_conflicts`. They do
not depend on which shop happens to be processed last. Field coverage reports
continue to count unknown fields as missing.

Verification includes the real saved Datatronic/Proshop pair, three-shop complete
matches, conflicting identifiers with identical titles, partial match bridges,
duplicate shop offers, deterministic ordering, null-price history and conflicting
specification provenance. Tests use temporary stores with network access mocked.
Existing raw files, saved specifications and deployed catalogue are not rewritten.
