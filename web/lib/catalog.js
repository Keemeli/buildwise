// Component catalog, read from the normaliser output.
//
// Source: data/normalised/components.json (made by scraper/normalise.py).
// The web app reads its own copy in web/data/components.json, because Vercel only
// deploys the web/ folder. Copy the file there after running the normaliser.

import raw from "@/data/components.json";

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

export const CATALOG_META = {
  generatedAt: raw.generated_at,
  source: raw.source,
};

// The normaliser writes "Micro-ATX" / "Mini-ITX"; the compatibility rules use short names.
const FORM_FACTOR = { "Micro-ATX": "mATX", "Mini-ITX": "ITX", ATX: "ATX", "E-ATX": "E-ATX" };

// "RTX5070TI", "RTX 5070 Ti" and "rtx 5070 ti" are the same chip.
export function chipsetKey(chipset) {
  return chipset ? chipset.toUpperCase().replace(/\s+/g, "") : null;
}

// Shop + shop's own product id. Jimms listings carry no external_id, so the product
// URL stands in; without it every Jimms part shared the id "jimms-none", and the
// picker list (keyed by id) showed the wrong rows. Replace with the MPN once the
// normaliser provides it.
function componentId(listing) {
  const ref = listing.external_id ?? listing.url?.replace(/^https?:\/\/[^/]+\//, "");
  return `${listing.shop}-${ref}`.toLowerCase();
}

function toComponent(c) {
  const first = c.listings[0];
  const specs = { ...c.specs };
  if (c.category === "motherboard" && specs.form_factor) {
    specs.form_factor = FORM_FACTOR[specs.form_factor] ?? specs.form_factor;
  }

  return {
    id: componentId(first),
    category: c.category,
    brand: c.brand,
    model: c.model,
    name: c.raw_name, // shown exactly as the shop writes it, never translated
    specs,
    image: c.image ?? null, // shop's product photo URL, loaded straight from the shop
    offers: c.listings
      .filter((l) => l.price_cents != null)
      .map((l) => ({
        shop: l.shop,
        priceCents: l.price_cents,
        inStock: l.in_stock ?? null,
        url: l.url,
      })),
  };
}

// Ids must be unique: React keys the picker list by id, and findComponent looks parts up by it.
function uniqueIds(components) {
  const seen = new Map();
  for (const c of components) {
    const n = seen.get(c.id) ?? 0;
    seen.set(c.id, n + 1);
    if (n > 0) c.id = `${c.id}-${n + 1}`;
  }
  return components;
}

export const COMPONENTS = uniqueIds(raw.components.map(toComponent).filter((c) => c.offers.length > 0));

// Shops the prices come from, for display: "Datatronic · Jimms".
export const SHOPS = [...new Set(COMPONENTS.flatMap((c) => c.offers.map((o) => o.shop)))].sort().join(" · ");

const BY_ID = new Map(COMPONENTS.map((c) => [c.id, c]));

export function findComponent(id) {
  return (id && BY_ID.get(id)) || null;
}

export function cheapestOffer(component) {
  return component.offers.reduce((best, o) => (o.priceCents < best.priceCents ? o : best));
}
