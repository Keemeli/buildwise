// The parts of one category as JSON, e.g. /catalog/gpu. Prerendered at build time for
// every slot category, so the builder downloads only the category whose picker is open.

import { SLOTS, componentsIn } from "@/lib/catalog";

export function generateStaticParams() {
  return SLOTS.map((s) => ({ category: s.category }));
}

async function partsIn(category) {
  "use cache";
  const name = await category;
  return SLOTS.some((s) => s.category === name) ? componentsIn(name) : null;
}

export async function GET(request, { params }) {
  const parts = await partsIn(params.then((p) => p.category));
  if (!parts) return Response.json({ error: "unknown category" }, { status: 404 });
  return Response.json(parts);
}
