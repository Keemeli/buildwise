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

// null = cannot estimate (a chosen CPU or GPU has neither a power figure nor a
// manufacturer minimum PSU size in the data)
export function estimateWattage(build) {
  const parts = [build.cpu, build.gpu].filter(Boolean);
  if (parts.length === 0) return 0;
  const powers = parts.map(partPowerW);
  if (powers.some((w) => w == null)) return null;
  return powers.reduce((sum, w) => sum + w, BASE_POWER_W);
}

const known = (v) => v !== null && v !== undefined;

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
    const a = memory.specs.memory_type;
    const b = motherboard.specs.memory_type;
    if (known(a) && known(b)) {
      if (a !== b) add("error", ["memory", "motherboard"], "memoryMismatch", { memoryType: a, boardType: b });
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
    const watts = estimateWattage(build);
    const psuWatts = psu.specs.wattage_w;
    const minimum = minimumPsuW(build);
    if (known(psuWatts) && known(watts)) {
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
