#!/usr/bin/env python3
"""BuildWise normaliser — raw scraped product names -> structured components.

Reads data/raw/datatronic_*.json (as produced by scraper/scrape.py) and writes:
    data/normalised/components.json          components with their listings + prices
    data/normalised/normalisation_report.md  coverage report + review list

Design rules:
    * Nothing is dropped: every component keeps `raw_name`, the exact string the shop
      published. Normalisation adds structure, it never replaces the source.
    * Missing is missing: a spec that cannot be read from the name stays null and is
      counted as a gap in the report. We never invent a value to fill a field.
    * Inferred values are labelled: `socket` for CPUs is inferred from the product
      family and marked with "socket_source": "inferred_from_family" so the engine
      can treat it as lower confidence than a parsed value.

Usage:
    python normalise.py
    python normalise.py --raw-dir ../data/raw --out ../data/normalised
    python normalise.py --category gpu
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "normalised"

CATEGORIES = ("gpu", "cpu", "motherboard", "memory", "storage", "psu", "case")

# What we expect to be able to say about each category. Used by the report to show
# gaps per field rather than hiding them in an average.
EXPECTED_FIELDS = {
    "gpu": ("chipset", "vram_gb", "memory_type", "gpu_vendor"),
    "cpu": ("family", "socket", "base_clock_ghz", "cache_mb"),
    "motherboard": ("chipset", "socket", "form_factor", "memory_type"),
    "memory": ("memory_type", "capacity_gb", "modules", "speed_mhz", "cas_latency"),
    "storage": ("capacity_gb", "interface", "form_factor", "pcie_gen"),
    "psu": ("wattage_w", "efficiency", "atx_version", "form_factor"),
    "case": ("form_factor", "color"),
}

# Most specific alternatives first: a loose pattern would otherwise match
# "Intel Core i5" and lose the model number that carries the generation.
FAMILY_PATTERN = (
    r"(Ryzen\s+\d\s+[\w-]+|Core\s+i[3579]-[\w]+|Core\s+Ultra\s+\d\s+[\w-]+|"
    r"Athlon\s+[\w-]+|Pentium\s+[\w-]+)"
)

# CPU socket is not in the product name on the AMD side; see cpu_socket_from_family.

BRANDS = (
    "be quiet!", "Cooler Master", "Kingston Technology", "Fractal Design", "Lian Li",
    "Team Group", "Thermalright", "Thermaltake", "SilverStone", "DeepCool", "Noctua",
    "Endorfy", "Chieftec", "Sharkoon", "Corsair", "Seasonic", "Patriot", "Goodram",
    "Crucial", "Samsung", "Sandisk", "SanDisk", "Seagate", "Western Digital", "PNY",
    "Kingston", "G.Skill", "G.SKILL", "Adata", "ADATA", "Lexar", "Netac", "Silicon Power",
    "Gigabyte", "GIGABYTE", "Asrock", "ASRock", "ASUS", "MSI", "Palit", "Gainward",
    "Zotac", "Inno3D", "PowerColor", "Sapphire", "XFX", "Pulse", "EVGA", "SAMA", "Zalman",
    "Antec", "NZXT", "Phanteks", "Arctic", "Scythe", "AMD", "Intel", "Raspberry Pi",
)

# Words that belong to the shop's category description, not to the model name.
CATEGORY_NOISE = {
    "gpu": ("näytönohjain", "naytonohjain"),
    "cpu": ("suoritin", "prosessori"),
    "motherboard": ("emolevy",),
    "memory": ("muistimoduuli", "muisti"),
    "storage": ("ssd-massamuisti", "sisäinen kiintolevy", "ssd-levy", "kiintolevy", "ssd"),
    "psu": ("virtalähdeyksikkö", "virtalähde", "power supply"),
    "case": ("tietokonekotelo", "kotelo"),
}


# --------------------------------------------------------------------------- helpers

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def extract_brand(name: str) -> Tuple[Optional[str], str]:
    """Return (brand, remainder). Tries the longest brand match first."""
    lowered = name.lower()
    for brand in sorted(BRANDS, key=len, reverse=True):
        if lowered.startswith(brand.lower()):
            return brand, clean(name[len(brand):])
    return None, clean(name)


def strip_noise(remainder: str, category: str) -> str:
    text = remainder
    for word in CATEGORY_NOISE.get(category, ()):
        text = re.sub(re.escape(word), " ", text, flags=re.IGNORECASE)
    return clean(text.strip(" -|,"))


def search(pattern: str, text: str, flags: int = re.IGNORECASE) -> Optional[str]:
    """First non-empty capture group (group 0 when the pattern has no groups)."""
    match = re.search(pattern, text, flags)
    if not match:
        return None
    for group in match.groups():
        if group:
            return group.strip()
    return match.group(0).strip()


def as_int(value: Optional[str], multiplier: int = 1) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value.replace(",", ".")) * multiplier))
    except ValueError:
        return None


def as_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


# ----------------------------------------------------------------- per-category parsers

def parse_gpu(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    specs["chipset"] = search(r"\b((?:RTX|RX|GTX)\s?\d{3,4}\s?(?:Ti|SUPER|XTX|XT|GRE)?)\b", name) or \
        search(r"\b(Arc\s+(?:Pro\s+)?[AB]\d{3})\b", name)
    vram = search(r"\b(\d{1,2})\s*GB\s*(GDDR\d[A-Z]?|HBM\d?)", name)
    specs["vram_gb"] = as_int(vram)
    specs["memory_type"] = search(r"\b(GDDR\d[A-Z]?|HBM\d?)\b", name)
    if re.search(r"\b(NVIDIA|GeForce|RTX|GTX)\b", name, re.I):
        specs["gpu_vendor"] = "NVIDIA"
    elif re.search(r"\bArc\b", name, re.I):
        specs["gpu_vendor"] = "Intel"
    elif re.search(r"\b(AMD|Radeon|RX)\b", name, re.I):
        specs["gpu_vendor"] = "AMD"
    else:
        specs["gpu_vendor"] = None
    return specs


def cpu_socket_from_family(family: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """AMD SKUs do not carry the socket in the name; Intel's generation does.

    Returns (socket, source) where source records that this is inferred, not parsed,
    so the engine can weight it as lower confidence.
    """
    if not family:
        return None, None
    lowered = family.lower()
    if "ryzen" in lowered:
        sku = search(r"(\d{4})", family)
        if sku:
            number = int(sku)
            if 7000 <= number <= 9999:
                return "AM5", "inferred_from_sku"
            if 3000 <= number <= 5999:
                return "AM4", "inferred_from_sku"
        return None, None
    if "core ultra" in lowered:
        return "LGA1851", "inferred_from_family"
    generation = re.search(r"i[3579]-(\d{2})\d{3}", family)
    if generation:
        series = int(generation.group(1))
        if 12 <= series <= 14:
            return "LGA1700", "inferred_from_generation"
        if series in (8, 9, 10, 11):
            return "LGA1200", "inferred_from_generation"
    return None, None


def parse_cpu(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    specs["family"] = search(FAMILY_PATTERN, name)
    family = specs["family"]
    specs["base_clock_ghz"] = as_float(search(r"(\d+(?:[,.]\d+)?)\s*GHz", name))
    specs["cache_mb"] = as_int(search(r"(\d+)\s*MB\s*(?:Smart\s?Cache|L2\s*&\s*L3|L3|L2)", name))
    specs["packaging"] = "boxed" if re.search(r"laatikko", name, re.I) else None
    specs["socket"], specs["socket_source"] = cpu_socket_from_family(family)
    specs["igpu"] = True if re.search(r"\b(iGPU|Integrated|Radeon Graphics|UHD Graphics)\b", name, re.I) else None
    specs["efficiency_cores"] = as_int(search(r"(\d+)\s*E-cores", name))
    return specs


# Chipset -> memory generation is deterministic on the AMD side (the chipset itself
# decides between DDR4 and DDR5). Intel boards can ship either, so they stay null
# unless the product name says so.
AMD_DDR4_CHIPSETS = {"A320", "B350", "B450", "X470", "A520", "B550", "X570"}
AMD_DDR5_CHIPSETS = {"A620", "B650", "B650E", "X670", "X670E", "B840", "B850", "X870", "X870E"}
INTEL_CHIPSETS = {"H610", "B660", "H670", "Z690", "B760", "H770", "Z790", "Z890", "B860", "H810", "W680"}
KNOWN_CHIPSETS = AMD_DDR4_CHIPSETS | AMD_DDR5_CHIPSETS | INTEL_CHIPSETS


def chipset_family(chipset_raw: Optional[str]) -> Optional[str]:
    """'B550M'/'B650I' are the mATX/ITX boards of the B550/B650 chipset, not a new
    chipset. 'X870E'/'B650E' are genuinely different chipsets and keep their suffix."""
    if not chipset_raw:
        return None
    if chipset_raw[-1] in ("M", "I") and chipset_raw[:-1] in KNOWN_CHIPSETS:
        return chipset_raw[:-1]
    return chipset_raw


def parse_motherboard(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    chipset_raw = search(r"\b([ABHXZ]\d{3}[A-Z]?)\b", name.upper())
    specs["chipset"] = chipset_family(chipset_raw)
    specs["chipset_raw"] = chipset_raw
    socket = search(r"\b(?:Kanta|Socket|Pistoke)\s*(AM\d|LGA\s?\d{4})\b", name) or search(r"\b(LGA\s?\d{4})\b", name.upper())
    specs["socket"] = re.sub(r"\s+", "", socket).upper() if socket else None
    form = search(r"\b(E-ATX|mikro\s?ATX|Micro\s?ATX|mATX|Mini-ITX|ATX)\b", name)
    specs["form_factor"] = {"mikro atx": "Micro-ATX", "micro atx": "Micro-ATX", "matx": "Micro-ATX"}.get(
        (form or "").lower(), form)
    memory_type = search(r"\b(DDR[345])\b", name.upper())
    memory_source = "parsed_from_name" if memory_type else None
    if memory_type is None:
        chipset = specs.get("chipset")
        if chipset in AMD_DDR4_CHIPSETS:
            memory_type, memory_source = "DDR4", "inferred_from_chipset"
        elif chipset in AMD_DDR5_CHIPSETS:
            memory_type, memory_source = "DDR5", "inferred_from_chipset"
    specs["memory_type"] = memory_type
    specs["memory_type_source"] = memory_source
    specs["wifi"] = bool(re.search(r"wifi|wireless", name, re.I)) or None
    return specs


def parse_memory(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    specs["memory_type"] = search(r"\b(DDR[345])\b", name.upper())
    modules = re.search(r"(\d)\s*[x×]\s*(\d+)\s*GB", name, re.I) or re.search(r"\((\d)x(\d+)GB\)", name, re.I)
    if modules:
        specs["modules"] = {"count": int(modules.group(1)), "size_gb": int(modules.group(2))}
        specs["capacity_gb"] = int(modules.group(1)) * int(modules.group(2))
    else:
        specs["modules"] = None
        specs["capacity_gb"] = as_int(search(r"\b(\d{1,3})\s*GB\b", name))
    speed = search(r"\b(\d{4,5})\s*MHz\b", name) or search(r"DDR\d[- ](\d{4})", name.upper()) or search(r"IR-(\d{4})", name)
    specs["speed_mhz"] = as_int(speed)
    specs["cas_latency"] = as_int(
        search(r"\bCL(\d{1,2})\b", name.upper())
        or search(r"C(\d{2})(?![0-9])", name.upper())   # F4-3200C16D-16GIS, CMK…6000C38
        or search(r"Z(\d{2})(?![0-9])", name.upper())   # CMK…6000Z36W
        or search(r"L(\d{2})S\b", name.upper())         # IR-6000D564L30S
    )
    form = search(r"\b(DIMM|SODIMM|288-pin|SO-DIMM)\b", name)
    specs["form_factor"] = clean(form) if form else None
    specs["ecc"] = True if re.search(r"\bECC\b", name, re.I) else None
    return specs


def parse_storage(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    capacity = re.search(r"(\d+(?:[,.]\d+)?)\s*(TB|GB)\b", name, re.I)
    if capacity:
        value = float(capacity.group(1).replace(",", "."))
        specs["capacity_gb"] = int(round(value * 1024)) if capacity.group(2).upper() == "TB" else int(value)
    else:
        specs["capacity_gb"] = None
    specs["interface"] = "NVMe" if re.search(r"\bNVMe\b", name, re.I) else (
        "SATA" if re.search(r"\b(?:Serial ATA|SATA)\b", name, re.I) else None)
    form = search(r"(M\.2\s?2280|M\.2|2[,.]5\"|3[,.]5\"|U\.2)", name, re.I)
    specs["form_factor"] = clean(form).replace("2,5", "2.5").replace("3,5", "3.5") if form else None
    specs["pcie_gen"] = search(r"(?:PCIe|PCI Express)\s?(\d\.\d)", name)
    specs["kind"] = "hdd" if re.search(r"kiintolevy", name, re.I) else (
        "nvme" if specs["interface"] == "NVMe" else "sata-ssd" if specs["interface"] == "SATA" else None)
    return specs


def parse_psu(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    specs["wattage_w"] = as_int(search(r"\b(\d{3,4})\s*W\b", name.upper().replace("|", " ")))
    eff = search(r"\b(?:80\s?Plus\s?)?(Titanium|Platinum|Gold|Silver|Bronze|White)\b", name, re.I)
    specs["efficiency"] = eff.capitalize() if eff else None
    specs["atx_version"] = search(r"\bATX\s?(\d\.\d)\b", name, re.I)
    specs["form_factor"] = "SFX" if re.search(r"\bSFX\b", name, re.I) else (
        "ATX" if re.search(r"\bATX\b", name, re.I) else None)
    specs["modular"] = True if re.search(r"modulaarinen|fully modular|modular", name, re.I) else None
    specs["connectors"] = search(r"\b(\d+\+\d+\s*pin|24-pin)\b", name, re.I)
    return specs


def parse_case(name: str) -> Dict[str, Any]:
    specs: Dict[str, Any] = {}
    form = search(r"\b(Full\s?Tower|Midi\s?Tower|Mini\s?Tower|Mini-ITX|Micro-ATX)\b", name, re.I)
    specs["form_factor"] = form
    color = None
    for word, english in (("musta", "black"), ("valkoinen", "white"), ("harmaa", "grey"), ("puu", "wood")):
        if re.search(rf"\b{word}\b", name, re.I):
            color = english
            break
    specs["color"] = color
    # Deliberately unknown: case dimensions and max GPU length are not in the name.
    specs["max_gpu_length_mm"] = None
    return specs


PARSERS = {
    "gpu": parse_gpu, "cpu": parse_cpu, "motherboard": parse_motherboard,
    "memory": parse_memory, "storage": parse_storage, "psu": parse_psu, "case": parse_case,
}


# ---------------------------------------------------------------------------- pipeline

def iter_raw_items(raw_dir: Path, only_category: Optional[str]) -> List[Dict[str, Any]]:
    """Read every scraped payload in raw_dir, whatever shop produced it.

    File name convention is <shop>_<category>_p<n>_<date>.json, so any future
    scraper (Proshop, Jimms) is picked up without changing this function.
    """
    items: List[Dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        category = payload.get("category")
        if not category or (only_category and category != only_category):
            continue
        for item in payload.get("items", []):
            items.append({
                "category": category,
                "raw_name": clean(item.get("name") or ""),
                "price_cents": item.get("price_cents"),
                "url": item.get("url"),
                "external_id": item.get("external_id"),
                "shop": payload.get("shop", "Datatronic"),
                "snapshot_date": (payload.get("fetched_at") or "")[:10] or date.today().isoformat(),
                "source_file": path.name,
            })
    return items


# Shop listings contain a few rows that are not hardware at all (assembly services,
# monitor accessories). They must not reach the compatibility engine.
NON_COMPONENT_PATTERN = (
    r"kasauspalvelu|asennuspalvelu|käyttöjärjestelmän asennus|"
    r"\bscreenbar\b|näytön valo|monitor light|hiiri|näppäimistö|kuulokkeet|"
    r"\bpalvelu\b|takuu|lisätakuu"
)


def is_non_component(raw_name: str) -> bool:
    return bool(re.search(NON_COMPONENT_PATTERN, raw_name, re.I))


def normalise_item(item: Dict[str, Any]) -> Dict[str, Any]:
    category = item["category"]
    raw_name = item["raw_name"]
    parser = PARSERS.get(category)
    brand, remainder = extract_brand(raw_name)
    model = strip_noise(remainder, category) if parser else remainder
    specs = parser(raw_name) if parser else {}
    missing = [f for f in EXPECTED_FIELDS.get(category, ()) if not specs.get(f)]
    # A row where nothing could be parsed at all is usually a product the shop filed
    # under the wrong category. Keep it, flag it, and let the report surface it.
    suspect = parser is not None and len(missing) == len(EXPECTED_FIELDS.get(category, ()))

    return {
        "category": category,
        "brand": brand,
        "model": model,
        "raw_name": raw_name,          # never dropped
        "specs": specs,
        "missing_specs": missing,
        "category_confidence": "suspect" if suspect else "ok",
        "listing": {
            "shop": item["shop"],
            "url": item["url"],
            "external_id": item["external_id"],
            "price_cents": item["price_cents"],
            "snapshot_date": item["snapshot_date"],
        },
    }


def dedupe(components: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    merged: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    duplicates = 0
    for component in components:
        key = (component["category"], (component["brand"] or "").lower(), component["model"].lower())
        existing = merged.get(key)
        if existing is None:
            component["listings"] = [component.pop("listing")]
            merged[key] = component
            continue
        duplicates += 1
        listing = component["listing"]
        if all(l["url"] != listing["url"] for l in existing["listings"]):
            existing["listings"].append(listing)
        # keep the best-covered spec set (more fields read from the name wins)
        if len(component["specs"]) - len(component["missing_specs"]) > len(existing["specs"]) - len(existing["missing_specs"]):
            existing["specs"] = component["specs"]
            existing["missing_specs"] = component["missing_specs"]
    return list(merged.values()), duplicates


def load_product_specs(path: Path) -> Dict[str, Dict[str, Any]]:
    """specs.json written by scraper/specs.py, keyed by product URL."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {url: entry for url, entry in payload.get("items", {}).items()
            if entry.get("status") == "ok" and entry.get("specs")}


def merge_product_specs(components: List[Dict[str, Any]],
                        specs_path: Path) -> Dict[str, int]:
    """Overwrite name-derived values with values parsed from the product page.

    A parsed value always wins over a guessed one, but the provenance is kept:
    every field that came from a data sheet is recorded in `spec_sources`, and the
    CPU `socket_source` stops saying "inferred" once a real socket was read.
    """
    specs_by_url = load_product_specs(specs_path)
    stats = {"components_matched": 0, "fields_parsed": 0, "upgraded_from_inferred": 0,
             "sockets_parsed": 0, "gaps_closed": 0}
    if not specs_by_url:
        return stats

    for component in components:
        sources = component.setdefault("spec_sources", {})
        matched: Dict[str, Any] = {}
        for listing in component["listings"]:
            entry = specs_by_url.get(listing["url"])
            if entry:
                matched.update(entry["specs"])
        if not matched:
            continue
        stats["components_matched"] += 1

        for field, value in matched.items():
            if value in (None, [], ""):
                continue
            previous = component["specs"].get(field)
            if previous is not None and sources.get(field, "").startswith("inferred"):
                stats["upgraded_from_inferred"] += 1
            if previous is None:
                if field in component.get("missing_specs", []):
                    component["missing_specs"] = [f for f in component["missing_specs"] if f != field]
                    stats["gaps_closed"] += 1
                stats["fields_parsed"] += 1
            component["specs"][field] = value
            sources[field] = "parsed_product_page"

        if matched.get("socket") and component["specs"].get("socket_source"):
            component["specs"]["socket_source"] = "parsed_product_page"
            stats["sockets_parsed"] += 1

    return stats


def write_report(out_dir: Path, components: List[Dict[str, Any]], duplicates: int,
                 scanned: int, excluded: List[str],
                 spec_stats: Optional[Dict[str, int]] = None) -> Path:
    lines: List[str] = []
    lines.append(f"# Normalisation report — {date.today().isoformat()}")
    lines.append("")
    lines.append(f"Scanned {scanned} raw products from `data/raw/`, produced "
                 f"**{len(components)} unique components** ({duplicates} duplicate rows merged).")
    lines.append("")
    lines.append("Missing values are reported, not filled. A `null` spec means the shop's "
                 "product name does not contain that information.")
    lines.append("")

    lines.append("## Coverage per category")
    lines.append("")
    lines.append("| Category | Components | Field | Parsed | Coverage |")
    lines.append("|---|---|---|---|---|")
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for component in components:
        by_category[component["category"]].append(component)

    for category in CATEGORIES:
        group = by_category.get(category, [])
        if not group:
            continue
        for field in EXPECTED_FIELDS.get(category, ()):
            found = sum(1 for c in group if c["specs"].get(field))
            pct = round(100 * found / len(group))
            lines.append(f"| {category} | {len(group)} | `{field}` | {found} | {pct}% |")
    lines.append("")

    if spec_stats and spec_stats.get("components_matched"):
        lines.append("## Values parsed from product pages (data sheet)")
        lines.append("")
        lines.append(f"- Components matched to a product page: **{spec_stats['components_matched']}**")
        lines.append(f"- Fields filled in from the data sheet: {spec_stats['fields_parsed']} "
                     f"({spec_stats['gaps_closed']} gaps in the name-based specs closed)")
        lines.append(f"- Guessed values replaced by parsed ones: {spec_stats['upgraded_from_inferred']}")
        lines.append(f"- CPU sockets now parsed instead of inferred: {spec_stats['sockets_parsed']}")
        lines.append("")
        lines.append("Each such field is recorded in the component's `spec_sources` as "
                     "`parsed_product_page`. It comes from the shop's own data sheet for that exact "
                     "product, not from the product name.")
        lines.append("")

    lines.append("## Products needing review (fewest specs found)")
    lines.append("")
    review = sorted(components, key=lambda c: (len(c["missing_specs"]), c["raw_name"]), reverse=True)[:15]
    for component in review:
        missing = ", ".join(component["missing_specs"]) or "none"
        lines.append(f"- **{component['category']}** — `{component['raw_name'][:80]}` — missing: {missing}")
    lines.append("")

    lines.append("## Rows excluded as non-components")
    lines.append("")
    lines.append(f"{len(excluded)} scraped rows were not hardware (assembly services or "
                 "accessories the shop lists inside a component category). They are kept in "
                 "`excluded_non_components.json` but must never reach the compatibility engine.")
    lines.append("")
    for name in excluded[:10]:
        lines.append(f"- `{name[:90]}`")
    lines.append("")

    suspects = [c for c in components if c.get("category_confidence") == "suspect"]
    if suspects:
        lines.append("## Suspect categories (nothing parsed at all)")
        lines.append("")
        for component in suspects[:10]:
            lines.append(f"- **{component['category']}** — `{component['raw_name'][:80]}`")
        lines.append("")

    if components:
        prices = [l["price_cents"] for c in components for l in c["listings"] if l["price_cents"]]
        if prices:
            lines.append("## Sanity check")
            lines.append("")
            lines.append(f"- Component listings with a price: {len(prices)}")
            lines.append(f"- Median price: {statistics.median(prices) / 100:.2f} €")
            lines.append(f"- Min {min(prices) / 100:.2f} € / max {max(prices) / 100:.2f} €")
            lines.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "normalisation_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalise scraped product names into components.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--category", choices=CATEGORIES, help="normalise a single category only")
    args = parser.parse_args()

    if not args.raw_dir.exists():
        print(f"no raw data at {args.raw_dir} — run scraper/scrape.py first", file=sys.stderr)
        return 1

    raw_items = iter_raw_items(args.raw_dir, args.category)
    if not raw_items:
        print("no items found in raw data", file=sys.stderr)
        return 1

    excluded = [item["raw_name"] for item in raw_items if is_non_component(item["raw_name"])]
    products = [item for item in raw_items if not is_non_component(item["raw_name"])]

    normalised = [normalise_item(item) for item in products]
    components, duplicates = dedupe(normalised)
    spec_stats = merge_product_specs(components, args.out / "specs.json")

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": date.today().isoformat(),
        "source": "Datatronic (scraped category listings)",
        "component_count": len(components),
        "components": components,
    }
    components_path = args.out / "components.json"
    components_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    excluded_path = args.out / "excluded_non_components.json"
    excluded_path.write_text(json.dumps({"excluded": excluded}, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(args.out, components, duplicates, len(raw_items), excluded, spec_stats)

    print(f"scanned {len(raw_items)} raw products → {len(components)} components "
          f"({duplicates} duplicates merged, {len(excluded)} non-components excluded)")
    print(f"wrote {components_path}")
    print(f"wrote {excluded_path}")
    print(f"wrote {report_path}")

    by_category: Dict[str, int] = defaultdict(int)
    for component in components:
        by_category[component["category"]] += 1
    for category in CATEGORIES:
        if by_category.get(category):
            without_specs = sum(1 for c in components
                                if c["category"] == category and len(c["missing_specs"]) == len(EXPECTED_FIELDS[category]))
            print(f"  {category:12} {by_category[category]:>3} components "
                  f"({without_specs} suspect: nothing parsed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())