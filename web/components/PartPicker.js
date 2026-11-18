"use client";

import { useEffect, useMemo, useState } from "react";
import { COMPONENTS, cheapestOffer } from "@/lib/catalog";
import { issuesForCandidate, issueKey } from "@/lib/compat";
import { UNKNOWN, OTHER, optionKeys, facetsFor, facetOptions, applyFacets } from "@/lib/facets";
import { formatEuros } from "@/lib/api";
import { matchesQuery, queryTokens, searchKey } from "@/lib/search";
import PartIcon from "./PartIcon";
import { useT } from "@/lib/locale";

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
function specSummary(c, t) {
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
      return line(has(s.wattage_w) && `${s.wattage_w} W`, s.efficiency, s.form_factor, has(s.modular) && t.specs.cabling[s.modular]);
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

// Picker rows are { component, offer, issues }; the facet helpers read the component.
const getComponent = (row) => row.component;

function optionLabel(facet, key, t) {
  if (key === UNKNOWN) return t.picker.unknown;
  if (key === OTHER) return t.picker.other;
  if (facet.id === "wattage") return t.picker.wattage[key] ?? key;
  if (facet.id === "capacity") return t.picker.capacity[key] ?? key;
  if (facet.id === "interface" && t.picker.interfaceGroups[key]) return t.picker.interfaceGroups[key];
  if (facet.id === "cpuSeries") return t.picker.cpuSeries[key] ?? key;
  if (facet.id === "wifi") return t.picker.wifi[key] ?? key;
  if (facet.id === "moduleSize") return `${key} GB`;
  if (facet.id === "cabling") return t.picker.cabling[key] ?? key;
  if (facet.id === "modularType") return t.picker.modularType[key] ?? key;
  if (facet.id === "gpuGeneration") return t.picker.gpuGeneration[key] ?? key;
  if (facet.id === "vram") return key === "gt16" ? t.picker.vramOver16 : `${key} GB`;
  return key; // spec values are shown as the pipeline writes them (language-neutral)
}

// A price field's text in euros ("149,90" or "150") → cents, or null when empty or not a number.
function euroCents(text) {
  const value = Number(String(text).trim().replace(",", "."));
  return String(text).trim() === "" || !Number.isFinite(value) || value < 0 ? null : Math.round(value * 100);
}

// A child facet (CPU series, board chipset, module size) appears only once a parent
// option is ticked, and then lists the options with parts under it. The counts already
// respect the parent's selection, so a zero count means "not under this parent".
function visibleOptions(facet, options, selections) {
  if (!facet.parent) return options;
  if ((selections[facet.parent] ?? []).length === 0) return [];
  const ticked = selections[facet.id] ?? [];
  const visible = options.filter(({ key, count }) => count > 0 || ticked.includes(key));
  // A single known option chooses nothing (an AM5 board is always DDR5), so the row stays
  // hidden; "not known" alone is no second choice.
  const known = visible.filter(({ key }) => key !== UNKNOWN);
  return known.length > 1 || ticked.length > 0 ? visible : [];
}

// The child options that have parts under the given parent options.
function childKeysUnder(rows, parent, child, parentKeys) {
  const keys = new Set();
  for (const { component } of rows) {
    if (optionKeys(parent, component).some((key) => parentKeys.includes(key))) {
      for (const key of optionKeys(child, component)) keys.add(key);
    }
  }
  return keys;
}

// owned: the slot is already marked as the user's own part.
// onSelect(component, { asOwned }) — asOwned when "I already have one" is on.
// onOwnedWithoutModel() — "I have one but don't know the model".
export default function PartPicker({ slot, build, owned = false, onSelect, onOwnedWithoutModel, onClose }) {
  const t = useT();
  const [query, setQuery] = useState("");
  // { [facetId]: optionKey[] } — ticked filter options
  const [selections, setSelections] = useState({});
  // Parts that don't fit the rest of the build are hidden by default, behind a "show all" toggle.
  const [showAll, setShowAll] = useState(false);
  // "I already have one": picking a part marks it as the user's own (not in price / budget).
  const [haveIt, setHaveIt] = useState(owned);
  // Price range in euros, as typed. The fields sit behind the "Price" button.
  const [priceOpen, setPriceOpen] = useState(false);
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const minCents = euroCents(priceMin);
  const maxCents = euroCents(priceMax);
  const priceActive = minCents !== null || maxCents !== null;

  // Close with the Escape key
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const facets = facetsFor(slot.category);

  // Every part in this category, with its cheapest offer and the errors it would cause.
  const all = useMemo(
    () =>
      COMPONENTS.filter((c) => c.category === slot.category).map((c) => ({
        component: c,
        key: searchKey(c.name),
        offer: cheapestOffer(c),
        issues: issuesForCandidate(build, c),
      })),
    [slot.category, build],
  );

  const view = useMemo(() => {
    const tokens = queryTokens(query);
    const searched = all.filter(
      (row) =>
        matchesQuery(row.key, tokens) &&
        (minCents === null || row.offer.priceCents >= minCents) &&
        (maxCents === null || row.offer.priceCents <= maxCents),
    );
    const incompatible = searched.filter((row) => row.issues.length > 0).length;
    const pool = showAll ? searched : searched.filter((row) => row.issues.length === 0);
    const options = facetOptions(pool, facets, selections, getComponent);
    const parts = applyFacets(pool, facets, selections, getComponent)
      // Compatible parts first, then cheapest first
      .sort((a, b) => a.issues.length - b.issues.length || a.offer.priceCents - b.offer.priceCents);
    return { parts, options, incompatible };
  }, [all, facets, query, selections, showAll, minCents, maxCents]);

  const anySelected = priceActive || Object.values(selections).some((keys) => keys.length > 0);

  function toggleOption(facetId, key) {
    setSelections((prev) => {
      const current = prev[facetId] ?? [];
      const next = current.includes(key) ? current.filter((k) => k !== key) : [...current, key];
      const updated = { ...prev, [facetId]: next };
      // A changed parent drops the ticked child options it has no parts in (Intel
      // unticks "Ryzen 5"), so no hidden selection keeps filtering the list.
      const parent = facets.find((f) => f.id === facetId);
      for (const child of facets.filter((f) => f.parent === facetId)) {
        const available = childKeysUnder(all, parent, child, next);
        updated[child.id] = (updated[child.id] ?? []).filter((k) => available.has(k));
      }
      return updated;
    });
  }

  function clearFilters() {
    setSelections({});
    setPriceMin("");
    setPriceMax("");
  }

  let priceLabel = t.picker.price;
  if (priceActive) priceLabel = t.picker.priceRange(minCents === null ? null : priceMin.trim(), maxCents === null ? null : priceMax.trim());

  let emptyText = t.picker.noFilterMatches;
  if (all.length === 0) emptyText = t.picker.emptyCategory;
  else if (query.trim() && !anySelected) emptyText = t.picker.noMatches(query);

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

        <label className={`have-it-toggle${haveIt ? " on" : ""}`}>
          <input type="checkbox" checked={haveIt} onChange={(e) => setHaveIt(e.target.checked)} />
          <span>
            <strong>{t.picker.haveIt(t.categories[slot.category])}</strong>
            <span className="muted small"> · {t.picker.haveItHint}</span>
          </span>
        </label>
        {haveIt && (
          <div className="have-it-help">
            <span>{t.picker.haveItHelp}</span>
            <button type="button" className="link-button" onClick={onOwnedWithoutModel}>
              {t.picker.noModel}
            </button>
          </div>
        )}

        <input
          className="search"
          placeholder={t.picker.searchPlaceholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />

        {all.length > 0 && (
          <div className="price-filter">
            <button
              type="button"
              className={`chip${priceActive ? " on" : ""}`}
              aria-expanded={priceOpen}
              onClick={() => setPriceOpen((open) => !open)}
            >
              {priceLabel} <span aria-hidden="true">{priceOpen ? "▴" : "▾"}</span>
            </button>
            {priceOpen && (
              <div className="price-fields">
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  placeholder={t.picker.priceMin}
                  aria-label={t.picker.priceMin}
                  value={priceMin}
                  onChange={(e) => setPriceMin(e.target.value)}
                />
                <span className="muted">–</span>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  placeholder={t.picker.priceMax}
                  aria-label={t.picker.priceMax}
                  value={priceMax}
                  onChange={(e) => setPriceMax(e.target.value)}
                />
                <span className="muted">€</span>
              </div>
            )}
          </div>
        )}

        {facets.length > 0 && all.length > 0 && (
          <div className="facets" aria-label={t.picker.filters}>
            {view.options.map(({ facet, options }) => ({ facet, options: visibleOptions(facet, options, selections) }))
              .filter(({ options }) => options.length > 0)
              .map(({ facet, options }) => (
              <div key={facet.id} className={`facet${facet.parent ? " facet-child" : ""}`} role="group" aria-label={t.picker.facets[facet.id]}>
                <span className="facet-label">{t.picker.facets[facet.id]}</span>
                <div className="facet-options">
                  {options.map(({ key, count }) => {
                    const on = (selections[facet.id] ?? []).includes(key);
                    return (
                      <button
                        key={key}
                        type="button"
                        className={`chip${on ? " on" : ""}${count === 0 && !on ? " zero" : ""}${key === UNKNOWN ? " unknown" : ""}`}
                        aria-pressed={on}
                        onClick={() => toggleOption(facet.id, key)}
                      >
                        {optionLabel(facet, key, t)}
                        <span className="chip-count">{count}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Shown whenever something is hidden, so a part never disappears silently. */}
        {(view.incompatible > 0 || showAll) && (
          <div className="compat-filter">
            <span>{showAll ? t.picker.showingAll : t.picker.compatibleOnly(view.incompatible)}</span>
            <button type="button" className="link-button" onClick={() => setShowAll((v) => !v)}>
              {showAll ? t.picker.showCompatibleOnly : t.picker.showAll}
            </button>
          </div>
        )}

        {all.length > 0 && (
          <div className="picker-status muted small">
            <span>{t.picker.resultCount(view.parts.length, all.length)}</span>
            {anySelected && (
              <button type="button" className="link-button" onClick={clearFilters}>
                {t.picker.clearFilters}
              </button>
            )}
          </div>
        )}

        <ul className="picker-list">
          {view.parts.map(({ component, offer, issues }) => (
            <li key={component.id} className={issues.length ? "picker-item incompatible" : "picker-item"}>
              <div className="picker-info">
                <div className="part-name">{component.name}</div>
                <div className="part-specs">{specSummary(component, t)}</div>
                {issues.map((issue) => (
                  <div key={issueKey(issue)} className="issue-inline error">
                    ✕ {t.issues[issue.code](issue.params)}
                  </div>
                ))}
              </div>
              <div className="picker-price">
                <div className="price">{formatEuros(offer.priceCents, t.locale)}</div>
                <div className="muted small">
                  {offer.shop}
                  {component.offers.length > 1 && ` · ${t.picker.shops(component.offers.length)}`}
                </div>
              </div>
              <button
                className={`button small-button${haveIt ? " secondary" : ""}`}
                onClick={() => onSelect(component, { asOwned: haveIt })}
              >
                {haveIt ? t.picker.addOwned : t.picker.add}
              </button>
            </li>
          ))}
          {view.parts.length === 0 && <li className="muted empty">{emptyText}</li>}
        </ul>
      </div>
    </div>
  );
}
