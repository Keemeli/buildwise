// Compatibility rules for a build.
// `build` is an object like { cpu: component, motherboard: component, ... } (missing slots are null).
//
// Returns a list of issues: { level, parts: [categories], code, params }.
//   level "error"   — the parts do not work together
//   level "warning" — works, but something needs attention
//   level "unknown" — the check could not run because a spec is missing from the data.
//                     Never report "ok" for a check we could not do.
// `code` is a key in strings.ts → issues, which turns it into text in the right language.
// The real version will live in the Express engine; keep the rules in sync with it.

const BASE_POWER_W = 75; // motherboard, RAM, SSD, fans

// One part's power draw. A CPU data sheet gives a TDP, a GPU sheet gives a maximum
// power draw (`power_w`). Both are the same kind of number, so either is accepted.
const partPowerW = (part) => part.specs.tdp_w ?? part.specs.power_w ?? null;

// The manufacturer's minimum PSU size for the system, when the GPU data sheet has
// one. It describes the whole system, not the card, so it is never reported as a
// part's power draw — it is only used to check the PSU.
export const minimumPsuW = (build) => build.gpu?.specs.recommended_psu_w ?? null;

// What a power number is based on, so the panel can say it out loud:
//   "parts"           — summed from the chosen parts' own power figures (TDP / power_w)
//   "manufacturerMin" — the GPU manufacturer's minimum PSU size for the system
//   "none"            — no CPU or GPU chosen yet
//   "unknown"         — neither a power figure nor a manufacturer minimum is in the data
export function powerBasis(build) {
  const parts = [build.cpu, build.gpu].filter(Boolean);
  if (parts.length === 0) return { watts: null, basis: "none" };
  const powers = parts.map(partPowerW);
  if (powers.every((w) => w != null)) {
    return { watts: powers.reduce((sum, w) => sum + w, BASE_POWER_W), basis: "parts" };
  }
  const minimum = minimumPsuW(build);
  if (minimum != null) return { watts: minimum, basis: "manufacturerMin" };
  return { watts: null, basis: "unknown" };
}

// null = cannot estimate (neither a power figure nor a manufacturer minimum)
export function estimateWattage(build) {
  return powerBasis(build).watts;
}

const known = (v) => v !== null && v !== undefined;

// "DDR4", "DDR4-SDRAM", "ddr5 sdram", ["DDR4-SDRAM", "DDR5-SDRAM"] -> ["DDR4"] / ["DDR5"] / ["DDR4","DDR5"].
// Data sheets and product names describe the same memory generation in different
// words, so comparing the raw strings reports a mismatch between compatible parts.
const ddrGenerations = (value) => {
  const parts = Array.isArray(value) ? value : [value];
  const found = [];
  for (const part of parts) {
    for (const match of String(part ?? "").match(/G?DDR\d/gi) || []) {
      const token = match.toUpperCase();
      if (!found.includes(token)) found.push(token);
    }
  }
  return found;
};

export function checkCompatibility(build) {
  const { cpu, cooler, motherboard, memory, gpu, psu } = build;
  const pcCase = build.case;
  const issues = [];
  const add = (level, parts, code, params = {}) => issues.push({ level, parts, code, params });

  // CPU ↔ motherboard
  if (cpu && motherboard) {
    const a = cpu.specs.socket;
    const b = motherboard.specs.socket;
    if (known(a) && known(b)) {
      if (a !== b) add("error", ["cpu", "motherboard"], "socketMismatch", { cpuSocket: a, boardSocket: b });
    } else {
      add("unknown", ["cpu", "motherboard"], "socketUnknown");
    }
  }

  // Memory ↔ motherboard
  if (memory && memory.specs.form_factor === "SO-DIMM") {
    add("error", ["memory"], "laptopMemory");
  }
  if (memory && motherboard) {
    const memoryTypes = ddrGenerations(memory.specs.memory_type);
    const boardTypes = ddrGenerations(motherboard.specs.memory_type);
    if (memoryTypes.length > 0 && boardTypes.length > 0) {
      // Compare generations, not shop wording: one shop writes "DDR4", the next
      // "DDR4-SDRAM", and a board can legitimately support two generations.
      if (!memoryTypes.some((type) => boardTypes.includes(type))) {
        add("error", ["memory", "motherboard"], "memoryMismatch", {
          memoryType: memory.specs.memory_type,
          boardType: motherboard.specs.memory_type,
        });
      }
    } else {
      add("unknown", ["memory", "motherboard"], "memoryUnknown");
    }
  }

  // Cooler ↔ CPU
  if (cooler && cpu) {
    const sockets = cooler.specs.sockets;
    if (known(sockets) && known(cpu.specs.socket)) {
      if (!sockets.includes(cpu.specs.socket)) add("error", ["cooler", "cpu"], "coolerSocket", { socket: cpu.specs.socket });
    } else {
      add("unknown", ["cooler", "cpu"], "coolerSocketUnknown");
    }
  }

  // Motherboard ↔ case
  if (motherboard && pcCase) {
    const supported = pcCase.specs.form_factors;
    if (known(supported) && known(motherboard.specs.form_factor)) {
      if (!supported.includes(motherboard.specs.form_factor)) {
        add("error", ["motherboard", "case"], "formFactor", { formFactor: motherboard.specs.form_factor });
      }
    } else {
      add("unknown", ["motherboard", "case"], "formFactorUnknown");
    }
  }

  // GPU ↔ case
  if (gpu && pcCase) {
    const length = gpu.specs.length_mm;
    const max = pcCase.specs.max_gpu_length_mm;
    if (known(length) && known(max)) {
      if (length > max) add("error", ["gpu", "case"], "gpuLength", { length, max });
    } else {
      add("unknown", ["gpu", "case"], "gpuLengthUnknown");
    }
  }

  // Cooler ↔ case
  if (cooler && pcCase) {
    const height = cooler.specs.height_mm;
    const max = pcCase.specs.max_cooler_height_mm;
    if (known(height) && known(max)) {
      if (height > max) add("error", ["cooler", "case"], "coolerHeight", { height, max });
    } else {
      add("unknown", ["cooler", "case"], "coolerHeightUnknown");
    }
  }

  // Power supply
  if (psu && (cpu || gpu)) {
    const { basis } = powerBasis(build);
    const psuWatts = psu.specs.wattage_w;
    const minimum = minimumPsuW(build);
    if (known(psuWatts) && basis === "parts") {
      const watts = estimateWattage(build);
      if (psuWatts < watts) {
        add("error", ["psu"], "psuTooWeak", { psu: psuWatts, draw: watts });
      } else if (psuWatts < watts * 1.3) {
        add("warning", ["psu"], "psuLowHeadroom", {
          psu: psuWatts,
          draw: watts,
          recommended: Math.ceil((watts * 1.3) / 50) * 50,
        });
      }
    } else if (known(psuWatts) && known(minimum)) {
      // Only the manufacturer's minimum is known, so check it directly. No headroom
      // warning on this path: that figure already includes the manufacturer's own
      // allowance, and demanding 30% on top of it would push people to oversized units.
      if (psuWatts < minimum) {
        add("error", ["psu"], "psuBelowMinimum", { psu: psuWatts, minimum });
      }
    } else {
      add("unknown", ["psu"], "powerUnknown");
    }
  }

  // Only warn when the data says so explicitly: null means "not known", not "no".
  if (cpu && !cooler && cpu.specs.cooler_included === false) {
    add("warning", ["cooler", "cpu"], "needsCooler");
  }
  if (cpu && !gpu && (cpu.specs.igpu ?? cpu.specs.integrated_graphics) === false) {
    add("warning", ["gpu", "cpu"], "needsGpu");
  }

  return issues;
}

// Errors that a candidate part would cause, given the rest of the build.
export function issuesForCandidate(build, candidate) {
  const next = { ...build, [candidate.category]: candidate };
  return checkCompatibility(next).filter(
    (issue) => issue.level === "error" && issue.parts.includes(candidate.category),
  );
}

// Key for React lists
export function issueKey(issue) {
  return `${issue.code}:${issue.parts.join(",")}`;
}

// Which checks the engine can actually run with the parts chosen so far.
// The panel uses this so a build with only a CPU and a GPU does not show a bare
// green tick: it says how many checks ran and what is still waiting for parts.
const CHECK_AREAS = [
  { id: "cpuSocket", needs: ["cpu", "motherboard"] },
  { id: "memoryType", needs: ["memory", "motherboard"] },
  { id: "memoryForm", needs: ["memory"] },
  { id: "coolerMount", needs: ["cooler", "motherboard"] },
  { id: "coolerHeight", needs: ["cooler", "case"] },
  { id: "gpuLength", needs: ["gpu", "case"] },
  { id: "psuPower", needs: ["psu"], anyOf: ["cpu", "gpu"] },
  { id: "cpuExtras", needs: ["cpu"] },
];

export function checkCoverage(build) {
  const areas = CHECK_AREAS.map((area) => ({
    ...area,
    ready: area.needs.every((k) => build[k]) && (!area.anyOf || area.anyOf.some((k) => build[k])),
  }));
  const waitingFor = [...new Set(
    areas.filter((a) => !a.ready).flatMap((a) => a.needs).filter((k) => !build[k]),
  )];
  return {
    done: areas.filter((a) => a.ready).length,
    total: areas.length,
    waitingFor,
    notDone: areas.length - areas.filter((a) => a.ready).length,
  };
}
