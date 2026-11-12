# Common GPU specification values

Milestone 6 resolves known wording differences in the normaliser. Retailer
parsers and saved `specs.json` values retain their original retailer wording.
Matching still requires consistent product identity; vocabulary equivalence
alone never links listings or overrides GTIN/MPN/category conflicts.

## Supported forms and boundaries

| Field | Example inputs | Normalised result |
| --- | --- | --- |
| graphics_chipset | GeForce RTX5070 ti; NVIDIA GeForce RTX 5070 Ti | NVIDIA GeForce RTX 5070 Ti |
| graphics_chipset | Radeon RX9070 xt; AMD Radeon RX 9070 XT | AMD Radeon RX 9070 XT |
| graphics_chipset | Arc B580; Intel Arc B 580 | Intel Arc B580 |
| interface | PCI-E 5.0; PCI Express x16 5.0; PCI Express 5.0 | PCI Express 5.0 x16 |
| power_connectors | 1x 16-pin; 1 x 16-pin | ["1 x 16-pin"] |

Only complete recognised patterns are rewritten. GPU model numbers and suffixes
are significant: base, Ti, SUPER, XT and XTX remain distinct. Workstation text,
OC variants, composite models and other unsupported forms are preserved exactly;
they are not reduced to a broadly similar chip name.

PCIe generation and lane count are compared separately. Missing details are
unknown, so a consistent explicit value from a verified offer may supplement
another offer that omitted it. The sample's x16 comes from Datatronic; it is not
inferred from the term PCI Express. Differing explicit generations or lanes
produce null with source evidence. Descriptions such as x16 (x8), ranges and
multiple generations remain unsupported text rather than losing details.

Connector quantities, pin configurations and duplicate entries are significant.
Spacing/case and x/× separators are standardised. Explicit counts of the same
pin configuration may be added (two 1 x 8-pin entries equal 2 x 8-pin); list order
is immaterial. An uncounted 16-pin does not become 1 x 16-pin. A 6+2-pin
configuration does not silently become 8-pin. Named connector standards remain
unchanged; they are not treated as interchangeable based on pin count.

Fields outside these three GPU values retain the previous exact comparison.
No generic fuzzy text comparison or global punctuation stripping is introduced.

## Provenance and output

For each supported field, the component's `spec_observations` contains:

- `value`: the original parsed retailer value;
- `canonical_value`: its recognised common form, or the untouched unsupported value;
- retailer, product URL, saved HTML reference and observation timestamp.

Evidence is ordered deterministically. For PCIe, an individual canonical_value
still shows only that observation's published details. The component value can
contain the combined consistent generation/lanes from the available observations.
Genuine conflicts stay null and retain this evidence in `spec_conflicts` too.
The normalisation report points reviewers to these source observations.

This adds catalogue evidence metadata; existing field types and retailer commands
are unchanged. The source specification store, raw observations and web catalogue
are not rewritten by development verification.

## Verification

Focused cases cover positive spelling equivalence and negative model suffix,
generation, lane and connector differences, along with input ordering and
unchanged source files. The isolated saved-page sample still produces one verified
Datatronic/Jimms/Proshop group plus separate non-Ti and missing-identity V2 controls.
Its corrected values are NVIDIA GeForce RTX 5070 Ti, PCI Express 5.0 x16 and
["1 x 16-pin"], with card dimensions 304/50/126 mm. The three prior wording
conflicts are resolved; four saved product pages are parsed without network
requests, and the intentionally uncached V2 page remains an offline miss.
