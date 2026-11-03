// Compatibility rules for a build.
// `build` is an object like { cpu: component, motherboard: component, ... } (missing slots are null).
// Returns a list of issues: { level: "error" | "warning", parts: [categories], code, params }.
// `code` is a key in strings.ts → issues, which turns it into text in the right language.
// The real version will live in the Express engine; keep the rules in sync with it.

const BASE_POWER_W = 75; // motherboard, RAM, SSD, fans

export function estimateWattage(build) {
  const cpu = build.cpu?.specs.tdp_w ?? 0;
  const gpu = build.gpu?.specs.tdp_w ?? 0;
  if (!cpu && !gpu) return 0;
  return cpu + gpu + BASE_POWER_W;
}

export function checkCompatibility(build) {
  const { cpu, cooler, motherboard, memory, gpu, psu } = build;
  const pcCase = build.case;
  const issues = [];
  const error = (parts, code, params = {}) => issues.push({ level: "error", parts, code, params });
  const warning = (parts, code, params = {}) => issues.push({ level: "warning", parts, code, params });

  if (cpu && motherboard && cpu.specs.socket !== motherboard.specs.socket) {
    error(["cpu", "motherboard"], "socketMismatch", { cpuSocket: cpu.specs.socket, boardSocket: motherboard.specs.socket });
  }
  if (memory && motherboard && memory.specs.memory_type !== motherboard.specs.memory_type) {
    error(["memory", "motherboard"], "memoryMismatch", { memoryType: memory.specs.memory_type, boardType: motherboard.specs.memory_type });
  }
  if (cooler && cpu && !cooler.specs.sockets.includes(cpu.specs.socket)) {
    error(["cooler", "cpu"], "coolerSocket", { socket: cpu.specs.socket });
  }
  if (motherboard && pcCase && !pcCase.specs.form_factors.includes(motherboard.specs.form_factor)) {
    error(["motherboard", "case"], "formFactor", { formFactor: motherboard.specs.form_factor });
  }
  if (gpu && pcCase && gpu.specs.length_mm > pcCase.specs.max_gpu_length_mm) {
    error(["gpu", "case"], "gpuLength", { length: gpu.specs.length_mm, max: pcCase.specs.max_gpu_length_mm });
  }
  if (cooler && pcCase && cooler.specs.height_mm > pcCase.specs.max_cooler_height_mm) {
    error(["cooler", "case"], "coolerHeight", { height: cooler.specs.height_mm, max: pcCase.specs.max_cooler_height_mm });
  }

  const watts = estimateWattage(build);
  if (psu && watts) {
    if (psu.specs.wattage_w < watts) {
      error(["psu"], "psuTooWeak", { psu: psu.specs.wattage_w, draw: watts });
    } else if (psu.specs.wattage_w < watts * 1.3) {
      warning(["psu"], "psuLowHeadroom", {
        psu: psu.specs.wattage_w,
        draw: watts,
        recommended: Math.ceil((watts * 1.3) / 50) * 50,
      });
    }
  }

  if (cpu && !cooler && !cpu.specs.cooler_included) {
    warning(["cooler", "cpu"], "needsCooler");
  }
  if (cpu && !gpu && !cpu.specs.igpu) {
    warning(["gpu", "cpu"], "needsGpu");
  }

  return issues;
}

// Issues that a candidate part would cause, given the rest of the build.
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
