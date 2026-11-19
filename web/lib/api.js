import { mockBuild } from "@/mock/build";
import { t } from "@/strings";

// When the Express API is ready, set this in .env.local, e.g.
//   API_URL=http://localhost:4000
// Until then, mock data is returned.
const API_URL = process.env.API_URL;

// Target resolutions of the budget search. `id` is the value in the URL and the API, and
// matches the `resolution` of a build's FPS rows; `label` is shown (language-neutral).
export const RESOLUTIONS = [
  { id: "1080p", label: "1080p" },
  { id: "1440p", label: "2K (1440p)" },
  { id: "4K", label: "4K" },
];
export const DEFAULT_RESOLUTION = "1080p";

export function resolutionLabel(id) {
  return RESOLUTIONS.find((r) => r.id === id)?.label ?? id;
}

// exclude: categories the user already owns. The budget goes to the other parts only.
// resolution: the user's target resolution; the engine sizes the GPU for it.
export async function getBuild({ budget, game, resolution = DEFAULT_RESOLUTION, exclude = [] }) {
  if (!API_URL) {
    // Mock data, using the budget and game the user entered. Owned parts are left out,
    // so the page shows what a build without them looks like; the real engine will
    // spend the freed budget on the remaining parts. The mock parts do not change
    // with the resolution; only the FPS row shown does.
    const parts = mockBuild.parts.filter((p) => !exclude.includes(p.category));
    const totalCents = parts.reduce((sum, p) => sum + p.priceCents, 0);
    return { ...mockBuild, parts, totalCents, budgetCents: budget * 100, game, resolution, exclude };
  }

  const params = new URLSearchParams({ budget: String(budget), game, resolution });
  if (exclude.length > 0) params.set("exclude", exclude.join(","));
  const res = await fetch(`${API_URL}/api/build?${params}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

// `locale` decides the number format (1 234,50 € vs €1,234.50); pass `t.locale` from useT().
export function formatEuros(cents, locale = t.locale) {
  return (cents / 100).toLocaleString(locale, { style: "currency", currency: "EUR" });
}
