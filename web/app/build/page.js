import { Suspense } from "react";
import Link from "next/link";
import { getBuild, formatEuros } from "@/lib/api";
import { GAMES } from "@/mock/build";
import PartsTable from "@/components/PartsTable";
import FpsChart from "@/components/FpsChart";
import { t } from "@/strings";

export default function BuildPage({ searchParams }) {
  return (
    <>
      <Link href="/" className="back">
        {t.result.changeSearch}
      </Link>
      <Suspense fallback={<div className="card loading">{t.result.loading}</div>}>
        <BuildResult searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function BuildResult({ searchParams }) {
  const params = await searchParams;
  const budget = Number(params.budget) || 1000;
  const game = params.game || "cs2";
  const exclude = (params.exclude || "").split(",").filter((c) => c in t.categories);
  const gameName = GAMES.find((g) => g.id === game)?.name ?? game;

  const build = await getBuild({ budget, game, exclude });
  const leftover = build.budgetCents - build.totalCents;

  return (
    <>
      <h1>
        {gameName} · {formatEuros(build.budgetCents)}
      </h1>
      {exclude.length > 0 && (
        <p className="muted">{t.result.ownedParts(exclude.map((c) => t.categories[c]))}</p>
      )}

      <div className="summary">
        <div className="card stat">
          <span className="stat-label">{t.result.totalPrice}</span>
          <span className="stat-value">{formatEuros(build.totalCents)}</span>
        </div>
        <div className="card stat">
          <span className="stat-label">{t.result.leftInBudget}</span>
          <span className="stat-value">{formatEuros(leftover)}</span>
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
