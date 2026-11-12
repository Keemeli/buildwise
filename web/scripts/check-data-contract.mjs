#!/usr/bin/env node
/**
 * Contract check for the seam between the data pipeline and this app.
 *
 * Two visible bugs came from this seam in one night:
 *   1. a DDR4 memory kit was reported as incompatible with a DDR4 motherboard — the
 *      pipeline wrote the shop's wording ("DDR4-SDRAM") while the engine compared it
 *      against a product name's "DDR4";
 *   2. every memory row showed "undefined×undefined GB" — the UI reads
 *      `modules.count` / `modules.size_gb` while the pipeline wrote a plain count.
 * Both were found by a person clicking in the builder, not by a check.
 *
 * `normalisation_report.md` prints the facet vocabulary, which catches *value* drift
 * during review. Nothing caught *shape* drift. This script runs the same cases on every
 * pull request. It is deliberately dependency-free (node only, no test runner, no
 * build) and it loads the real engine from `web/lib/compat.js` — not a copy of it.
 *
 * When a bug is found on this seam, add a case here so it cannot come back.
 *
 * Run: npm run check:contract
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const catalogue = JSON.parse(readFileSync(join(webRoot, "data", "components.json"), "utf8"));
const components = catalogue.components;

// `lib/compat.js` is an ES module in a `.js` file inside an app that does not set
// "type": "module", so node cannot import it directly. Importing the source through a
// data: URL keeps the app's module setup untouched.
const engineSource = readFileSync(join(webRoot, "lib", "compat.js"), "utf8");
const { checkCompatibility } = await import(
  `data:text/javascript;charset=utf-8,${encodeURIComponent(engineSource)}`
);
// The picker's spec filters (issue #25), loaded the same way.
const facetsSource = readFileSync(join(webRoot, "lib", "facets.js"), "utf8");
const { FACETS, UNKNOWN, optionKeys, applyFacets, facetOptions } = await import(
  `data:text/javascript;charset=utf-8,${encodeURIComponent(facetsSource)}`
);

// Coverage floors, set well below today's numbers on purpose: a parser regression that
// silently drops most values must fail, ordinary catalogue churn must not. Raise them as
// coverage grows; never lower one to make a red build green.
const FLOORS = {
  "cpu.tdp_w": 0.8,
  "gpu.recommended_psu_w": 0.8,
  "memory.capacity_gb": 0.9,
  "motherboard.memory_type": 0.9,
  "psu.wattage_w": 0.9,
};

const notes = [];
const failures = [];
const check = (name, fn) => {
  try {
    const detail = fn();
    notes.push(`  ok   ${name}${detail ? ` — ${detail}` : ""}`);
  } catch (error) {
    failures.push(`  FAIL ${name} — ${error.message}`);
  }
};
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const of = (category) => components.filter((c) => c.category === category);
const value = (component, field) => (component?.specs ?? {})[field];
const asList = (v) => (Array.isArray(v) ? v : [v]);
const filled = (v) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0);
const memoryIssues = (build) => checkCompatibility(build).filter((i) => i.code.startsWith("memory"));
const sample = (list, description) => {
  assert(list.length > 0, description);
  return list[0];
};

// ---------------------------------------------------------------------------
// 1. Vocabulary — the engine compares these values and the UI filters on them, so
//    one real thing must have exactly one spelling.
// ---------------------------------------------------------------------------
check("memory generations are canonical (no shop wording)", () => {
  const bad = [];
  for (const category of ["memory", "motherboard"]) {
    for (const component of of(category)) {
      for (const type of asList(value(component, "memory_type"))) {
        if (!filled(type)) continue;
        if (!/^G?DDR\d$/.test(String(type))) {
          bad.push(`${category}: "${type}" in ${component.raw_name.slice(0, 40)}`);
        }
      }
    }
  }
  assert(bad.length === 0, `uncanonical memory type: ${bad.slice(0, 3).join(" | ")}`);
  return `${of("memory").length} memory + ${of("motherboard").length} motherboard rows are DDRx`;
});

check("storage interface and form factor are canonical", () => {
  const bad = [];
  for (const component of of("storage")) {
    const iface = value(component, "interface");
    if (filled(iface) && /serial\s*ata/i.test(String(iface))) {
      bad.push(`interface "${iface}" (expected "SATA III")`);
    }
    const shape = value(component, "form_factor");
    if (filled(shape) && !/^(M\.2( \d{4})?|\d(\.\d)?"|3\.5")$/.test(String(shape))) {
      bad.push(`form_factor "${shape}"`);
    }
  }
  assert(bad.length === 0, `uncanonical storage value: ${bad.slice(0, 3).join(" | ")}`);
  return "SATA III / M.2 2280 / 2.5\" style values only";
});

// ---------------------------------------------------------------------------
// 2. Shape — what the UI renders must be what the pipeline writes.
// ---------------------------------------------------------------------------
check("memory modules carry the shape the UI renders", () => {
  const bad = [];
  for (const component of of("memory")) {
    const modules = value(component, "modules");
    const capacity = value(component, "capacity_gb");
    if (!filled(modules)) continue;
    const ok = typeof modules === "object" && Number.isInteger(modules.count) && modules.count > 0
      && typeof modules.size_gb === "number" && modules.size_gb > 0;
    if (!ok) {
      bad.push(`${component.raw_name.slice(0, 40)} → modules=${JSON.stringify(modules)}`);
      continue;
    }
    if (filled(capacity) && Math.round(modules.count * modules.size_gb) !== capacity) {
      bad.push(`${modules.count}×${modules.size_gb} GB ≠ ${capacity} GB`);
    }
    // The exact line PartPicker.specSummary() builds; it cannot be imported here
    // because it is a JSX client component.
    const line = `${capacity} GB (${modules.count}×${modules.size_gb} GB)`;
    if (line.includes("undefined")) bad.push(`${component.raw_name.slice(0, 30)} → ${line}`);
  }
  assert(bad.length === 0, `bad modules shape: ${bad.slice(0, 3).join(" | ")}`);
  return `${of("memory").length} memory rows render without undefined`;
});

check("power fields are numbers, never strings", () => {
  const bad = [];
  const numeric = [["cpu", "tdp_w"], ["gpu", "power_w"], ["gpu", "recommended_psu_w"], ["psu", "wattage_w"]];
  for (const [category, field] of numeric) {
    for (const component of of(category)) {
      const v = value(component, field);
      if (filled(v) && !Number.isInteger(v)) {
        bad.push(`${category}.${field} = ${JSON.stringify(v)} (${component.raw_name.slice(0, 30)})`);
      }
    }
  }
  assert(bad.length === 0, `non-numeric power value: ${bad.slice(0, 3).join(" | ")}`);
  return `${numeric.length} power fields are integers or null`;
});

check("coverage floors hold", () => {
  const thin = [];
  for (const [key, floor] of Object.entries(FLOORS)) {
    const [category, field] = key.split(".");
    const group = of(category);
    const share = group.length ? group.filter((c) => filled(value(c, field))).length / group.length : 0;
    if (share < floor) thin.push(`${key} ${(share * 100).toFixed(0)}% < ${(floor * 100).toFixed(0)}%`);
  }
  assert(thin.length === 0, `coverage below floor: ${thin.join(", ")}`);
  return `${Object.keys(FLOORS).length} floors hold`;
});

check("catalogue rows are complete enough to build with", () => {
  assert(components.length > 200, `only ${components.length} components — did the export run?`);
  assert(catalogue.component_count === components.length,
    `the file claims ${catalogue.component_count} components but carries ${components.length}`);
  const bad = components.filter((c) => {
    if (!c.category || !c.raw_name) return true;
    return !(c.listings ?? []).some((l) => Number.isInteger(l.price_cents) && l.price_cents > 0);
  });
  assert(bad.length === 0, `${bad.length} rows without category, name or a priced listing`);
  return `${components.length} components with a price, generated ${String(catalogue.generated_at).slice(0, 10)}`;
});

// ---------------------------------------------------------------------------
// 3. Engine — the rules that were wrong, called directly with real catalogue rows.
//    Positive case, inverse case, a legacy raw value, and a dual-capability board.
// ---------------------------------------------------------------------------
check("engine: DDR generations are compared, not spellings", () => {
  const ddr4Board = sample(of("motherboard").filter((b) => asList(value(b, "memory_type")).includes("DDR4")),
    "no DDR4 motherboard in the catalogue");
  const ddr5Board = sample(of("motherboard").filter((b) => asList(value(b, "memory_type")).includes("DDR5")),
    "no DDR5 motherboard in the catalogue");
  const ddr4Memory = sample(of("memory").filter((m) => value(m, "memory_type") === "DDR4"),
    "no DDR4 memory in the catalogue");
  const ddr5Memory = sample(of("memory").filter((m) => value(m, "memory_type") === "DDR5"),
    "no DDR5 memory in the catalogue");

  assert(memoryIssues({ memory: ddr4Memory, motherboard: ddr4Board }).length === 0,
    "a DDR4 kit in a DDR4 board is flagged again");
  assert(memoryIssues({ memory: ddr5Memory, motherboard: ddr5Board }).length === 0,
    "a DDR5 kit in a DDR5 board is flagged");

  const mismatch = memoryIssues({ memory: ddr5Memory, motherboard: ddr4Board });
  assert(mismatch.length === 1 && mismatch[0].code === "memoryMismatch",
    "a DDR5 kit in a DDR4 board is no longer an error");

  // Legacy / raw wording, should a future shop send it: the engine's safety net.
  const rawMemory = { ...ddr4Memory, specs: { ...ddr4Memory.specs, memory_type: "DDR4-SDRAM" } };
  assert(memoryIssues({ memory: rawMemory, motherboard: ddr4Board }).length === 0,
    "raw shop wording 'DDR4-SDRAM' still breaks the comparison");
  const dualBoard = { ...ddr4Board, specs: { ...ddr4Board.specs, memory_type: ["DDR4-SDRAM", "DDR5-SDRAM"] } };
  assert(memoryIssues({ memory: ddr5Memory, motherboard: dualBoard }).length === 0,
    "a board supporting both generations rejects one of them");

  // No known type on either side must stay an honest "could not check", not a silent pass.
  const unknown = memoryIssues({ memory: { ...ddr4Memory, specs: { ...ddr4Memory.specs, memory_type: null } }, motherboard: ddr4Board });
  assert(unknown.length === 1 && unknown[0].level === "unknown",
    "a missing memory type is not reported as unchecked");

  return "positive, inverse, raw and dual cases all behave";
});

// ---------------------------------------------------------------------------
// 5. Owned parts — "I already have this" must never turn into a silent pass.
// ---------------------------------------------------------------------------
check("an owned part of unknown model is reported, not silently skipped", () => {
  const gpu = sample(of("gpu").filter((c) => filled(value(c, "length_mm"))), "no GPU with a length");
  const cpuNoIgpu = of("cpu").find((c) => value(c, "integrated_graphics") === false || value(c, "igpu") === false);

  // Own case, model not given, GPU chosen → the GPU-length check says why it could not run.
  const issues = checkCompatibility({ gpu }, { ownedUnknown: ["case"] });
  const owned = issues.filter((i) => i.code === "ownedModelUnknown");
  assert(owned.length === 1 && owned[0].level === "unknown", "owned case without a model is not reported");
  assert(owned[0].params.checks.includes("gpuLength"), "the blocked GPU-length check is not listed");

  // Nothing to compare against yet → no message (it would only be noise).
  assert(checkCompatibility({}, { ownedUnknown: ["case"] }).length === 0, "owned case reported with no other parts");

  // Own GPU, model not given → no "add a graphics card" warning for an iGPU-less CPU.
  if (cpuNoIgpu) {
    const warns = checkCompatibility({ cpu: cpuNoIgpu }, { ownedUnknown: ["gpu"] }).filter((i) => i.code === "needsGpu");
    assert(warns.length === 0, "asks for a graphics card the user already owns");
  }
  return "owned case, owned GPU and empty build behave";
});

// ---------------------------------------------------------------------------
// 4. Picker filters — a missing spec must never make a part unreachable (issue #25).
// ---------------------------------------------------------------------------
check("every part is reachable through every picker filter", () => {
  let facetCount = 0;
  for (const [category, facets] of Object.entries(FACETS)) {
    const items = of(category);
    for (const facet of facets) {
      facetCount += 1;
      const [{ options }] = facetOptions(items, [facet], {});
      // Ticking every option, the "not known" one included, must give back the whole category.
      const everything = applyFacets(items, [facet], { [facet.id]: options.map((o) => o.key) });
      assert(everything.length === items.length,
        `${category}.${facet.id}: ${items.length - everything.length} parts fall in no option`);
      assert(options.some((o) => o.key === UNKNOWN), `${category}.${facet.id} has no "not known" option`);
      for (const item of items) {
        for (const key of optionKeys(facet, item)) {
          assert(options.some((o) => o.key === key), `${category}.${facet.id}: option "${key}" is not listed`);
        }
      }
    }
  }
  // A part without the spec lands in "not known", not in "no".
  const blank = { category: "memory", specs: { memory_type: null } };
  const [memoryFacet] = FACETS.memory;
  assert(optionKeys(memoryFacet, blank).join() === UNKNOWN, "a missing memory type is not filed under 'not known'");
  return `${facetCount} facets, all parts reachable`;
});

// ---------------------------------------------------------------------------
const total = notes.length + failures.length;
if (failures.length) {
  console.log(`\nData contract FAILED — ${failures.length} of ${total} checks:\n`);
  console.log(failures.join("\n"));
  console.log("\nThe seam between scraper/ and web/ is what these checks guard; see the header of this file.\n");
  process.exit(1);
}
console.log(`\nData contract ok — ${total} checks over ${components.length} components:\n`);
console.log(notes.join("\n"));
console.log("");
