// Spec filters ("facets") for the part picker.
//
// Two rules, same as the rest of the app (issue #25):
//   1. A missing value means "not known", never "no". Every facet has an UNKNOWN bucket,
//      so a part without the spec is still reachable and never silently filtered away.
//   2. Facets are built on fields with near-full coverage and a canonical vocabulary
//      (see normalisation_report.md → Facet vocabulary). Values are shown as the pipeline
//      writes them; fixing a spelling belongs in the pipeline, not here.
//
// Semantics: options inside one facet are OR (DDR4 or DDR5), facets are AND
// (socket AM5 and DDR5). A facet with nothing selected does not filter.
//
// This file has no imports on purpose, so scripts/check-data-contract.mjs can load it
// the same way it loads lib/compat.js.

export const UNKNOWN = "__unknown__";
// A known value outside the groups a facet offers. Listed only when some part has one.
export const OTHER = "__other__";

const filled = (v) => v !== null && v !== undefined && v !== "";

// PSU wattage is a number, so it is grouped into ranges. Labels come from strings.ts.
export const WATTAGE_BUCKETS = [
  { key: "w-lt600", max: 600 },
  { key: "w-600-749", min: 600, max: 750 },
  { key: "w-750-999", min: 750, max: 1000 },
  { key: "w-gte1000", min: 1000 },
];

function wattageBucket(watts) {
  if (!filled(watts)) return UNKNOWN;
  const bucket = WATTAGE_BUCKETS.find((b) => (b.min == null || watts >= b.min) && (b.max == null || watts < b.max));
  return bucket ? bucket.key : UNKNOWN;
}

// Storage capacity, grouped by the sizes drives are sold in. Shops write 1 TB as 960,
// 1000 or 1024 GB, so each bucket's edges sit between the marketed sizes.
export const CAPACITY_BUCKETS = [
  { key: "c-lt500", max: 450 },
  { key: "c-500", min: 450, max: 900 },
  { key: "c-1tb", min: 900, max: 1500 },
  { key: "c-2tb", min: 1500, max: 3000 },
  { key: "c-4tb", min: 3000, max: 6000 },
  { key: "c-gt4tb", min: 6000 },
];

function capacityBucket(gb) {
  if (!filled(gb)) return UNKNOWN;
  const bucket = CAPACITY_BUCKETS.find((b) => (b.min == null || gb >= b.min) && (b.max == null || gb < b.max));
  return bucket ? bucket.key : UNKNOWN;
}

// Storage interface, in the few groups a buyer chooses between. The shops write the
// same thing many ways ("SATA III", "SATA", "PCI Express 3.1a", "NVMe" + a PCIe
// generation); SAS, U.2 and NVMe drives with no known generation go to "other".
export const INTERFACE_GROUPS = ["sata", "pcie-3", "pcie-4", "pcie-5"];

function interfaceGroup(specs) {
  const text = String(specs.interface ?? "");
  if (/\bSATA\b/i.test(text)) return "sata";
  const gen = String(specs.pcie_gen ?? "").match(/^[345]/)?.[0]
    ?? text.match(/PCI Express ([345])\./i)?.[1];
  if (gen) return `pcie-${gen}`;
  return filled(specs.interface) ? OTHER : UNKNOWN;
}

// Motherboard size in the four classes cases are sold for. The shops write "mikro ATX",
// "mATX", "Laajennettu ATX", "EEB"...; MSI's "mini ATX" boards (B650I EDGE) and Mini-DTX
// boards are Mini-ITX wide, server CEB/EEB boards need an E-ATX case.
export const BOARD_SIZES = ["ATX", "Micro-ATX", "Mini-ITX", "E-ATX"];
const BOARD_SIZE_SPELLINGS = {
  atx: "ATX",
  mikroatx: "Micro-ATX", microatx: "Micro-ATX", matx: "Micro-ATX", uatx: "Micro-ATX",
  miniitx: "Mini-ITX", itx: "Mini-ITX", miniatx: "Mini-ITX", minidtx: "Mini-ITX", dtx: "Mini-ITX",
  microitx: "Mini-ITX",
  laajennettuatx: "E-ATX", eatx: "E-ATX", eeb: "E-ATX", ceb: "E-ATX", ssiceb: "E-ATX",
  ssieeb: "E-ATX", xlatx: "E-ATX",
};

export function boardSize(value) {
  if (!filled(value)) return UNKNOWN;
  return BOARD_SIZE_SPELLINGS[String(value).toLowerCase().replace(/[\s\-]+/g, "")] ?? OTHER;
}

// The sockets of current desktop builds; workstation and server sockets go to OTHER.
export const DESKTOP_SOCKETS = ["AM4", "AM5", "LGA1200", "LGA1700", "LGA1851"];

function socketGroup(value) {
  if (!filled(value)) return UNKNOWN;
  const socket = String(value).toUpperCase().replace(/\s+/g, "");
  return DESKTOP_SOCKETS.includes(socket) ? socket : OTHER;
}

// CPU vendor and series. The series is read from the name ("AMD Ryzen 7 9800X3D",
// "Intel Core Ultra 5 245KF"); EPYC, Xeon, Athlon, Pentium, Celeron... go to the
// vendor's "other" series, so every CPU stays reachable.
export const CPU_VENDORS = ["AMD", "Intel"];
export const CPU_SERIES = {
  AMD: ["ryzen-3", "ryzen-5", "ryzen-7", "ryzen-9", "threadripper", "amd-other"],
  Intel: ["core-i3", "core-i5", "core-i7", "core-i9", "core-ultra-5", "core-ultra-7", "core-ultra-9", "intel-other"],
};

const componentName = (component) => String(component?.name ?? component?.raw_name ?? "");

function cpuVendor(component) {
  const text = `${component?.brand ?? ""} ${componentName(component)}`;
  if (/\bAMD\b/i.test(text)) return "AMD";
  if (/\bIntel\b/i.test(text)) return "Intel";
  return UNKNOWN;
}

function cpuSeries(component) {
  const vendor = cpuVendor(component);
  const name = componentName(component);
  if (vendor === "AMD") {
    if (/threadripper/i.test(name)) return "threadripper";
    const ryzen = name.match(/\bRyzen\s+([3579])\b/i);
    return ryzen ? `ryzen-${ryzen[1]}` : "amd-other";
  }
  if (vendor === "Intel") {
    const ultra = name.match(/\bCore\s+Ultra\s+([579])\b/i);
    if (ultra) return `core-ultra-${ultra[1]}`;
    const core = name.match(/\bCore\s+i([3579])\b/i);
    return core ? `core-i${core[1]}` : "intel-other";
  }
  return UNKNOWN;
}

// Motherboard vendor; the four big board makers by name, the rest in OTHER.
export const BOARD_VENDORS = ["ASUS", "MSI", "Gigabyte", "ASRock"];

function boardVendor(component) {
  const brand = String(component?.brand ?? "").toLowerCase();
  if (!brand) return UNKNOWN;
  return BOARD_VENDORS.find((vendor) => vendor.toLowerCase() === brand) ?? OTHER;
}

// Chipset, without the board-size letter: "B850M" and "B650I" are B850 and B650 boards.
// `chipset` is often only "AMD" / "Intel", so the data-sheet `chipset_raw` and the
// name are read first.
const CHIPSET = /\b((?:TRX|WRX|[ABHQXZW])\d{2,3}E?)[MI]?(?=\b|-)/i;

function boardChipset(specs, component) {
  for (const text of [specs.chipset_raw, specs.chipset, componentName(component)]) {
    const match = String(text ?? "").match(CHIPSET);
    if (match) return match[1].toUpperCase();
  }
  return UNKNOWN;
}

// WiFi: "no" only when a data sheet says so; a name without "WiFi" is not a "no".
export const WIFI_OPTIONS = ["yes", "no"];

function wifiOption(specs) {
  if (specs.wifi === true) return "yes";
  if (specs.wifi === false) return "no";
  return UNKNOWN;
}

// Memory kit: number of modules, then the size of one module.
export const MODULE_COUNTS = ["1", "2", "4"];
// The common module sizes; the rare ones (4 GB, 64 GB...) are in OTHER.
export const MODULE_SIZES = ["8", "16", "24", "32", "48"];

function moduleCount(specs) {
  const count = specs.modules?.count;
  if (!filled(count)) return UNKNOWN;
  return MODULE_COUNTS.includes(String(count)) ? String(count) : OTHER;
}

function moduleSize(specs) {
  const size = specs.modules?.size_gb;
  if (!filled(size)) return UNKNOWN;
  return MODULE_SIZES.includes(String(size)) ? String(size) : OTHER;
}

// GPU vendor, and under it the gaming generation. Workstation and data-centre cards
// (RTX 4000 Ada, RTX PRO, RTX A1000, Radeon Pro, Arc Pro, H200...) go to the vendor's
// "other": their model numbers would otherwise read as a gaming generation.
export const GPU_VENDORS = ["NVIDIA", "AMD", "Intel"];
export const GPU_GENERATIONS = {
  NVIDIA: ["rtx-50", "rtx-40", "rtx-30", "rtx-20", "gtx-16", "gtx-10", "nvidia-other"],
  AMD: ["rx-9000", "rx-7000", "rx-6000", "amd-other"],
  Intel: ["arc-b", "arc-a", "intel-other"],
};
// "Pro" alone is not enough: "RTX 5090 Frostbite Pro" is a gaming card.
const WORKSTATION_GPU = /\b(RTX|Radeon|AI|Arc) PRO\b|\bAda\b|Quadro|\bRTX A\d|Blackwell|\bW\d{4}\b|\b[HL]\d{1,3}S?\b|tekoäly|Server/i;

function gpuVendor(specs, component) {
  const vendor = String(specs.gpu_vendor ?? "").toUpperCase();
  const match = GPU_VENDORS.find((v) => v.toUpperCase() === vendor);
  if (match) return match;
  const name = componentName(component);
  if (/nvidia|geforce|\b[RG]TX ?\d/i.test(name)) return "NVIDIA";
  // PowerColor and Sapphire only make AMD cards ("R9700S 32GB Powercolor AI PRO").
  if (/radeon|\bRX ?\d|powercolor|sapphire/i.test(name)) return "AMD";
  if (/\bintel\b|\bArc\b/i.test(name)) return "Intel";
  return UNKNOWN;
}

function gpuGeneration(specs, component) {
  const vendor = gpuVendor(specs, component);
  if (vendor === UNKNOWN) return UNKNOWN;
  const name = componentName(component);
  const other = `${vendor.toLowerCase()}-other`;
  if (WORKSTATION_GPU.test(name)) return other;
  for (const text of [specs.chipset, specs.graphics_chipset, name]) {
    const value = String(text ?? "");
    if (vendor === "NVIDIA") {
      const m = value.match(/\b(RTX|GTX) ?(\d{2})(\d{2})\b/i);
      if (m) {
        // Gaming model numbers never end in 00 (RTX 2000, RTX 4500 are workstation cards).
        const key = `${m[1].toLowerCase()}-${m[2]}`;
        return m[3] !== "00" && GPU_GENERATIONS.NVIDIA.includes(key) ? key : other;
      }
    } else if (vendor === "AMD") {
      const m = value.match(/\bRX ?(\d)\d{3}\b/i);
      if (m) return GPU_GENERATIONS.AMD.includes(`rx-${m[1]}000`) ? `rx-${m[1]}000` : other;
    } else {
      const m = value.match(/\bArc ([AB])\d{2,3}\b/i);
      if (m) return `arc-${m[1].toLowerCase()}`;
    }
  }
  return other;
}

// VRAM: the common sizes, everything over 16 GB together, and the rest in OTHER.
export const VRAM_OPTIONS = ["8", "12", "16", "gt16"];

function vramOption(specs) {
  const gb = specs.vram_gb;
  if (!filled(gb)) return UNKNOWN;
  if (gb > 16) return "gt16";
  return VRAM_OPTIONS.includes(String(gb)) ? String(gb) : OTHER;
}

// PSU cabling: modular or not, and under "modular" how far. A data sheet that only says
// "Modulaarinen" stays "not specified" — it is never guessed into fully or semi.
export const CABLING_OPTIONS = ["modular", "non_modular"];
export const MODULAR_TYPES = ["fully_modular", "semi_modular", "modular"];

function cabling(specs) {
  if (specs.modular === "non_modular") return "non_modular";
  return MODULAR_TYPES.includes(specs.modular) ? "modular" : UNKNOWN;
}

function modularType(specs) {
  return MODULAR_TYPES.includes(specs.modular) ? specs.modular : UNKNOWN;
}

// Per category: which facets to show, in this order.
//   id      — key in strings.ts → picker.facets
//   value   — (specs, component) → the facet value(s). May return a list
//             (a motherboard that supports both DDR4 and DDR5).
//   order   — fixed option order; otherwise options are sorted by count.
//   parent  — the picker shows this facet only once a parent option is ticked, with the
//             options the ticked parent options have parts in (CPU series under the
//             vendor, chipset under the board vendor, module size under module count).
export const FACETS = {
  cpu: [
    { id: "cpuVendor", value: (s, c) => cpuVendor(c), order: CPU_VENDORS },
    // Shown under the vendor: only the series of the ticked vendor(s), all when none is.
    { id: "cpuSeries", value: (s, c) => cpuSeries(c), order: [...CPU_SERIES.AMD, ...CPU_SERIES.Intel], parent: "cpuVendor" },
    { id: "socket", value: (s) => socketGroup(s.socket), order: DESKTOP_SOCKETS },
  ],
  motherboard: [
    { id: "boardVendor", value: (s, c) => boardVendor(c), order: BOARD_VENDORS },
    { id: "chipset", value: (s, c) => boardChipset(s, c), parent: "boardVendor" },
    { id: "socket", value: (s) => socketGroup(s.socket), order: DESKTOP_SOCKETS },
    // The socket mostly settles the memory type; only LGA1700 boards come in DDR4 and DDR5.
    { id: "memoryType", value: (s) => s.memory_type, parent: "socket" },
    { id: "formFactor", value: (s) => boardSize(s.form_factor), order: BOARD_SIZES },
    { id: "wifi", value: (s) => wifiOption(s), order: WIFI_OPTIONS },
  ],
  memory: [
    { id: "memoryType", value: (s) => s.memory_type },
    { id: "moduleCount", value: (s) => moduleCount(s), order: MODULE_COUNTS },
    { id: "moduleSize", value: (s) => moduleSize(s), order: MODULE_SIZES, parent: "moduleCount" },
  ],
  gpu: [
    { id: "vendor", value: (s, c) => gpuVendor(s, c), order: GPU_VENDORS },
    { id: "gpuGeneration", value: (s, c) => gpuGeneration(s, c), order: Object.values(GPU_GENERATIONS).flat(), parent: "vendor" },
    { id: "vram", value: (s) => vramOption(s), order: VRAM_OPTIONS },
  ],
  storage: [
    { id: "capacity", value: (s) => capacityBucket(s.capacity_gb), order: CAPACITY_BUCKETS.map((b) => b.key) },
    { id: "interface", value: (s) => interfaceGroup(s), order: INTERFACE_GROUPS },
  ],
  psu: [
    { id: "wattage", value: (s) => wattageBucket(s.wattage_w), order: WATTAGE_BUCKETS.map((b) => b.key) },
    { id: "cabling", value: (s) => cabling(s), order: CABLING_OPTIONS },
    { id: "modularType", value: (s) => modularType(s), order: MODULAR_TYPES, parent: "cabling" },
  ],
  case: [{ id: "caseSize", value: (s) => s.form_factor }],
};

export function facetsFor(category) {
  return FACETS[category] ?? [];
}

// The option keys a component falls into for one facet. Never empty: no value → UNKNOWN.
export function optionKeys(facet, component) {
  const raw = facet.value(component.specs ?? {}, component);
  const list = (Array.isArray(raw) ? raw : [raw]).filter(filled).map(String);
  return list.length > 0 ? [...new Set(list)] : [UNKNOWN];
}

// selections: { [facetId]: string[] } — the option keys the user has ticked.
function matchesFacet(facet, component, selected) {
  if (!selected || selected.length === 0) return true;
  return optionKeys(facet, component).some((key) => selected.includes(key));
}

export function applyFacets(items, facets, selections, getComponent = (x) => x) {
  return items.filter((item) => facets.every((f) => matchesFacet(f, getComponent(item), selections[f.id])));
}

// Options for every facet, each with the number of items it would show.
// A count respects the *other* facets' selections but not its own, so ticking a second
// option in the same facet shows how many more parts it adds (standard faceted search).
// The UNKNOWN option is always listed, even at 0, so it is clear nothing is hidden.
export function facetOptions(items, facets, selections, getComponent = (x) => x) {
  return facets.map((facet) => {
    const others = facets.filter((f) => f.id !== facet.id);
    const pool = applyFacets(items, others, selections, getComponent);
    const counts = new Map();
    for (const item of pool) {
      for (const key of optionKeys(facet, getComponent(item))) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    // Options that are ticked stay visible even if another facet brought them to 0.
    for (const key of selections[facet.id] ?? []) if (!counts.has(key)) counts.set(key, 0);
    if (facet.order) for (const key of facet.order) if (!counts.has(key)) counts.set(key, 0);
    if (!counts.has(UNKNOWN)) counts.set(UNKNOWN, 0);

    const known = [...counts.entries()].filter(([key]) => key !== UNKNOWN);
    // OTHER, and anything outside a fixed order, goes after the named options.
    const rank = (key) => (key === OTHER ? Infinity : facet.order ? (facet.order.indexOf(key) + 1 || Infinity) : 0);
    known.sort(([a, ca], [b, cb]) => rank(a) - rank(b) || (facet.order ? 0 : cb - ca || a.localeCompare(b)));
    const options = [...known, [UNKNOWN, counts.get(UNKNOWN)]].map(([key, count]) => ({ key, count }));
    return { facet, options };
  });
}
