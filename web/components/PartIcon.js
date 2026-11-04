// Simple line icons for each part slot. Drawn on a 48×48 grid, colour comes from `currentColor`.

const ICONS = {
  cpu: (
    <>
      <rect x="12" y="12" width="24" height="24" rx="3" />
      <rect x="18" y="18" width="12" height="12" rx="1.5" />
      <path d="M18 6v6M24 6v6M30 6v6M18 36v6M24 36v6M30 36v6M6 18h6M6 24h6M6 30h6M36 18h6M36 24h6M36 30h6" />
    </>
  ),
  cooler: (
    <>
      <rect x="6" y="6" width="36" height="36" rx="5" />
      <circle cx="24" cy="24" r="3.5" />
      <path d="M24 20.5c0-6 3-9.5 8-9.5-1 5-3.5 8.5-8 9.5ZM27.5 24c6 0 9.5 3 9.5 8-5-1-8.5-3.5-9.5-8ZM24 27.5c0 6-3 9.5-8 9.5 1-5 3.5-8.5 8-9.5ZM20.5 24c-6 0-9.5-3-9.5-8 5 1 8.5 3.5 9.5 8Z" />
    </>
  ),
  motherboard: (
    <>
      <rect x="6" y="6" width="36" height="36" rx="3" />
      <rect x="11" y="11" width="12" height="12" rx="1.5" />
      <path d="M29 11v15M33 11v15M37 11v15" />
      <path d="M11 30h26M11 35h18" />
    </>
  ),
  memory: (
    <>
      <rect x="4" y="15" width="40" height="15" rx="2" />
      <rect x="9" y="19" width="6" height="7" />
      <rect x="18" y="19" width="6" height="7" />
      <rect x="27" y="19" width="6" height="7" />
      <path d="M8 30v4M12 30v4M16 30v4M20 30v4M28 30v4M32 30v4M36 30v4M40 30v4" />
    </>
  ),
  gpu: (
    <>
      <rect x="4" y="12" width="40" height="22" rx="3" />
      <circle cx="16" cy="23" r="6" />
      <circle cx="32" cy="23" r="6" />
      <path d="M16 19v8M12 23h8M32 19v8M28 23h8" />
      <path d="M10 34v4h16v-4" />
    </>
  ),
  storage: (
    <>
      <rect x="4" y="17" width="40" height="14" rx="2" />
      <rect x="10" y="20" width="10" height="8" rx="1" />
      <rect x="23" y="20" width="8" height="8" rx="1" />
      <path d="M38 20v8" />
      <circle cx="41" cy="24" r="1" />
    </>
  ),
  psu: (
    <>
      <rect x="5" y="10" width="38" height="28" rx="3" />
      <circle cx="19" cy="24" r="9" />
      <path d="M19 15v18M10 24h18M12.6 17.6l12.8 12.8M25.4 17.6 12.6 30.4" />
      <path d="M33 17h5M33 22h5M33 27h5" />
    </>
  ),
  case: (
    <>
      <rect x="12" y="4" width="24" height="40" rx="3" />
      <circle cx="24" cy="12" r="2" />
      <path d="M17 19h14M17 23h14M17 27h14M17 31h14" />
      <path d="M17 38h4" />
    </>
  ),
};

export default function PartIcon({ category, size = 36 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[category]}
    </svg>
  );
}
