import { mockBuild } from "@/mock/build";
import { t } from "@/strings";

// When the Express API is ready, set this in .env.local, e.g.
//   API_URL=http://localhost:4000
// Until then, mock data is returned.
const API_URL = process.env.API_URL;

// exclude: categories the user already owns. The budget goes to the other parts only.
export async function getBuild({ budget, game, exclude = [] }) {
  if (!API_URL) {
    // Mock data, using the budget and game the user entered. Owned parts are left out,
    // so the page shows what a build without them looks like; the real engine will
    // spend the freed budget on the remaining parts.
    const parts = mockBuild.parts.filter((p) => !exclude.includes(p.category));
    const totalCents = parts.reduce((sum, p) => sum + p.priceCents, 0);
    return { ...mockBuild, parts, totalCents, budgetCents: budget * 100, game, exclude };
  }

  const params = new URLSearchParams({ budget: String(budget), game });
  if (exclude.length > 0) params.set("exclude", exclude.join(","));
  const res = await fetch(`${API_URL}/api/build?${params}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export function formatEuros(cents) {
  return (cents / 100).toLocaleString(t.locale, { style: "currency", currency: "EUR" });
}
