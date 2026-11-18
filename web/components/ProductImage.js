"use client";

import { useState } from "react";
import PartIcon from "./PartIcon";

// A shop's product photo at a fixed size, so the list does not jump while it loads.
// Parts without an image (about 8 %), or whose image fails to load, show the slot icon.
export default function ProductImage({ src, alt, category, size = 56 }) {
  // The URL that failed, not a flag: a new part in the same slot gets a fresh try.
  const [failedSrc, setFailedSrc] = useState(null);

  if (!src || failedSrc === src) {
    return <PartIcon category={category} size={Math.round(size * 0.7)} />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- Shop images are shown as-is; next/image optimisation would spend the Vercel free-tier image quota.
    <img
      className="product-image"
      src={src}
      alt={alt}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailedSrc(src)}
    />
  );
}
