"use client";

import { useEffect, useMemo, useState } from "react";
import { COMPONENTS, cheapestOffer } from "@/lib/catalog";
import { issuesForCandidate, issueKey } from "@/lib/compat";
import { formatEuros } from "@/lib/api";
import PartIcon from "./PartIcon";
import { t } from "@/strings";

// Storage capacity. The normaliser currently counts 1 TB as 1024 GB, so both
// 1000 and 1024 multiples are shown as whole terabytes.
function formatCapacity(gb) {
  if (gb >= 1000) {
    const tb = gb % 1024 === 0 ? gb / 1024 : gb / 1000;
    return `${Math.round(tb * 10) / 10} TB`;
  }
  return `${gb} GB`;
}

// Joins the parts that are known. A missing spec is left out, never guessed.
const line = (...parts) => parts.filter((p) => p !== null && p !== undefined && p !== false && p !== "").join(" · ");
const has = (v) => v !== null && v !== undefined;

// Short spec line shown under each part name.
function specSummary(c) {
  const s = c.specs;
  switch (c.category) {
    case "cpu":
      return line(
        s.socket,
        has(s.base_clock_ghz) && t.specs.clock(s.base_clock_ghz),
        has(s.cache_mb) && t.specs.cache(s.cache_mb),
        has(s.tdp_w) && `${s.tdp_w} W`,
      );
    case "cooler":
      return line(has(s.height_mm) && t.specs.height(s.height_mm), has(s.tdp_rating_w) && t.specs.upToWatts(s.tdp_rating_w));
    case "motherboard":
      return line(s.socket, s.chipset, s.memory_type, s.form_factor);
    case "memory":
      return line(
        s.memory_type,
        has(s.capacity_gb) && (s.modules ? `${s.capacity_gb} GB (${s.modules.count}×${s.modules.size_gb} GB)` : `${s.capacity_gb} GB`),
        has(s.speed_mhz) && `${s.speed_mhz} MHz`,
        has(s.cas_latency) && `CL${s.cas_latency}`,
        s.form_factor === "SO-DIMM" && "SO-DIMM",
      );
    case "gpu":
      return line(
        s.chipset,
        has(s.vram_gb) && `${s.vram_gb} GB${s.memory_type ? ` ${s.memory_type}` : ""}`,
        has(s.tdp_w) && `${s.tdp_w} W`,
        has(s.length_mm) && `${s.length_mm} mm`,
      );
    case "storage":
      return line(has(s.capacity_gb) && formatCapacity(s.capacity_gb), s.interface, s.form_factor, has(s.pcie_gen) && `PCIe ${s.pcie_gen}`);
    case "psu":
      return line(has(s.wattage_w) && `${s.wattage_w} W`, s.efficiency, s.form_factor, s.modular && t.specs.modular);
    case "case":
      return line(
        s.form_factor,
        has(s.color) && (t.specs.colors[s.color] ?? s.color),
        has(s.max_gpu_length_mm) && t.specs.gpuUpTo(s.max_gpu_length_mm),
      );
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
      .filter((c) => !q || c.name.toLowerCase().includes(q))
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
                  {component.name}
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
          {parts.length === 0 && (
            <li className="muted empty">{query.trim() ? t.picker.noMatches(query) : t.picker.emptyCategory}</li>
          )}
        </ul>
      </div>
    </div>
  );
}
