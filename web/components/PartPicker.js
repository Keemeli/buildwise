"use client";

import { useEffect, useMemo, useState } from "react";
import { COMPONENTS, cheapestOffer } from "@/mock/components";
import { issuesForCandidate, issueKey } from "@/lib/compat";
import { formatEuros } from "@/lib/api";
import PartIcon from "./PartIcon";
import { t } from "@/strings";

// Short spec line shown under each part name.
function specSummary(c) {
  const s = c.specs;
  switch (c.category) {
    case "cpu":
      return `${s.socket} · ${t.specs.coresThreads(s.cores, s.threads)} · ${s.tdp_w} W${s.cooler_included ? ` · ${t.specs.coolerIncluded}` : ""}`;
    case "cooler":
      return `${t.specs.height(s.height_mm)} · ${t.specs.upToWatts(s.tdp_rating_w)}`;
    case "motherboard":
      return `${s.socket} · ${s.chipset} · ${s.memory_type} · ${s.form_factor}`;
    case "memory":
      return `${s.memory_type} · ${s.capacity_gb} GB (${s.modules}×${s.capacity_gb / s.modules}) · ${s.speed_mhz} MHz`;
    case "gpu":
      return `${t.specs.vram(s.vram_gb)} · ${s.tdp_w} W · ${s.length_mm} mm`;
    case "storage":
      return `${s.capacity_gb >= 1000 ? s.capacity_gb / 1000 + " TB" : s.capacity_gb + " GB"} · ${s.interface}`;
    case "psu":
      return `${s.wattage_w} W · ${s.efficiency}${s.modular ? ` · ${t.specs.modular}` : ""}`;
    case "case":
      return `${s.form_factors.join(" / ")} · ${t.specs.gpuUpTo(s.max_gpu_length_mm)} · ${t.specs.coolerUpTo(s.max_cooler_height_mm)}`;
    default:
      return "";
  }
}

export { specSummary };

export default function PartPicker({ slot, build, onSelect, onClose }) {
  const [query, setQuery] = useState("");

  // Close with the Escape key
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const parts = useMemo(() => {
    const q = query.trim().toLowerCase();
    return COMPONENTS.filter((c) => c.category === slot.category)
      .filter((c) => !q || `${c.brand} ${c.model}`.toLowerCase().includes(q))
      .map((c) => ({ component: c, offer: cheapestOffer(c), issues: issuesForCandidate(build, c) }))
      // Compatible parts first, then cheapest first
      .sort((a, b) => a.issues.length - b.issues.length || a.offer.priceCents - b.offer.priceCents);
  }, [slot.category, build, query]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={t.picker.title(t.categories[slot.category])} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">
            <span className="slot-icon filled-icon">
              <PartIcon category={slot.category} size={32} />
            </span>
            {t.picker.title(t.categories[slot.category])}
          </h2>
          <button className="icon-button" onClick={onClose} aria-label={t.picker.close}>
            ✕
          </button>
        </div>

        <input
          className="search"
          placeholder={t.picker.searchPlaceholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />

        <ul className="picker-list">
          {parts.map(({ component, offer, issues }) => (
            <li key={component.id} className={issues.length ? "picker-item incompatible" : "picker-item"}>
              <div className="picker-info">
                <div className="part-name">
                  {component.brand} {component.model}
                </div>
                <div className="part-specs">{specSummary(component)}</div>
                {issues.map((issue) => (
                  <div key={issueKey(issue)} className="issue-inline error">
                    ✕ {t.issues[issue.code](issue.params)}
                  </div>
                ))}
              </div>
              <div className="picker-price">
                <div className="price">{formatEuros(offer.priceCents)}</div>
                <div className="muted small">
                  {offer.shop}
                  {component.offers.length > 1 && ` · ${t.picker.shops(component.offers.length)}`}
                </div>
              </div>
              <button className="button small-button" onClick={() => onSelect(component)}>
                {t.picker.add}
              </button>
            </li>
          ))}
          {parts.length === 0 && <li className="muted empty">{t.picker.noMatches(query)}</li>}
        </ul>
      </div>
    </div>
  );
}
