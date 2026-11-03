"use client";

import { useMemo, useState } from "react";
import { SLOTS, FPS_BASELINE, cheapestOffer, findComponent } from "@/mock/components";
import { GAMES } from "@/mock/build";
import { checkCompatibility, estimateWattage, issueKey } from "@/lib/compat";
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
  const watts = estimateWattage(build);
  const issues = checkCompatibility(build);
  const errors = issues.filter((i) => i.level === "error");
  const errorParts = new Set(errors.flatMap((e) => e.parts));
  const gpuTooLong = errors.some((e) => e.code === "gpuLength");

  const fps = build.gpu
    ? FPS_BASELINE[game].map((row) => ({
        ...row,
        min: Math.round(row.min * build.gpu.specs.perf_index),
        max: Math.round(row.max * build.gpu.specs.perf_index),
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
                        {part.brand} {part.model}
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
          <div className="summary-row">
            <span className="muted">{t.builder.total}</span>
            <span className="stat-value">{formatEuros(totalCents)}</span>
          </div>
          <div className="summary-row">
            <span className="muted">{t.builder.powerDraw}</span>
            <span>{watts ? `~${watts} W` : "–"}</span>
          </div>
          <div className="summary-row">
            <span className="muted">{t.builder.partsChosen}</span>
            <span>
              {chosen.length} / {SLOTS.length}
            </span>
          </div>
        </div>

        <div className="card">
          <h2>{t.builder.compatibility}</h2>
          {chosen.length === 0 ? (
            <p className="muted small">{t.builder.addPartsToCheck}</p>
          ) : issues.length === 0 ? (
            <p className="issue ok">{t.builder.noProblems}</p>
          ) : (
            <ul className="issues">
              {issues.map((issue) => (
                <li key={issueKey(issue)} className={`issue ${issue.level}`}>
                  {issue.level === "error" ? "✕" : "!"} {t.issues[issue.code](issue.params)}
                </li>
              ))}
            </ul>
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
            <p className="muted small">{t.builder.chooseGpuForFps}</p>
          )}
        </div>

      </aside>

      {openSlot && (
        <PartPicker slot={openSlot} build={build} onSelect={selectPart} onClose={() => setOpenSlot(null)} />
      )}
    </div>
  );
}
