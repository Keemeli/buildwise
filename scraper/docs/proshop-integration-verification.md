# Proshop GPU integration verification — milestone 4

Reviewed the five product responses from the user's successful live specification
run on local date 2026-11-12. The category collection contained 48 regular GPU
listings and two reported DEMO exclusions. This review used those saved responses;
no new retailer requests were made.

## Field checks against the cached data sheets

| Product ID | Memory | Length mm | Width mm | Height mm | Recommended PSU W | GPU consumption W |
| --- | --- | --- | --- | --- | --- | --- |
| 3331069 (ASUS Astral) | 32 GB GDDR7 | 357.6 | 76 | 149.3 | 1000 | unknown |
| 3331067 (ASUS TUF) | 32 GB GDDR7 | 348 | 72 | 146 | 1000 | unknown |
| 3395203 (ASUS Astral BTF) | 32 GB GDDR7 | 357.6 | 76 | 149.3 | 1000 | unknown |
| 3331106 (Gigabyte WindForce) | 16 GB GDDR7 | 304 | 50 | 126 | 750 | unknown |
| 3371545 (NVIDIA Server) | 96 GB GDDR7 | 266.7 | unknown | 111.7 | unknown | 600 |

All listed dimensions match their published source measurements after cm-to-mm
conversion. Width uses the published `Leveys` axis, not an inferred card face
measurement. Missing source dimensions and PSU recommendations remain null.
The five cached JSON-LD SKUs and offer URLs agree with the collected listing IDs
and URLs. All five offer prices match the previously collected category prices
in these snapshots; this is not a guarantee about current live prices.

## Coverage correction

The server card publishes `Muuta / Virran kulutus (toiminnassa): 600 watti(a)`.
The milestone 3 parser did not recognise this label. Added the exact grouped label
to `power_w`, using the shared canonical watts converter. It is independent of
`recommended_psu_w`: 600 W is operating consumption, not a PSU recommendation.
The existing four consumer cards still have null consumption. The corrected
server result has eight fields; each consumer result has nine.

## Integration and preservation

- Reparsed the same five cached pages through the shared CLI in offline mode.
- Used a copied specification store and temporary normalisation output under
  `/tmp/buildwise-proshop-m4/normalised`.
- Each of the five listings matched exactly one resulting component, and every
  non-null parsed field reached that component unchanged.
- Reused existing checks for robots/caching, exact-page retries, exclusions,
  refresh stage planning and stopping before publication on failed stages.
- Saved three additional reduced product fixtures (TUF, BTF and server), with
  source URLs, fetch times and original/excerpt hashes in
  `tests/fixtures/proshop/specification_samples.json`.
- Added regression checks for these layouts and for server consumption staying
  separate from an unknown recommended PSU through normalisation.
- Ignored the operational `data/normalised/specs.lock` file.

The real specification store/report, raw observations, collection run log,
normalised catalogue and web catalogue are left unchanged. The source snapshots'
UTC fetch times are retained, independently of the local cache date.
The updated server field exists in the temporary verification output; a later
ordinary/offline specification run applies it to the main store.

This verifies this GPU sample's integration, not universal cross-retailer product
identity or resolution of conflicting specifications. Those previously noted
limitations remain separate work. No database, live crawl or publication changes
are included.
