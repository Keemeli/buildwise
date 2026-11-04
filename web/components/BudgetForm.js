"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GAMES } from "@/mock/build";
import { t } from "@/strings";

const MIN = 500;
const MAX = 4000;

export default function BudgetForm() {
  const router = useRouter();
  const [budget, setBudget] = useState(1200);
  const [game, setGame] = useState(GAMES[0].id);

  function handleSubmit(event) {
    event.preventDefault();
    const params = new URLSearchParams({ budget: String(budget), game });
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

      <button type="submit" className="button">
        {t.budget.submit}
      </button>
    </form>
  );
}
