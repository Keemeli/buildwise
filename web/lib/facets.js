// Spec filters ("facets") for the part picker.
//
// Two rules, same as the rest of the app (issue #25):
//   1. A missing value means "not known", never "no". Every facet has an UNKNOWN bucket,
//      so a part without the spec is still reachable and never silently filtered away.
//   2. Facets are built on fields with near-full coverage and a canonical vocabulary
//      (see normalisation_report.md → Facet vocabulary). Values are shown as the pipeline
//      writes them; fixing a spelling belongs in the pipeline, not here.
//
// Semantics: options inside one facet are OR (DDR4 or DDR5), facets are AND
// (socket AM5 and DDR5). A facet with nothing selected does not filter.
//
// This file has no imports on purpose, so scripts/check-data-contract.mjs can load it
// the same way it loads lib/compat.js.

export const UNKNOWN = "__unknown__";

const filled = (v) => v !== null && v !== undefined && v !== "";

// PSU wattage is a number, so it is grouped into ranges. Labels come from strings.ts.
export const WATTAGE_BUCKETS = [
  { key: "w-lt600", max: 600 },
  { key: "w-600-749", min: 600, max: 750 },
  { key: "w-750-999", min: 750, max: 1000 },
  { key: "w-gte1000", min: 1000 },
];

function wattageBucket(watts) {
  if (!filled(watts)) return UNKNOWN;
  const bucket = WATTAGE_BUCKETS.find((b) => (b.min == null || watts >= b.min) && (b.max == null || watts < b.max));
  return bucket ? bucket.key : UNKNOWN;
}

// Per category: which facets to show, in this order.
//   id      — key in strings.ts → picker.facets
//   value   — reads the facet value(s) from a component's specs. May return a list
//             (a motherboard that supports both DDR4 and DDR5).
//   order   — fixed option order; otherwise options are sorted by count.
export const FACETS = {
  cpu: [{ id: "socket", value: (s) => s.socket }],
  motherboard: [
    { id: "socket", value: (s) => s.socket },
    { id: "memoryType", value: (s) => s.memory_type },
    { id: "formFactor", value: (s) => s.form_factor },
  ],
  memory: [{ id: "memoryType", value: (s) => s.memory_type }],
  gpu: [{ id: "vendor", value: (s) => s.gpu_vendor }],
  storage: [
    { id: "interface", value: (s) => s.interface },
    { id: "formFactor", value: (s) => s.form_factor },
  ],
  psu: [{ id: "wattage", value: (s) => wattageBucket(s.wattage_w), order: WATTAGE_BUCKETS.map((b) => b.key) }],
  case: [{ id: "caseSize", value: (s) => s.form_factor }],
};

export function facetsFor(category) {
  return FACETS[category] ?? [];
}

// The option keys a component falls into for one facet. Never empty: no value → UNKNOWN.
export function optionKeys(facet, component) {
  const raw = facet.value(component.specs ?? {});
  const list = (Array.isArray(raw) ? raw : [raw]).filter(filled).map(String);
  return list.length > 0 ? [...new Set(list)] : [UNKNOWN];
}

// selections: { [facetId]: string[] } — the option keys the user has ticked.
function matchesFacet(facet, component, selected) {
  if (!selected || selected.length === 0) return true;
  return optionKeys(facet, component).some((key) => selected.includes(key));
}

export function applyFacets(items, facets, selections, getComponent = (x) => x) {
  return items.filter((item) => facets.every((f) => matchesFacet(f, getComponent(item), selections[f.id])));
}

// Options for every facet, each with the number of items it would show.
// A count respects the *other* facets' selections but not its own, so ticking a second
// option in the same facet shows how many more parts it adds (standard faceted search).
// The UNKNOWN option is always listed, even at 0, so it is clear nothing is hidden.
export function facetOptions(items, facets, selections, getComponent = (x) => x) {
  return facets.map((facet) => {
    const others = facets.filter((f) => f.id !== facet.id);
    const pool = applyFacets(items, others, selections, getComponent);
    const counts = new Map();
    for (const item of pool) {
      for (const key of optionKeys(facet, getComponent(item))) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    // Options that are ticked stay visible even if another facet brought them to 0.
    for (const key of selections[facet.id] ?? []) if (!counts.has(key)) counts.set(key, 0);
    if (facet.order) for (const key of facet.order) if (!counts.has(key)) counts.set(key, 0);
    if (!counts.has(UNKNOWN)) counts.set(UNKNOWN, 0);

    const known = [...counts.entries()].filter(([key]) => key !== UNKNOWN);
    known.sort(([a, ca], [b, cb]) =>
      facet.order ? facet.order.indexOf(a) - facet.order.indexOf(b) : cb - ca || a.localeCompare(b),
    );
    const options = [...known, [UNKNOWN, counts.get(UNKNOWN)]].map(([key, count]) => ({ key, count }));
    return { facet, options };
  });
}
