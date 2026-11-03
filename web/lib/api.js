import { mockBuild } from "@/mock/build";
import { t } from "@/strings";

// When the Express API is ready, set this in .env.local, e.g.
//   API_URL=http://localhost:4000
// Until then, mock data is returned.
const API_URL = process.env.API_URL;

export async function getBuild({ budget, game }) {
  if (!API_URL) {
    // Mock data, using the budget and game the user entered.
    return { ...mockBuild, budgetCents: budget * 100, game };
  }

  const params = new URLSearchParams({ budget: String(budget), game });
  const res = await fetch(`${API_URL}/api/build?${params}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export function formatEuros(cents) {
  return (cents / 100).toLocaleString(t.locale, { style: "currency", currency: "EUR" });
}
