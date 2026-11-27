"use client";

import { useMemo, useState } from "react";
import { SLOTS, cheapestOffer, chipsetKey } from "@/lib/catalog-shared";
import { FPS_BASELINE, PERF_BY_CHIPSET } from "@/mock/fps";
import { GAMES } from "@/mock/build";
import { checkCompatibility, checkCoverage, powerBasis, issueKey } from "@/lib/compat";
import { formatEuros } from "@/lib/api";
import PartPicker, { specSummary } from "@/components/PartPicker";
import FpsChart from "@/components/FpsChart";
import BudgetForm from "@/components/BudgetForm";
import PartIcon from "@/components/PartIcon";
import ProductImage from "@/components/ProductImage";
import PcPreview from "@/components/PcPreview";
import { useT } from "@/lib/locale";

// A build can hold up to four drives. The first one is the regular "storage" slot (the
// one compatibility checks and the preview read); the others are keyed "storage:2"...
const MAX_STORAGE = 4;
const storageKey = (n) => (n === 1 ? "storage" : `storage:${n}`);

export default function BuilderPage() {
  const t = useT();
  // { cpu: component, gpu: component, "storage:2": component, ... } — the chosen parts, by slot key.
  // Whole objects, not ids: the catalogue is not in the page, only the categories the
  // pickers have fetched.
  const [selected, setSelected] = useState({});
  // How many drive rows are shown (1–4). Extra rows start empty.
  const [storageRows, setStorageRows] = useState(1);
  const [openSlot, setOpenSlot] = useState(null);
  const [game, setGame] = useState(GAMES[0].id);
  // { case: true, ... } — slots the user already owns. Not counted in the price or the budget.
  // An owned slot may still have a model chosen (e.g. their own RTX 3060), so checks can run.
  const [owned, setOwned] = useState({});
  // { cpu: componentObject | null, ... }
  const build = useMemo(
    () => Object.fromEntries(SLOTS.map((s) => [s.category, selected[s.category] ?? null])),
    [selected],
  );

  // The drives after the first one: [{ key: "storage:2", part }, ...]
  const extraDrives = Array.from({ length: storageRows - 1 }, (_, i) => {
    const key = storageKey(i + 2);
    return { key, part: selected[key] ?? null };
  });

  const ownedCategories = SLOTS.map((s) => s.category).filter((c) => owned[c]);
  // Owned, but the user hasn't said which model: checks that need it cannot run.
  const ownedUnknown = ownedCategories.filter((c) => !build[c]);
  // Every chosen part by slot key, extra drives included; owned parts are not paid for.
  const paid = [
    ...SLOTS.map((s) => [s.category, build[s.category]]),
    ...extraDrives.map((d) => [d.key, d.part]),
  ].filter(([key, part]) => part && !owned[key]);
  const totalCents = paid.reduce((sum, [, part]) => sum + cheapestOffer(part).priceCents, 0);
  const filledSlots = SLOTS.filter((s) => build[s.category] || owned[s.category]).length;
  const { watts, basis: powerBasisKind } = powerBasis(build);
  const issues = checkCompatibility(build, { ownedUnknown });
  const coverage = checkCoverage(build, { owned: ownedUnknown });
  const errors = issues.filter((i) => i.level === "error");
  const errorParts = new Set(errors.flatMap((e) => e.parts));
  const gpuTooLong = errors.some((e) => e.code === "gpuLength");

  // Problems first, then things we could not check
  const LEVEL_ORDER = { error: 0, warning: 1, unknown: 2 };
  const sortedIssues = [...issues].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level]);
  const hasProblems = issues.some((i) => i.level !== "unknown");
  const hasUnknowns = issues.some((i) => i.level === "unknown");

  const perf = build.gpu ? PERF_BY_CHIPSET[chipsetKey(build.gpu.specs.chipset)] : undefined;
  const fps = perf
    ? FPS_BASELINE[game].map((row) => ({
        ...row,
        min: Math.round(row.min * perf),
        max: Math.round(row.max * perf),
      }))
    : null;

  // Picked from the picker into the open slot. `asOwned`: a part the user already has.
  function pickPart(component, { asOwned = false } = {}) {
    const key = openSlot.key;
    setSelected((prev) => ({ ...prev, [key]: component }));
    setOwned((prev) => ({ ...prev, [key]: asOwned }));
    setOpenSlot(null);
  }

  // "I have one, but I don't know the model": owned, no part chosen.
  function markOwnedWithoutModel(key) {
    removePart(key);
    setOwned((prev) => ({ ...prev, [key]: true }));
    setOpenSlot(null);
  }

  function unmarkOwned(key) {
    setOwned((prev) => ({ ...prev, [key]: false }));
  }

  function clearAll() {
    setSelected({});
    setOwned({});
    setStorageRows(1);
  }

  function removePart(key) {
    setSelected((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  // Removes drive row n (1–4) and moves the drives after it up one row, so the first
  // drive — the one the checks read — is always filled while any drive is.
  function removeDrive(n) {
    const shift = (prev) => {
      const next = { ...prev };
      for (let i = n; i < storageRows; i += 1) {
        const later = prev[storageKey(i + 1)];
        if (later === undefined) delete next[storageKey(i)];
        else next[storageKey(i)] = later;
      }
      delete next[storageKey(storageRows)];
      return next;
    };
    if (storageRows === 1) {
      removePart("storage");
      return;
    }
    setSelected(shift);
    setOwned(shift);
    setStorageRows((rows) => rows - 1);
  }

  // One part row. `key` is the slot key ("cpu", "storage", "storage:2"); `part` defaults to
  // the build's part for the category; `label` overrides the category name ("Drive 2");
  // `onRemove` overrides plain removal (drives move up when one is removed).
  function renderSlot({ category, key, part = build[category], label, onRemove }) {
    const slot = { category, key };
    const offer = part && cheapestOffer(part);
    // Compatibility errors name categories; only the first drive is checked.
    const slotErrors = key === category ? errors.filter((e) => e.parts.includes(category)) : [];
    const isOwned = Boolean(owned[key]);
    const remove = onRemove ?? (() => removePart(key));
    // "Your part" badge; clicking it turns the slot back into a part to buy.
    const ownedBadge = (
      <button
        type="button"
        className="owned-badge"
        title={t.builder.notOwned}
        aria-label={`${t.builder.ownedBadge}: ${t.builder.notOwned}`}
        onClick={() => unmarkOwned(key)}
      >
        {t.builder.ownedBadge} <span aria-hidden="true">✕</span>
      </button>
    );

    return (
      <li
        key={key}
        className={`slot${part ? " filled" : ""}${isOwned ? " owned" : ""}${slotErrors.length ? " has-error" : ""}`}
      >
        <div className="slot-label">
          <span className="slot-icon">
            {part ? <ProductImage src={part.image} alt={part.name} category={category} size={52} /> : <PartIcon category={category} />}
          </span>
          {label ?? t.categories[category]}
        </div>

        {part ? (
          <>
            <div className="slot-part">
              <a href={offer.url} target="_blank" rel="noopener noreferrer" className="part-name">
                {part.name}
              </a>
              <div className="part-specs">{specSummary(part, t)}</div>
            </div>
            <div className="slot-price">
              {isOwned ? (
                ownedBadge
              ) : (
                <>
                  <div className="price">{formatEuros(offer.priceCents, t.locale)}</div>
                  <div className="muted small">{offer.shop}</div>
                </>
              )}
            </div>
            <div className="slot-actions">
              <button className="link-button" onClick={() => setOpenSlot(slot)}>
                {t.builder.change}
              </button>
              <button className="icon-button" onClick={remove} aria-label={t.builder.remove(label ?? t.categories[category])}>
                ✕
              </button>
            </div>
          </>
        ) : isOwned ? (
          <>
            <div className="slot-part">
              <div className="part-name">{t.builder.ownedNoModel}</div>
              <div className="part-specs">{t.builder.ownedNoModelHint}</div>
            </div>
            <div className="slot-price">{ownedBadge}</div>
            <div className="slot-actions">
              <button className="link-button" onClick={() => setOpenSlot(slot)}>
                {t.builder.chooseModel}
              </button>
            </div>
          </>
        ) : (
          <div className="slot-empty">
            <button className="add-part" onClick={() => setOpenSlot(slot)}>
              {t.builder.choose(label ?? t.categories[category])}
            </button>
            {/* An empty extra drive row can be taken away again */}
            {key !== category && (
              <button className="icon-button" onClick={remove} aria-label={t.builder.remove(label)}>
                ✕
              </button>
            )}
          </div>
        )}
      </li>
    );
  }

  return (
    <div className="builder">
      {/* ---------- Main: part slots ---------- */}
      <section className="builder-main">
        <div className="builder-title">
          <h1>{t.builder.title}</h1>
          {filledSlots > 0 && (
            <button className="link-button" onClick={clearAll}>
              {t.builder.clearAll}
            </button>
          )}
        </div>

        <ul className="slots">
          {SLOTS.flatMap((s) => {
            if (s.category !== "storage") return [renderSlot({ category: s.category, key: s.category })];
            const drives = [
              renderSlot({ category: "storage", key: "storage", onRemove: () => removeDrive(1),
                label: storageRows > 1 ? t.builder.driveN(1) : undefined }),
              ...extraDrives.map((d, i) =>
                renderSlot({ category: "storage", key: d.key, part: d.part, onRemove: () => removeDrive(i + 2),
                  label: t.builder.driveN(i + 2) }),
              ),
            ];
            // Another drive can be added once the first one is chosen (or owned), up to four.
            if (storageRows < MAX_STORAGE && (build.storage || owned.storage)) {
              drives.push(
                <li key="add-storage" className="slot slot-more">
                  <button className="add-part" onClick={() => setStorageRows((rows) => rows + 1)}>
                    {t.builder.addDrive(storageRows, MAX_STORAGE)}
                  </button>
                </li>,
              );
            }
            return drives;
          })}
        </ul>

        <details className="card budget-card">
          <summary>{t.builder.budgetCard}</summary>
          <BudgetForm owned={ownedCategories} />
        </details>
      </section>

      {/* ---------- Sidebar: summary ---------- */}
      <aside className="builder-side">
        <div className="card preview-card">
          <PcPreview build={build} owned={owned} errorParts={errorParts} gpuTooLong={gpuTooLong} />
        </div>

        <div className="card">
          <h2>{t.builder.compatibility}</h2>
          {filledSlots === 0 ? (
            <p className="muted small">{t.builder.addPartsToCheck}</p>
          ) : (
            <ul className="issues">
              {!hasProblems && (
                <li className={`issue ${coverage.done > 0 && !hasUnknowns ? "ok" : "neutral"}`}>
                  {coverage.done === 0
                    ? t.builder.checksNone
                    : t.builder.checksSummary({ done: coverage.done, total: coverage.total })}
                  {coverage.waitingFor.length > 0
                    ? ` ${t.builder.checksWaiting({
                        parts: coverage.waitingFor.map((c) => t.categories[c]).join(", "),
                      })}`
                    : ""}
                </li>
              )}
              {sortedIssues.map((issue) => (
                <li key={issueKey(issue)} className={`issue ${issue.level}`}>
                  {{ error: "✕", warning: "!", unknown: "?" }[issue.level]} {t.issues[issue.code](issue.params)}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <div className="summary-row">
            <span className="muted">{t.builder.total}</span>
            <span className="stat-value">{formatEuros(totalCents, t.locale)}</span>
          </div>
          <div className="summary-row">
            <span className="muted">{t.builder.powerDraw}</span>
            <span>{watts == null ? "–" : `${powerBasisKind === "manufacturerMin" ? "≥" : "~"}${watts} W`}</span>
          </div>
          {(powerBasisKind === "parts" || powerBasisKind === "manufacturerMin") && (
            <p className="muted small">
              {powerBasisKind === "parts" ? t.builder.powerFromParts : t.builder.powerFromMinimum}
            </p>
          )}
          <div className="summary-row">
            <span className="muted">{t.builder.partsChosen}</span>
            <span>
              {filledSlots} / {SLOTS.length}
            </span>
          </div>
          {ownedCategories.length > 0 && (
            <div className="summary-row">
              <span className="muted">{t.builder.ownedParts}</span>
              <span className="small">{ownedCategories.map((c) => t.categories[c]).join(", ")}</span>
            </div>
          )}
        </div>

        <div className="card">
          <h2>{t.builder.fpsTitle}</h2>
          <select value={game} onChange={(e) => setGame(e.target.value)} className="full-width">
            {GAMES.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          {fps ? (
            <>
              <FpsChart fps={fps} />
              <p className="muted small">{t.builder.fpsMockNote}</p>
            </>
          ) : (
            <p className="muted small">{build.gpu ? t.fps.noEstimate : t.builder.chooseGpuForFps}</p>
          )}
        </div>

      </aside>

      {openSlot && (
        <PartPicker
          slot={openSlot}
          build={build}
          owned={Boolean(owned[openSlot.key])}
          onSelect={pickPart}
          onOwnedWithoutModel={() => markOwnedWithoutModel(openSlot.key)}
          onClose={() => setOpenSlot(null)}
        />
      )}
    </div>
  );
}
