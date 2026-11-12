"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GAMES } from "@/mock/build";
import { t } from "@/strings";

const MIN = 500;
const MAX = 4000;

// `owned`: categories the user already has. They are left out of the budget, so the
// whole budget goes to the other parts.
export default function BudgetForm({ owned = [] }) {
  const router = useRouter();
  const [budget, setBudget] = useState(1200);
  const [game, setGame] = useState(GAMES[0].id);

  function handleSubmit(event) {
    event.preventDefault();
    const params = new URLSearchParams({ budget: String(budget), game });
    if (owned.length > 0) params.set("exclude", owned.join(","));
    router.push(`/build?${params}`);
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label>
        {t.budget.budget}
        <div className="budget-row">
          <input
            type="range"
            min={MIN}
            max={MAX}
            step="50"
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            style={{ "--fill": `${((budget - MIN) / (MAX - MIN)) * 100}%` }}
          />
          <input
            type="number"
            min="300"
            max="10000"
            step="50"
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="budget-number"
          />
          <span>€</span>
        </div>
      </label>

      <label>
        {t.budget.game}
        <select value={game} onChange={(e) => setGame(e.target.value)}>
          {GAMES.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      </label>

      {owned.length > 0 && (
        <p className="muted small">{t.builder.budgetOwnedNote(owned.map((c) => t.categories[c]))}</p>
      )}

      <button type="submit" className="button">
        {t.budget.submit}
      </button>
    </form>
  );
}
