"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cheapestOffer } from "@/lib/catalog-shared";
import { useCategory } from "@/lib/useCategory";
import { issuesForCandidate, issueKey } from "@/lib/compat";
import { UNKNOWN, OTHER, optionKeys, facetsFor, facetOptions, applyFacets } from "@/lib/facets";
import { formatEuros } from "@/lib/api";
import { matchesQuery, queryTokens, searchKey } from "@/lib/search";
import PartIcon from "./PartIcon";
import ProductImage from "./ProductImage";
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

// A facet row shows at most this many options, so it fits on one line, until "+N more"
// is pressed (ASUS alone makes boards with 30+ chipsets, many of them a single board).
const MAX_OPTIONS = 6;

// Splits a row into the options shown at first and the ones behind "+N more", both in
// the row's own order. First: the MAX_OPTIONS known options with the most parts, plus
// every ticked one. Behind "+N more": the rest, minus those with a single part — they
// are noise in the row, and the part is still in the list without the filter.
function splitOptions(facet, options, selections) {
  const known = options.filter(({ key }) => key !== UNKNOWN);
  if (known.length <= MAX_OPTIONS) return { top: options, more: [] };
  const ticked = selections[facet.id] ?? [];
  const best = new Set(
    [...known]
      .sort((a, b) => b.count - a.count)
      .slice(0, MAX_OPTIONS)
      .map(({ key }) => key),
  );
  const isTop = ({ key }) => best.has(key) || ticked.includes(key);
  return {
    top: options.filter(isTop),
    more: options.filter((option) => !isTop(option) && option.count > 1),
  };
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

// Rows drawn per "show more" step.
const PAGE = 60;

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
  // The open filter dropdown: "price", a facet id, or null. One at a time.
  const [openMenu, setOpenMenu] = useState(null);
  const barRef = useRef(null);
  // Price range in euros, as typed. The fields sit in the "Price" dropdown.
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const minCents = euroCents(priceMin);
  const maxCents = euroCents(priceMax);
  const priceActive = minCents !== null || maxCents !== null;
  // min > max matches nothing; say so instead of showing an unexplained empty list.
  const priceInverted = minCents !== null && maxCents !== null && minCents > maxCents;
  // Order within the compatible and incompatible groups: "cheapest" | "priciest" | "name".
  const [sort, setSort] = useState("cheapest");
  // Facet ids whose "+N more" was pressed: they list every option.
  const [expanded, setExpanded] = useState([]);

  // Escape closes an open filter dropdown first, then the picker.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      if (openMenu) setOpenMenu(null);
      else onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, openMenu]);

  // A click outside the filter bar closes the open dropdown. Clicks inside it are the
  // dropdown's own (ticking several options keeps it open) or another filter's button.
  useEffect(() => {
    if (!openMenu) return;
    const onDown = (e) => {
      if (!barRef.current?.contains(e.target)) setOpenMenu(null);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [openMenu]);

  function toggleMenu(id) {
    setOpenMenu((current) => (current === id ? null : id));
  }

  const facets = facetsFor(slot.category);
  const { parts: categoryParts, loading, error: loadError } = useCategory(slot.category);

  // Every part in this category, with its cheapest offer and the errors it would cause.
  const all = useMemo(
    () =>
      (categoryParts ?? []).map((c) => ({
        component: c,
        key: searchKey(c.name),
        offer: cheapestOffer(c),
        issues: issuesForCandidate(build, c),
      })),
    [categoryParts, build],
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
    const byName = new Intl.Collator(t.locale, { sensitivity: "base", numeric: true });
    const compare = {
      cheapest: (a, b) => a.offer.priceCents - b.offer.priceCents,
      priciest: (a, b) => b.offer.priceCents - a.offer.priceCents,
      name: (a, b) => byName.compare(a.component.name, b.component.name),
    }[sort];
    const parts = applyFacets(pool, facets, selections, getComponent)
      // Compatible parts always first, then the chosen order
      .sort((a, b) => a.issues.length - b.issues.length || compare(a, b));
    return { parts, options, incompatible };
  }, [all, facets, query, selections, showAll, minCents, maxCents, sort, t.locale]);

  const anySelected = priceActive || Object.values(selections).some((keys) => keys.length > 0);

  // Long categories (700+ memory kits) are drawn PAGE rows at a time. Any change to the
  // search, filters or order starts again from the first page.
  const listKey = JSON.stringify([slot.category, query, selections, showAll, priceMin, priceMax, sort]);
  const [page, setPage] = useState({ listKey, rows: PAGE });
  const shownRows = page.listKey === listKey ? page.rows : PAGE;
  const shownParts = view.parts.slice(0, shownRows);
  const hiddenRows = view.parts.length - shownParts.length;

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
    // A changed parent also folds its child rows back to the first options: unticking
    // ASUS hides H770 & co. again instead of keeping them open for the next vendor.
    const childIds = facets.filter((f) => f.parent === facetId).map((f) => f.id);
    if (childIds.length > 0) setExpanded((ids) => ids.filter((id) => !childIds.includes(id)));
  }

  function clearFilters() {
    setSelections({});
    setExpanded([]);
    setOpenMenu(null);
    setPriceMin("");
    setPriceMax("");
  }

  // One dropdown per facet that has a choice to offer. A child facet (chipset under the
  // board vendor) has none until a parent option is ticked, so its button appears then.
  const facetMenus = view.options
    .map(({ facet, options }) => {
      const { top, more } = splitOptions(facet, visibleOptions(facet, options, selections), selections);
      if (expanded.includes(facet.id)) {
        const keep = new Set([...top, ...more].map((o) => o.key));
        return { facet, options: options.filter((o) => keep.has(o.key)), hidden: 0 };
      }
      return { facet, options: top, hidden: more.length };
    })
    .filter(({ options }) => options.length > 0);

  let priceLabel = t.picker.price;
  if (priceActive) priceLabel = t.picker.priceRange(minCents === null ? null : priceMin.trim(), maxCents === null ? null : priceMax.trim());

  let emptyText = t.picker.noFilterMatches;
  if (loading) emptyText = t.picker.loading;
  else if (loadError) emptyText = t.picker.loadError;
  else if (all.length === 0) emptyText = t.picker.emptyCategory;
  else if (priceInverted) emptyText = t.picker.priceInverted;
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

        <div className="picker-search-row">
          <input
            className="search"
            placeholder={t.picker.searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <select className="sort-select" aria-label={t.picker.sortLabel} value={sort} onChange={(e) => setSort(e.target.value)}>
            {["cheapest", "priciest", "name"].map((key) => (
              <option key={key} value={key}>
                {t.picker.sort[key]}
              </option>
            ))}
          </select>
        </div>

        {all.length > 0 && (
          <div className="filter-bar" ref={barRef} role="group" aria-label={t.picker.filters}>
            <div className="filter-item">
              <button
                type="button"
                className={`chip${priceActive ? " on" : ""}`}
                aria-expanded={openMenu === "price"}
                onClick={() => toggleMenu("price")}
              >
                {priceLabel} <span aria-hidden="true">{openMenu === "price" ? "▴" : "▾"}</span>
              </button>
              {openMenu === "price" && (
                <div className="filter-menu price-fields" role="group" aria-label={t.picker.price}>
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="10"
                    placeholder={t.picker.priceMin}
                    aria-label={t.picker.priceMin}
                    value={priceMin}
                    onChange={(e) => setPriceMin(e.target.value)}
                    autoFocus
                  />
                  <span className="muted">–</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="10"
                    placeholder={t.picker.priceMax}
                    aria-label={t.picker.priceMax}
                    value={priceMax}
                    onChange={(e) => setPriceMax(e.target.value)}
                  />
                  <span className="muted">€</span>
                </div>
              )}
            </div>

            {facetMenus.map(({ facet, options, hidden }) => {
              const ticked = selections[facet.id] ?? [];
              const label = t.picker.facets[facet.id];
              const open = openMenu === facet.id;
              return (
                <div key={facet.id} className="filter-item">
                  <button
                    type="button"
                    className={`chip${ticked.length > 0 ? " on" : ""}`}
                    aria-expanded={open}
                    onClick={() => toggleMenu(facet.id)}
                  >
                    {ticked.length > 0 ? t.picker.filterSummary(label, ticked.map((key) => optionLabel(facet, key, t))) : label}{" "}
                    <span aria-hidden="true">{open ? "▴" : "▾"}</span>
                  </button>
                  {open && (
                    <div className="filter-menu" role="group" aria-label={label}>
                      {options.map(({ key, count }) => {
                        const on = ticked.includes(key);
                        return (
                          <label
                            key={key}
                            className={`filter-option${count === 0 && !on ? " zero" : ""}${key === UNKNOWN ? " unknown" : ""}`}
                          >
                            <input type="checkbox" checked={on} onChange={() => toggleOption(facet.id, key)} />
                            <span>{optionLabel(facet, key, t)}</span>
                            <span className="chip-count">{count}</span>
                          </label>
                        );
                      })}
                      {hidden > 0 && (
                        <button
                          type="button"
                          className="link-button filter-more"
                          onClick={() => setExpanded((ids) => [...ids, facet.id])}
                        >
                          {t.picker.moreOptions(hidden)}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {priceInverted && (
          <p className="price-warning" role="status">
            {t.picker.priceInverted}
          </p>
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
          {shownParts.map(({ component, offer, issues }) => (
            <li key={component.id} className={issues.length ? "picker-item incompatible" : "picker-item"}>
              <div className="picker-thumb">
                <ProductImage src={component.image} alt={component.name} category={slot.category} size={56} />
              </div>
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
          {view.parts.length === 0 && (
            <li className="muted empty" role={loading || loadError ? "status" : undefined}>
              {emptyText}
            </li>
          )}
          {hiddenRows > 0 && (
            <li className="picker-more">
              <button
                type="button"
                className="button secondary"
                onClick={() => setPage({ listKey, rows: shownRows + PAGE })}
              >
                {t.picker.showMore(hiddenRows)}
              </button>
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
