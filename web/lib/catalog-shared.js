// Catalogue helpers that client components may import. Nothing here touches the
// catalogue data itself: that stays on the server (lib/catalog.js) and reaches the
// browser one category at a time through /catalog/<category> (see lib/useCategory.js).

export const SLOTS = [
  { category: "cpu" },
  { category: "cooler" },
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
