"use client";

import { useT } from "@/lib/locale";
import { formatEuros } from "@/lib/api";
import { GAMES } from "@/mock/build";
import PartIcon from "@/components/PartIcon";

// Front-page illustration: a small version of what a budget search returns.
// Uses the same example build as the mock budget search, and says it is an example.
// The parts people look at first in a gaming PC; the rest are summed up.
const SHOWN = ["cpu", "gpu", "memory"];

export default function ExampleBuildCard({ build }) {
  const t = useT();
  const gameName = GAMES.find((g) => g.id === build.game)?.name ?? build.game;
  const fps = build.fps[0];
  const shown = SHOWN.map((c) => build.parts.find((p) => p.category === c)).filter(Boolean);
  const rest = build.parts.filter((p) => !SHOWN.includes(p.category));
  const restCents = rest.reduce((sum, p) => sum + p.priceCents, 0);

  // FPS scale: 0 → a round number above the estimate, so the range sits inside the bar.
  const scaleMax = Math.ceil((fps.max * 1.4) / 100) * 100;
  const left = (fps.min / scaleMax) * 100;
  const width = ((fps.max - fps.min) / scaleMax) * 100;

  return (
    <div className="card example-card">
      <div className="example-head">
        <strong>{gameName}</strong>
        <span className="example-tag">{t.landing.example}</span>
      </div>

      <ul className="example-parts">
        {shown.map((part) => (
          <li key={part.category}>
            <span className="example-part">
              <PartIcon category={part.category} size={20} />
              {part.name}
            </span>
            <span>{formatEuros(part.priceCents, t.locale)}</span>
          </li>
        ))}
        {rest.length > 0 && (
          <li className="muted">
            <span>{t.landing.moreParts(rest.length)}</span>
            <span>{formatEuros(restCents, t.locale)}</span>
          </li>
        )}
      </ul>

      <div className="example-total">
        <span>{t.builder.total}</span>
        <span>{formatEuros(build.totalCents, t.locale)}</span>
      </div>

      <p className="muted small example-fps-label">
        FPS {fps.resolution} · {t.fps.settings[fps.settings] ?? fps.settings}
      </p>
      <div className="fps-range" role="img" aria-label={`FPS ${fps.min}–${fps.max}`}>
        <div className="fps-range-bar">
          <div className="fps-range-fill" style={{ left: `${left}%`, width: `${width}%` }} />
        </div>
        {/* The estimate sits right under the range it describes; the scale ends at the edges. */}
        <div className="fps-range-axis">
          <span>0</span>
          <span className="fps-range-value" style={{ left: `${left + width / 2}%` }}>
            {fps.min}–{fps.max}
          </span>
          <span>{scaleMax}</span>
        </div>
      </div>

      <p className="example-ok">✓ {t.landing.allFit}</p>
    </div>
  );
}
