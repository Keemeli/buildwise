// Catalogue helpers that client components may import. Nothing here touches the
// catalogue data itself: that stays on the server (lib/catalog.js) and reaches the
// browser one category at a time through /catalog/<category> (see lib/useCategory.js).

// Seven slots we can actually fill. A "cooler" slot sat between cpu and motherboard, but
// scraper/config.py has no cooler category and the catalogue carries zero cooler rows, so
// its picker could only ever answer "this category's parts have not been fetched yet" and
// a build could never reach its slot count. The strings, the picker's summary and the
// engine's two cooler rules (socket compatibility, height against the case) all stay in
// place for the day a cooler category is collected — tracked in issue #44.
export const SLOTS = [
  { category: "cpu" },
  { category: "motherboard" },
  { category: "memory" },
  { category: "gpu" },
  { category: "storage" },
  { category: "psu" },
  { category: "case" },
];

// "RTX5070TI", "RTX 5070 Ti" and "rtx 5070 ti" are the same chip.
export function chipsetKey(chipset) {
  return chipset ? chipset.toUpperCase().replace(/\s+/g, "") : null;
}

export function cheapestOffer(component) {
  return component.offers.reduce((best, o) => (o.priceCents < best.priceCents ? o : best));
}
