"use client";

// The shop a part is bought from, as a small badge instead of a bare word: a monogram in
// the shop's colour plus the name, so "Datatronic 249,90 €" reads as one offer.
//
// A monogram rather than the shop's real logo: we have no licence to redistribute their
// brand marks, and a generated mark cannot be mistaken for one. The shop name is always
// written out next to it, so the badge only speeds up scanning a list.

const BRAND = {
  datatronic: { initials: "D", className: "shop-datatronic" },
  jimms: { initials: "J", className: "shop-jimms" },
  proshop: { initials: "P", className: "shop-proshop" },
};

function brandOf(shop) {
  const key = String(shop ?? "").toLowerCase();
  const match = Object.keys(BRAND).find((name) => key.includes(name));
  if (match) return BRAND[match];
  return { initials: (String(shop ?? "?").trim()[0] || "?").toUpperCase(), className: "shop-other" };
}

export default function ShopBadge({ shop, showName = true, size = 18 }) {
  if (!shop) return null;
  const brand = brandOf(shop);
  return (
    <span className="shop-badge">
      <span
        className={`shop-mark ${brand.className}`}
        style={{ width: size, height: size, fontSize: Math.round(size * 0.6) }}
        aria-hidden="true"
      >
        {brand.initials}
      </span>
      {showName && <span className="shop-name">{shop}</span>}
    </span>
  );
}
