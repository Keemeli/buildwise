"use client";

import { useState } from "react";

// The shop a part is bought from: the shop's own logo where we have one, and a generated
// monogram for any shop we do not yet have a logo for (so a row never shows an empty gap),
// and the monogram again if a logo file fails to load.
//
// The logos are the shops' property, used the way a price comparison names its sources: to
// say where a price comes from, with no implication of endorsement or partnership. They are
// plain <img> tags, not next/image — three small static files do not need optimising, and
// the Vercel image quota stays for product photos (see ProductImage.js).
//
// Heights differ per logo because the marks differ: Datatronic and Proshop are wide
// wordmarks whose names are the artwork, while Jimms is a badge that is unreadable below
// ~24 px. The width is left free (capped) so nothing is stretched.
const SHOPS = {
  datatronic: { logo: "/logos/datatronic.svg", height: 14, maxWidth: 140 },
  jimms: { logo: "/logos/jimms.webp", height: 24, maxWidth: 48 },
  proshop: { logo: "/logos/proshop.svg", height: 12, maxWidth: 160 },
};

function entryFor(shop) {
  const key = String(shop ?? "").toLowerCase();
  const match = Object.keys(SHOPS).find((name) => key.includes(name));
  return match ? SHOPS[match] : null;
}

function Monogram({ shop, size }) {
  return (
    <>
      <span
        className="shop-mark shop-other"
        style={{ width: size, height: size, fontSize: Math.round(size * 0.6) }}
        aria-hidden="true"
      >
        {(String(shop).trim()[0] || "?").toUpperCase()}
      </span>
      <span className="shop-name">{shop}</span>
    </>
  );
}

export default function ShopBadge({ shop, size = 18 }) {
  // The URL that failed, not a flag: a different shop gets a fresh try.
  const [failed, setFailed] = useState(null);
  if (!shop) return null;

  const entry = entryFor(shop);
  if (entry && failed !== entry.logo) {
    return (
      <span className="shop-badge">
        {/* eslint-disable-next-line @next/next/no-img-element -- Three small static logo
            files: next/image would spend the Vercel image quota on marks that never change. */}
        <img
          className="shop-logo"
          src={entry.logo}
          alt={shop}
          style={{ height: entry.height, maxWidth: entry.maxWidth }}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(entry.logo)}
        />
      </span>
    );
  }

  return (
    <span className="shop-badge">
      <Monogram shop={shop} size={size} />
    </span>
  );
}
