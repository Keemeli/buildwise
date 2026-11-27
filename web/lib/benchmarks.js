// Reading the ingested benchmark table (web/data/benchmarks.json) for the builder.
//
// The table is written by `scraper/benchmarks/checkfps.py` from CheckFPS's public pages.
// CheckFPS states its figures are estimates from its own engine, not lab measurements, so
// every row carries `measured: false`, its source URL and the date it was read — the builder
// shows that line and never calls the result a measurement.
//
// Pure functions on purpose: no imports, so the contract check can load this file through a
// data: URL (see web/scripts/check-data-contract.mjs).

export const PRESETS = ["low", "medium", "high", "ultra"];
export const RESOLUTIONS = ["1080p", "1440p", "4K"];

/** The key our catalogue uses (see lib/catalog-shared.js chipsetKey). */
export function chipsetKey(chipset) {
  return chipset ? String(chipset).toUpperCase().replace(/\s+/g, "") : null;
}

/**
 * The card's relative index at each resolution, or null when we have no data for it.
 *
 * CheckFPS lists some cards per memory size ("RX 9060 XT 16GB"), so the exact key wins, then
 * the key with the card's own VRAM, then a prefix match — but only when it is unambiguous:
 * guessing between an 8 GB and a 16 GB variant would put the wrong number on a part.
 */
export function gpuIndexFor(part, benchmarks) {
  const index = benchmarks?.gpuIndex?.index || {};
  const keys = [
    chipsetKey(part?.specs?.chipset),
    chipsetKey(part?.specs?.graphics_chipset),
  ].filter(Boolean);
  if (!keys.length) return null;

  const vram = part?.specs?.vram_gb;
  const candidates = [];
  for (const key of keys) {
    if (vram && index[`${key}${vram}GB`]) candidates.push(index[`${key}${vram}GB`]);
    if (index[key]) candidates.push(index[key]);
  }
  if (candidates.length) return candidates[0];

  const prefixed = [...keys].flatMap((key) => Object.entries(index)
    .filter(([name]) => name.startsWith(key))
    .map(([, value]) => value));
  return prefixed.length === 1 ? prefixed[0] : null;
}

/** The rows the performance model eats, one game's worth, with the game's RAM need attached. */
export function tableForGame(benchmarks, game) {
  const entry = benchmarks?.games?.[game];
  if (!entry) return {};
  return {
    [game]: entry.rows.map((row) => ({ ...row, ramNeedGb: entry.ramNeedGb })),
  };
}

/** Which presets and resolutions we actually have for a game, so the UI offers no dead ends. */
export function optionsFor(benchmarks, game) {
  const rows = benchmarks?.games?.[game]?.rows || [];
  return {
    resolutions: RESOLUTIONS.filter((r) => rows.some((row) => row.resolution === r)),
    presets: PRESETS.filter((p) => rows.some((row) => row.preset === p)),
  };
}

/** The provenance the UI prints under an estimate. */
export function benchmarkSource(benchmarks) {
  const source = benchmarks?.source || {};
  return {
    name: source.name || "unknown",
    retrieved: source.retrieved || null,
    note: source.note || "",
    gpuReference: benchmarks?.reference?.gpu || null,
    cpuReference: benchmarks?.reference?.cpu || null,
  };
}
