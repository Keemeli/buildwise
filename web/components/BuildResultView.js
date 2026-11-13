"use client";

import Link from "next/link";
import { formatEuros } from "@/lib/api";
import { useT } from "@/lib/locale";
import PartsTable from "@/components/PartsTable";
import FpsChart from "@/components/FpsChart";

// Texts of the budget-search result page. The data is fetched on the server
// (app/suggestion/page.js); this part only renders it in the chosen language.

export function BackLink() {
  const t = useT();
  return (
    <Link href="/" className="back">
      {t.result.changeSearch}
    </Link>
  );
}

export function LoadingCard() {
  const t = useT();
  return <div className="card loading">{t.result.loading}</div>;
}

export default function BuildResultView({ build, gameName, exclude }) {
  const t = useT();
  const leftover = build.budgetCents - build.totalCents;

  return (
    <>
      <h1>
        {gameName} · {formatEuros(build.budgetCents, t.locale)}
      </h1>
      {exclude.length > 0 && (
        <p className="muted">{t.result.ownedParts(exclude.map((c) => t.categories[c]))}</p>
      )}

      <div className="summary">
        <div className="card stat">
          <span className="stat-label">{t.result.totalPrice}</span>
          <span className="stat-value">{formatEuros(build.totalCents, t.locale)}</span>
        </div>
        <div className="card stat">
          <span className="stat-label">{t.result.leftInBudget}</span>
          <span className="stat-value">{formatEuros(leftover, t.locale)}</span>
        </div>
        <div className="card stat">
          <span className="stat-label">{t.result.fps1080}</span>
          <span className="stat-value">
            {build.fps[0].min}–{build.fps[0].max}
          </span>
        </div>
      </div>

      <section className="card">
        <h2>{t.result.components}</h2>
        <PartsTable parts={build.parts} />
      </section>

      <section className="card">
        <h2>{t.result.fpsEstimate}</h2>
        <FpsChart fps={build.fps} />
        <ul className="notes">
          {build.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
