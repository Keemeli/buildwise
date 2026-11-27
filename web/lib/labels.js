// A short, readable name for a part, built only from values the shop itself published.
//
// The picker used to show the shop's full title — "Asrock AMD Radeon RX 9060 XT Challenger
// 16GB OC GDDR6 PCI Express 5.0 x16" — which buries the two things a builder looks for.
//
// The rule per category is "what reads fastest, without repeating the spec line below it":
// a graphics card by chipset + memory ("RX 9060 XT · 16 GB GDDR6"), memory and drives by
// size and type ("16 GB DDR4-3200" reads better than a part number), everything else by the
// shop's own brand + model ("DeepCool PN750M" instead of the full sentence).
//
// Two rules keep it honest:
//  * nothing is invented: every word comes from a parsed field, and an unknown field is
//    left out rather than guessed;
//  * it never replaces the shop's name: `exactName()` returns what the shop wrote, which
//    the UI shows on hover and on the result page. This is a label, not a rename.
//
// Dependency-free on purpose: `web/scripts/check-data-contract.mjs` loads it through a
// data: URL (node cannot import an ESM `.js` from a package without "type": "module"),
// and a data: URL cannot resolve relative imports.
//
// Storage counts in 1024-based units, so 2048 GB is shown as 2 TB and 240 GB stays in GB.

const KIND_LABELS = {
  nvme: "NVMe", ssd: "SSD", hdd: "HDD",
  "solid state drive": "SSD", "hard disk drive": "HDD",
};

const present = (value) =>
  value !== null && value !== undefined && value !== "" && value !== false &&
  !(Array.isArray(value) && value.length === 0);

/** Joins the parts that are known; unknown ones are dropped, never guessed. */
export const line = (...parts) => parts.filter(present).join(" · ");

export function formatCapacity(gb) {
  if (!present(gb)) return null;
  if (gb >= 1000) {
    // The normaliser counts 1 TB as 1024 GB, but some shops write 1000 GB for the same
    // drive, so both multiples are shown as whole terabytes.
    const tb = gb % 1024 === 0 ? gb / 1024 : gb / 1000;
    return `${Math.round(tb * 10) / 10} TB`;
  }
  return `${gb} GB`;
}

/** What the shop wrote, exactly — the traceable name behind every label. */
export function exactName(part) {
  return part?.name || part?.raw_name || "";
}

const brandModel = (part) => [part?.brand, part?.model].filter(present).join(" ");

function gpuLabel(part, s) {
  // The brand has to be in the label: a shop lists fifteen "GeForce RTX 5070 · 12 GB" rows
  // from different board partners, and without it they are indistinguishable. The chipset
  // usually repeats the vendor ("NVIDIA GeForce RTX 5070"), so drop that word when the
  // vendor field knows it — "Inno3D GeForce GT 710 · 2 GB GDDR3", "Asrock RX 9060 XT · 16 GB GDDR6".
  const raw = String(s.chipset || s.graphics_chipset || "").trim();
  const vendor = String(s.gpu_vendor || "").trim();
  const chip = vendor && raw.toLowerCase().startsWith(vendor.toLowerCase() + " ")
    ? raw.slice(vendor.length + 1)
    : raw;
  const memory = present(s.vram_gb)
    ? [s.vram_gb && `${s.vram_gb} GB`, s.memory_type].filter(present).join(" ")
    : s.memory_type;
  // A row without a parsed chipset (every Jimms row until specs are collected for them,
  // issue #42) falls back to the shop's model — never to a bare brand.
  const identity = chip || part?.model || null;
  return line([part?.brand, identity].filter(present).join(" ") || null, memory) || exactName(part);
}

function memoryLabel(s) {
  const size = formatCapacity(s.capacity_gb);
  const modules = present(s.modules?.count) ? `(${s.modules.count}×)` : null;
  const sizeText = [size, modules].filter(present).join(" ");
  const speedText = present(s.memory_type) && present(s.speed_mhz)
    ? `${s.memory_type}-${s.speed_mhz}`
    : s.memory_type || (present(s.speed_mhz) ? `${s.speed_mhz} MHz` : null);
  return line(sizeText || null, speedText, present(s.cas_latency) && `CL${s.cas_latency}`);
}

function storageLabel(s) {
  const kind = KIND_LABELS[String(s.kind ?? "").toLowerCase()] || s.kind;
  return line(formatCapacity(s.capacity_gb), kind, s.form_factor);
}

function psuLabel(s) {
  const watts = present(s.wattage_w) ? `${s.wattage_w} W` : null;
  const efficiency = present(s.efficiency)
    ? (String(s.efficiency).includes("80") ? String(s.efficiency) : `80+ ${s.efficiency}`)
    : null;
  return line(watts, efficiency);
}

/** True when the shop's own model string already says it, so the label must not repeat it. */
function alreadySaid(model, value) {
  return present(value) && present(model) && String(model).toLowerCase().includes(String(value).toLowerCase());
}

function caseLabel(part, s) {
  const model = brandModel(part);
  const size = alreadySaid(model, s.tower_size) ? null : s.tower_size || s.form_factor;
  return line(model || null, alreadySaid(model, size) ? null : size);
}

function motherboardLabel(s) {
  // `chipset` can hold the vendor ("AMD") while `chipset_raw` holds "B650"; prefer the
  // wording that carries a number.
  const chip = [s.chipset_raw, s.chipset].find((value) => present(value) && /\d/.test(String(value))) ?? null;
  return line(chip, s.socket, s.form_factor);
}

/**
 * The label shown as a part's name in the picker and the result table.
 * Falls back to brand + model and then to the shop's own name, so a row is never nameless.
 */
export function partLabel(part) {
  const s = part?.specs || {};
  const model = brandModel(part);

  switch (part?.category) {
    case "gpu":
      return gpuLabel(part, s) || model || exactName(part);
    case "cpu":
      return line(s.family || model || null) || exactName(part);
    case "memory":
      return memoryLabel(s) || model || exactName(part);
    case "storage":
      return storageLabel(s) || model || exactName(part);
    case "psu":
      return psuLabel(s) || model || exactName(part);
    case "motherboard":
      return motherboardLabel(s) || model || exactName(part);
    case "case":
      return caseLabel(part, s) || model || exactName(part);
    default:
      return line(s.chipset, model) || exactName(part);
  }
}
