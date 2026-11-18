"use client";

import Link from "next/link";
import { useT } from "@/lib/locale";
import BudgetForm from "@/components/BudgetForm";
import ExampleBuildCard from "@/components/ExampleBuildCard";
import { EXAMPLE_BUILDS } from "@/mock/build";

// Front page. `partCount`, `shops` and `updatedIso` come from the catalogue on the server,
// so the numbers shown are always the real ones.
export default function Landing({ partCount, shops, updatedIso }) {
  const t = useT();
  const updated = new Date(updatedIso).toLocaleDateString(t.locale, { timeZone: "UTC" });

  return (
    <div className="landing">
      <section className="landing-hero">
        <div>
          <h1>{t.landing.title}</h1>
          <p className="lead">{t.landing.lead}</p>

          {/* One main action; the builder is the secondary route, so it is a link, not a second card. */}
          <div className="card start-card start-primary">
            <h2>{t.landing.budgetTitle}</h2>
            <BudgetForm />
          </div>

          <div className="landing-alt">
            <span>{t.landing.builderPrompt}</span>
            <Link href="/builder" className="button button-secondary">
              {t.landing.openBuilder}
            </Link>
          </div>
          <p className="muted small landing-upgrade">{t.landing.upgradeNote}</p>
        </div>

        <div className="landing-art">
          {EXAMPLE_BUILDS.map((build) => (
            <ExampleBuildCard key={build.game} build={build} />
          ))}
        </div>
      </section>

      <section className="landing-features">
        <div className="feature">
          <h3>{t.landing.compatTitle}</h3>
          <p className="muted small">{t.landing.compatText}</p>
        </div>
        <div className="feature">
          <h3>{t.landing.fpsTitle}</h3>
          <p className="muted small">{t.landing.fpsText}</p>
        </div>
        <div className="feature">
          <h3>{t.landing.catalogTitle(partCount)}</h3>
          <p className="muted small">{t.landing.catalogText(shops, updated)}</p>
        </div>
      </section>
    </div>
  );
}
