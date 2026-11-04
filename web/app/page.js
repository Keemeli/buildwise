"use client";

import { useMemo, useState } from "react";
import { SLOTS, cheapestOffer, findComponent, chipsetKey } from "@/lib/catalog";
import { FPS_BASELINE, PERF_BY_CHIPSET } from "@/mock/fps";
import { GAMES } from "@/mock/build";
import { checkCompatibility, checkCoverage, powerBasis, issueKey } from "@/lib/compat";
import { formatEuros } from "@/lib/api";
import PartPicker, { specSummary } from "@/components/PartPicker";
import FpsChart from "@/components/FpsChart";
import BudgetForm from "@/components/BudgetForm";
import PartIcon from "@/components/PartIcon";
import PcPreview from "@/components/PcPreview";
import { t } from "@/strings";

export default function BuilderPage() {
  // { cpu: "cpu-7600", gpu: "gpu-5070", ... } — ids of the chosen parts
  const [selectedIds, setSelectedIds] = useState({});
  const [openSlot, setOpenSlot] = useState(null);
  const [game, setGame] = useState(GAMES[0].id);
  // { cpu: componentObject | null, ... }
  const build = useMemo(
    () => Object.fromEntries(SLOTS.map((s) => [s.category, findComponent(selectedIds[s.category])])),
    [selectedIds],
  );

  const chosen = SLOTS.map((s) => build[s.category]).filter(Boolean);
  const totalCents = chosen.reduce((sum, c) => sum + cheapestOffer(c).priceCents, 0);
  const { watts, basis: powerBasisKind } = powerBasis(build);
  const issues = checkCompatibility(build);
  const coverage = checkCoverage(build);
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

  function selectPart(component) {
    setSelectedIds((prev) => ({ ...prev, [component.category]: component.id }));
    setOpenSlot(null);
  }

  function removePart(category) {
    setSelectedIds((prev) => {
      const next = { ...prev };
      delete next[category];
      return next;
    });
  }

  return (
    <div className="builder">
      {/* ---------- Main: part slots ---------- */}
      <section className="builder-main">
        <div className="builder-title">
          <h1>{t.builder.title}</h1>
          {chosen.length > 0 && (
            <button className="link-button" onClick={() => setSelectedIds({})}>
              {t.builder.clearAll}
            </button>
          )}
        </div>

        <ul className="slots">
          {SLOTS.map((slot) => {
            const part = build[slot.category];
            const offer = part && cheapestOffer(part);
            const slotErrors = errors.filter((e) => e.parts.includes(slot.category));

            return (
              <li
                key={slot.category}
                className={`slot${part ? " filled" : ""}${slotErrors.length ? " has-error" : ""}`}
              >
                <div className="slot-label">
                  <span className="slot-icon">
                    <PartIcon category={slot.category} />
                  </span>
                  {t.categories[slot.category]}
                </div>

                {part ? (
                  <>
                    <div className="slot-part">
                      <a href={offer.url} target="_blank" rel="noopener noreferrer" className="part-name">
                        {part.name}
                      </a>
                      <div className="part-specs">{specSummary(part)}</div>
                    </div>
                    <div className="slot-price">
                      <div className="price">{formatEuros(offer.priceCents)}</div>
                      <div className="muted small">{offer.shop}</div>
                    </div>
                    <div className="slot-actions">
                      <button className="link-button" onClick={() => setOpenSlot(slot)}>
                        {t.builder.change}
                      </button>
                      <button
                        className="icon-button"
                        onClick={() => removePart(slot.category)}
                        aria-label={t.builder.remove(t.categories[slot.category])}
                      >
                        ✕
                      </button>
                    </div>
                  </>
                ) : (
                  <button className="add-part" onClick={() => setOpenSlot(slot)}>
                    {t.builder.choose(t.categories[slot.category])}
                  </button>
                )}
              </li>
            );
          })}
        </ul>

        <details className="card budget-card">
          <summary>{t.builder.budgetCard}</summary>
          <BudgetForm />
        </details>
      </section>

      {/* ---------- Sidebar: summary ---------- */}
      <aside className="builder-side">
        <div className="card preview-card">
          <PcPreview build={build} errorParts={errorParts} gpuTooLong={gpuTooLong} />
        </div>

        <div className="card">
          <h2>{t.builder.compatibility}</h2>
          {chosen.length === 0 ? (
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
            <span className="stat-value">{formatEuros(totalCents)}</span>
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
              {chosen.length} / {SLOTS.length}
            </span>
          </div>
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
        <PartPicker slot={openSlot} build={build} onSelect={selectPart} onClose={() => setOpenSlot(null)} />
      )}
    </div>
  );
}
