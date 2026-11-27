// The performance model: what the chosen CPU and GPU can be expected to do in a game at a
// resolution and a quality preset — as an **average frame rate and a 1% low**.
//
// Four rules, all of them about not overclaiming:
//
//  1. **Every number carries its source.** `measured` is true only when the figure comes
//     from a published measurement of that hardware; a figure derived from a relative index
//     is `measured: false` and says which index it used.
//  2. **A 1% low is never invented.** It is the *ratio* of the low to the average observed
//     for that game and resolution, applied to the average this model derived. If the
//     source has no low, the result says so (`low1: null`, `lowReason`) instead of
//     reporting the average as if it were the floor. (A rendering range's lower bound is
//     not a 1% low and is never used as one.)
//  3. **The CPU can cap the frame rate.** Below the CPU's ceiling for a game — usually at
//     1080p and low presets, where the GPU waits for the CPU — the estimate is the ceiling,
//     and `cpuBound: true` says the faster GPU will not help.
//  4. **RAM above the game's need does not raise FPS.** More than the stated need is
//     reported as sufficient, not as a bonus; below it, the estimate is flagged instead of
//     silently kept.
//
// The dataset is handed in, so the model is testable on synthetic numbers and the real
// benchmark data becomes a drop-in. Dependency-free on purpose: the contract check loads
// this file through a data: URL.

export const DEFAULT_RAM_GB = 32;
export const PRESETS = ["low", "medium", "high", "ultra"];

const num = (value) => (typeof value === "number" && Number.isFinite(value) ? value : null);

/** Preset ordering for "at least this preset" lookups; unknown presets are ignored. */
function presetRank(preset) {
  const index = PRESETS.indexOf(String(preset ?? "").toLowerCase());
  return index === -1 ? null : index;
}

/**
 * The row for one game at a resolution and a preset. A row belongs to exactly one of each:
 * a measurement at 1440p Ultra is not an estimate at 1080p Low, so nothing is inferred
 * across rows — an unknown combination is reported as unknown.
 */
function findRow(table, game, resolution, preset) {
  const rows = table?.[game];
  if (!Array.isArray(rows)) return null;
  const wanted = presetRank(preset);
  return rows.find((row) => row.resolution === resolution
    && (wanted === null || presetRank(row.preset) === wanted)) ?? null;
}

/**
 * @param {object} input
 * @param {object} input.table       benchmark table: { [game]: [{resolution, preset, avg, low, lowRatio, cpuCeiling, ramNeedGb, measured, source, retrieved}] }
 * @param {string} input.game
 * @param {string} input.resolution  "1080p" | "1440p" | "4K"
 * @param {string} input.preset      low | medium | high | ultra
 * @param {number} [input.ramGb]     RAM in the build; defaults to 32
 * @param {number|null} [input.gpuIndex]  relative GPU index, 1.0 = the row's reference card
 * @param {number|null} [input.cpuIndex]  relative CPU index, 1.0 = the row's reference CPU
 * @returns {object} { avg, low1, measured, source, retrieved, cpuBound, ramBelowNeed, reasons }
 */
export function estimateFps({ table, game, resolution, preset, ramGb = DEFAULT_RAM_GB, gpuIndex = null, cpuIndex = null }) {
  const reasons = [];
  const row = findRow(table, game, resolution, preset);
  if (!row) {
    return { avg: null, low1: null, measured: false, cpuBound: null, ramBelowNeed: null,
             source: null, retrieved: null, reasons: ["no benchmark row for this game, resolution and preset"] };
  }

  const baseAvg = num(row.avg);
  if (baseAvg === null) {
    return { avg: null, low1: null, measured: false, cpuBound: null, ramBelowNeed: null,
             source: row.source ?? null, retrieved: row.retrieved ?? null,
             reasons: ["the row has no usable average frame rate"] };
  }

  // A row already belongs to one resolution and preset, so nothing is scaled twice: the
  // only scaling left is the card's relative index (1.0 = the row's reference card).
  const gpuFactor = num(gpuIndex) ?? 1;
  let avg = baseAvg * gpuFactor;
  if (gpuIndex === null) reasons.push("no GPU index: shown for the row's reference card");

  // The CPU caps the frame rate in the CPU-bound range: the estimate is the lower of what
  // the GPU could draw and what the CPU can feed it (a ceiling, not a resolution effect).
  const ceiling = num(row.cpuCeiling);
  const cpuFactor = num(cpuIndex);
  let cpuBound = null;
  if (ceiling !== null && cpuFactor !== null) {
    const cpuLimit = ceiling * cpuFactor;
    if (cpuLimit < avg) {
      avg = cpuLimit;
      cpuBound = true;
    } else {
      cpuBound = false;
    }
  } else if (ceiling !== null) {
    reasons.push("no CPU index: the CPU ceiling was not applied");
  }

  // A 1% low is a ratio against the average, never an absolute number conjured here.
  const lowRatio = num(row.lowRatio) ?? (num(row.low) !== null && baseAvg ? row.low / baseAvg : null);
  const low1 = lowRatio === null ? null : Math.round(avg * lowRatio);
  if (low1 === null) reasons.push("the benchmark source has no 1% low for this game and resolution");

  const ramNeedGb = num(row.ramNeedGb);
  const ramBelowNeed = ramNeedGb === null ? null : ramGb < ramNeedGb;
  if (ramBelowNeed) reasons.push(`the game states ${ramNeedGb} GB of memory; the build has ${ramGb} GB`);

  return {
    avg: Math.round(avg),
    low1,
    measured: Boolean(row.measured),
    cpuBound,
    ramBelowNeed,
    source: row.source ?? null,
    retrieved: row.retrieved ?? null,
    reasons,
  };
}

/** Every preset a table row exists for — what the quality slider should offer for a game. */
export function presetsFor(table, game) {
  const rows = table?.[game];
  if (!Array.isArray(rows)) return [];
  const found = [...new Set(rows.map((row) => presetRank(row.preset)).filter((rank) => rank !== null))];
  return found.sort((a, b) => a - b).map((rank) => PRESETS[rank]);
}
