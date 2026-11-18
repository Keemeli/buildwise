"use client";

import { useT } from "@/lib/locale";

// 2D side view of the case, as seen through the side window of a PC standing on a desk:
// rear (I/O, GPU bracket, PSU) on the left, front on the right.
// Parts appear when chosen; parts with a compatibility error turn red.
// Sizes are illustrative, not to scale.

// Parts the user already owns are drawn dashed, also when the model is not known.
function cls(category, build, errorParts, owned) {
  let c = "pv-part";
  if (owned[category]) c += " pv-owned";
  else if (!build[category]) c += " pv-off";
  if (errorParts.has(category)) c += " pv-error";
  return c;
}

export default function PcPreview({ build, owned = {}, errorParts, gpuTooLong }) {
  const t = useT();
  const gpuWidth = gpuTooLong ? 330 : 200;

  return (
    <svg viewBox="0 0 360 410" className="pc-preview" role="img" aria-label={t.preview.label}>
      {/* Case */}
      <rect x="20" y="20" width="320" height="360" rx="8" className={`pv-case${errorParts.has("case") ? " pv-case-error" : ""}${owned.case ? " pv-case-owned" : ""}`} />
      <line x1="30" y1="295" x2="330" y2="295" className="pv-shroud" />
      <text x="20" y="400" className="pv-text">
        {t.preview.rear}
      </text>
      <text x="340" y="400" className="pv-text" textAnchor="end">
        {t.preview.front}
      </text>
      {Object.values(owned).some(Boolean) && (
        <text x="180" y="400" className="pv-text" textAnchor="middle">
          {t.preview.owned}
        </text>
      )}

      {/* Empty-slot outlines */}
      <rect x="60" y="40" width="190" height="240" rx="4" className="pv-slot" />
      <rect x="35" y="310" width="125" height="55" rx="4" className="pv-slot" />

      {/* Motherboard */}
      <g className={cls("motherboard", build, errorParts, owned) + " pv-board"}>
        <rect x="60" y="40" width="190" height="240" rx="4" />
        <rect x="60" y="50" width="8" height="70" className="pv-io" />
        <text x="75" y="268" className="pv-text">
          {t.categories.motherboard}
        </text>
      </g>

      {/* Cooler: see-through so the CPU stays visible */}
      <g className={cls("cooler", build, errorParts, owned) + " pv-cooler"}>
        <rect x="110" y="52" width="84" height="100" rx="6" />
        <path d="M110 64h84M110 76h84M110 128h84M110 140h84" className="pv-fins" />
        <circle cx="152" cy="102" r="34" className="pv-fan" />
        <text x="152" y="166" className="pv-text" textAnchor="middle">
          {t.preview.cooler}
        </text>
      </g>

      {/* CPU (drawn after the cooler so it shows through) */}
      <g className={cls("cpu", build, errorParts, owned)}>
        <rect x="130" y="80" width="44" height="44" rx="3" />
        <text x="152" y="106" className="pv-text pv-on-part" textAnchor="middle">
          {t.preview.cpu}
        </text>
      </g>

      {/* Memory */}
      <g className={cls("memory", build, errorParts, owned)}>
        <rect x="210" y="56" width="8" height="96" rx="2" />
        <rect x="224" y="56" width="8" height="96" rx="2" />
      </g>

      {/* Storage (M.2) */}
      <g className={cls("storage", build, errorParts, owned)}>
        <rect x="150" y="178" width="60" height="10" rx="2" />
        <text x="144" y="187" className="pv-text" textAnchor="end">
          {t.preview.storage}
        </text>
      </g>

      {/* GPU: bracket at the rear wall, extends towards the front */}
      <g className={cls("gpu", build, errorParts, owned)}>
        <rect x="30" y="200" width={gpuWidth} height="40" rx="4" />
        <rect x="24" y="196" width="6" height="48" className="pv-bracket" />
        <circle cx="60" cy="220" r="14" className="pv-fan" />
        <circle cx={gpuTooLong ? 300 : 205} cy="220" r="14" className="pv-fan" />
        <text x="132" y="224" className="pv-text pv-on-part" textAnchor="middle">
          {t.categories.gpu}
        </text>
      </g>

      {/* PSU */}
      <g className={cls("psu", build, errorParts, owned)}>
        <rect x="35" y="310" width="125" height="55" rx="4" />
        <circle cx="75" cy="337" r="18" className="pv-fan" />
        <text x="148" y="342" className="pv-text" textAnchor="end">
          {t.preview.psu}
        </text>
      </g>
    </svg>
  );
}
