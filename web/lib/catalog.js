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

function toComponent(c) {
  const first = c.listings[0];
  const specs = { ...c.specs };
  if (c.category === "motherboard" && specs.form_factor) {
    specs.form_factor = FORM_FACTOR[specs.form_factor] ?? specs.form_factor;
  }

  return {
    // Shop + shop's own product id. Replace with the MPN once the normaliser provides it.
    id: `${first.shop}-${first.external_id}`.toLowerCase(),
    category: c.category,
    brand: c.brand,
    model: c.model,
    name: c.raw_name, // shown exactly as the shop writes it, never translated
    specs,
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

export const COMPONENTS = raw.components.map(toComponent).filter((c) => c.offers.length > 0);

// Shops the prices come from, for display: "Datatronic · Jimms".
export const SHOPS = [...new Set(COMPONENTS.flatMap((c) => c.offers.map((o) => o.shop)))].sort().join(" · ");

const BY_ID = new Map(COMPONENTS.map((c) => [c.id, c]));

export function findComponent(id) {
  return (id && BY_ID.get(id)) || null;
}

export function cheapestOffer(component) {
  return component.offers.reduce((best, o) => (o.priceCents < best.priceCents ? o : best));
}
