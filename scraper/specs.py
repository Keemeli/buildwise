#!/usr/bin/env python3
"""BuildWise data worker — product-page data sheet extraction.

Category listings carry only a name and a price. Product pages carry the full
manufacturer data sheet, embedded in the page as a JSON array of name/value pairs
(`"features": [{"name": "Tehonkulutus (maks.)", "value": "180 W"}, ...]`).

This script fetches one product page per SKU, reads that array, and maps the labels
we understand onto canonical spec fields:

    data/normalised/specs.json        parsed specs per product URL (+ provenance)
    data/normalised/specs_report.md   coverage per field, and the labels we did NOT map

Design rules (same as the rest of the pipeline):
    * Nothing is invented. A label we do not recognise is reported, never guessed.
    * Every value keeps its provenance: source "product_page" + the fetch timestamp.
    * Fields the product name could only infer (CPU socket, motherboard memory type)
      are upgraded to parsed values once a real data sheet provides them.
    * Polite by default: one request per SKU, `--delay` seconds apart, raw HTML
      cached per day so a rerun the same day costs zero requests.

Usage:
    python specs.py --category gpu --limit 24        # smoke test one listing page
    python specs.py --category gpu --category cpu    # only these categories
    python specs.py --all                            # everything (~4000 SKUs, ~67 min)
    python specs.py --all --delay 1.2 --force        # ignore today's cache, refetch
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "normalised"
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "html" / "specs"

USER_AGENT = "BuildWise-course-project/0.1 (eekarjal24@students.oamk.fi)"
CATEGORIES = ("gpu", "cpu", "motherboard", "memory", "storage", "psu", "case")

# --------------------------------------------------------------------------- value parsing

def to_number(text: str) -> Optional[float]:
    """'291,9' / '291.9' / '1 234' -> float. Finnish pages use a comma."""
    cleaned = text.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group(0)) if match else None


def parse_watts(text: str) -> Optional[int]:
    value = to_number(text)
    return int(round(value)) if value is not None else None


def parse_mm(text: str) -> Optional[float]:
    """'291,9 mm' -> 291.9 ; '38 cm' -> 380.0 ; '0,5 m' -> 500.0"""
    value = to_number(text)
    if value is None:
        return None
    lowered = text.lower()
    if re.search(r"\d\s*cm", lowered):
        value *= 10
    elif re.search(r"\d\s*m\b", lowered) and not re.search(r"\d\s*mm", lowered):
        value *= 1000
    return round(value, 1)


def parse_mhz(text: str) -> Optional[int]:
    value = to_number(text)
    if value is None:
        return None
    if "GHz" in text:
        value *= 1000
    return int(round(value))


def parse_mb(text: str) -> Optional[int]:
    """Cache size: '104 MB' -> 104, '1 GB' -> 1024, '65 MB' -> 65."""
    value = to_number(text)
    if value is None:
        return None
    if "gb" in text.lower():
        value *= 1024
    return int(round(value))


def parse_gb(text: str) -> Optional[int]:
    """'2000 GB' -> 2000 ; '2 TB' -> 2048."""
    value = to_number(text)
    if value is None:
        return None
    if "tb" in text.lower():
        value *= 1024
    return int(round(value))


def parse_socket(text: str) -> Optional[str]:
    """Normalised exactly like normalise.py: 'Pistoke AM5' -> 'AM5', 'LGA 1851' -> 'LGA1851'."""
    match = re.search(r"(AM\d|LGA\s?\d{3,4}|sTR\d|FM\d|TR4|SP\d)", text, re.IGNORECASE)
    return re.sub(r"\s+", "", match.group(1)).upper() if match else None


def parse_bool(text: str) -> Optional[bool]:
    lowered = text.strip().lower()
    if lowered in {"kyllä", "kylla", "yes", "true"}:
        return True
    if lowered in {"ei", "no", "false"}:
        return False
    return None


def parse_channels(text: str) -> Optional[int]:
    """'Kaksikanava' / 'Dual-channel' / '2' -> 2 channels."""
    lowered = text.strip().lower()
    if "quad" in lowered or "neli" in lowered:
        return 4
    if "dual" in lowered or "kaksi" in lowered:
        return 2
    if "single" in lowered or "yksi" in lowered:
        return 1
    return parse_watts(text)


def parse_modules(text: str) -> Optional[int]:
    """'Muistin sijoitus (moduulit x koko)' reads '2 x 16 GB' -> 2 modules."""
    match = re.search(r"(\d+)\s*[x×]\s*\d+", text)
    if match:
        return int(match.group(1))
    return parse_watts(text)


def parse_list(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"[,;/]| tai ", text) if part.strip()]


def parse_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- field mapping
#
# canonical field -> candidate labels as they appear in Finnish data sheets.
# Matching is case-insensitive; a candidate may also be a "re:" pattern.

FIELD_MAP: Dict[str, Dict[str, List[str]]] = {
    "gpu": {
        "power_w": ["Tehonkulutus (maks.)", "Virrankulutus (maks.)", "Tehonkulutus", "TDP"],
        "length_mm": ["Pituus", "Tuotteen pituus"],
        "width_mm": ["Leveys"],
        "height_mm": ["Korkeus"],
        "slot_width": ["Korttipaikkojen lukumäärä", "Paksuus"],
        "power_connectors": ["Virransyöttöliitäntä", "Virransyöttöliitännät"],
        "recommended_psu_w": ["Virtalähteen minimikoko", "Järjestelmän virtalähteen vähimmäisteho",
                              "Suositeltu virtalähde"],
        "interface": ["Väylä", "PCI-väylä", "PCI Express -versio"],
        "vram_gb": ["Diskreetti näytönohjainmuisti", "Näytönohjaimen muisti"],
        "memory_type": ["Näytönohjaimen muistityyppi"],
        "graphics_chipset": ["Grafiikkaprosessori"],
        "memory_bus_bit": ["Muistiväylä"],
    },
    "cpu": {
        "tdp_w": ["Thermal Design Power (TDP)", "TDP", "Tehonkulutus (TDP)", "Prosessorin pohjateho"],
        "max_turbo_power_w": ["Enimmäisturboteho", "Prosessorin enimmäisteho"],
        "socket": ["Prosessorin kanta", "Kanta"],
        "memory_types": ["Prosessorin tukemat muistityypit", "Tuetut muistityypit"],
        "cores": ["Prosessorin ytimet", "Ytimien lukumäärä"],
        "threads": ["Prosessorin säikeet", "Säikeiden lukumäärä"],
        "cache_mb": ["Prosessorin välimuisti", "Välimuisti"],
        "base_clock_mhz": ["Prosessorin perustaajuus"],
        "boost_clock_mhz": ["Suorittimen boost-taajuus", "Prosessorin enimmäistaajuus"],
        "memory_channels": ["Muistikanavat"],
        "memory_speed_mhz": ["Prosessorin tukemat muistin kellonopeudet"],
        "integrated_graphics": ["Sisäinen näytönohjain"],
        "cooler_included": ["Jäähdytin sisältyy"],
        "lithography_nm": ["Prosessorin litografia"],
        "pcie_version": ["PCI Express korttipaikan versio"],
    },
    "motherboard": {
        "socket": ["Prosessorin kanta", "Kanta"],
        "chipset": ["Emolevyn piirisarja", "Piirisarja"],
        "form_factor": ["Emolevyn muototekijä", "Muototekijä"],
        "memory_type": ["Tuetut muistityypit", "Muistityyppi"],
        "memory_slots": ["Muistipaikkojen lukumäärä", "Muistipaikkojen määrä", "Muistipaikat"],
        "memory_max_gb": ["Tuettu enimmäismuisti", "Enimmäismuisti"],
        "memory_channels": ["Muistikanavat"],
        "m2_slots": ["re:m\\.2.*(paikkojen|paikat|paikkaa)", "M.2-paikkojen määrä", "M.2-liitäntöjen määrä"],
        "width_mm": ["Tuotteen leveys"],
        "depth_mm": ["Tuotteen syvyys"],
    },
    "memory": {
        "memory_type": ["Muistityyppi", "Sisäisen muistin tyyppi"],
        "capacity_gb": ["Sisäinen muisti", "Sisäisen muistin", "Muistin kapasiteetti", "Kapasiteetti"],
        "modules": ["Muistimoduulien määrä", "Moduulien määrä", "Muistin sijoitus"],
        "speed_mhz": ["Muistin kellotaajuus", "Kellotaajuus"],
        "cas_latency": ["CAS-viive", "CAS-latenssi", "Muistin latenssi", "Latenssi"],
        "form_factor": ["Muistin muoto", "Muototekijä"],
        "voltage_v": ["Muistin jännite", "Jännite"],
        "ecc": ["ECC"],
    },
    "storage": {
        "capacity_gb": ["Kiintolevyn kapasiteetti", "SSD-tallennuskapasiteetti",
                        "SSD-kapasiteetti (Gt)", "Tallennuskapasiteetti", "Kapasiteetti"],
        "interface": ["Käyttöliittymä", "Tallennusväylän nimi", "Liitäntä", "Väylä"],
        "form_factor": ["M.2 SSD:n koko", "SSD-muototekijä", "Kiintolevyn koko", "Muototekijä"],
        "pcie_gen": ["PCI Express -versio"],
        "nvme": ["NVMe"],
        "read_mb_s": ["Lukunopeus"],
        "write_mb_s": ["Kirjoitusnopeus"],
    },
    "psu": {
        "wattage_w": ["Teho", "Virtalähteen teho", "Nimellisteho"],
        "efficiency": ["Tehokkuusluokka", "80 PLUS", "Tehokkuus"],
        "atx_version": ["ATX-versio", "ATX-versio(t)", "ATX versio"],
        "form_factor": ["Muototekijä", "Virtalähteen muoto"],
        "length_mm": ["Pituus"],
        "width_mm": ["Tuotteen leveys"],
        "depth_mm": ["Tuotteen syvyys"],
        "height_mm": ["Tuotteen korkeus"],
        "modular": ["Kaapelointi", "Modulaarinen"],
        "fan_size_mm": ["Tuulettimen halkaisija"],
        "main_connector": ["Emolevyn virtaliitin", "ATX virtaliitin", "ATX-virtaliitin"],
        "pcie_connectors": ["PCI Express-virtaliittimiä (6+2 pin)", "PCI Express -virtaliittimet"],
    },
    "case": {
        "max_gpu_length_mm": ["Näytönohjaimen suurin pituus", "Näytönohjaimen maksimipituus"],
        "max_cooler_height_mm": ["CPU-jäähdyttimen enimmäiskorkeus", "Jäähdyttimen enimmäiskorkeus"],
        "max_psu_length_mm": ["Virtalähteen enimmäispituus"],
        "supported_motherboards": ["Tuetut emolevyt", "Emolevyn muototekijä"],
        "tower_size": ["Kotelo", "Kotelon tyyppi", "Muototekijä"],
        "width_mm": ["Leveys", "Tuotteen leveys"],
        "height_mm": ["Korkeus", "Tuotteen korkeus"],
        "depth_mm": ["Syvyys", "Tuotteen syvyys"],
        "expansion_slots": ["Laajennuspaikkoja", "Laajennuspaikkojen määrä"],
        "color": ["Tuotteen väri"],
        "material": ["Materiaali"],
        "psu_included": ["Virtalähde mukana"],
        "hdd_35_bays": ["3,25\":n laitepaikkojen lukumäärä"],
        "front_usb_c": ["USB 3.2 Gen 2 (3.1 Gen 2) C-tyypin porttien määrä"],
    },
}

PARSERS: Dict[str, Callable[[str], Any]] = {
    "power_w": parse_watts, "tdp_w": parse_watts, "wattage_w": parse_watts,
    "recommended_psu_w": parse_watts, "max_turbo_power_w": parse_watts,
    "length_mm": parse_mm, "width_mm": parse_mm, "height_mm": parse_mm,
    "depth_mm": parse_mm, "max_gpu_length_mm": parse_mm, "max_cooler_height_mm": parse_mm,
    "max_psu_length_mm": parse_mm, "fan_size_mm": parse_mm,
    "base_clock_mhz": parse_mhz, "boost_clock_mhz": parse_mhz, "speed_mhz": parse_mhz,
    "memory_speed_mhz": parse_mhz,
    "cache_mb": parse_mb, "capacity_gb": parse_gb, "memory_max_gb": parse_gb,
    "vram_gb": parse_gb,
    "socket": parse_socket,
    "nvme": parse_bool, "ecc": parse_bool, "psu_included": parse_bool,
    "cooler_included": parse_bool, "integrated_graphics": parse_bool,
    "cores": parse_watts, "threads": parse_watts, "modules": parse_modules,
    "memory_slots": parse_watts, "memory_channels": parse_channels, "m2_slots": parse_watts,
    "slot_width": parse_watts, "expansion_slots": parse_watts, "cas_latency": parse_watts,
    "read_mb_s": parse_watts, "write_mb_s": parse_watts, "memory_bus_bit": parse_watts,
    "lithography_nm": parse_watts, "pcie_connectors": parse_watts, "hdd_35_bays": parse_watts,
    "front_usb_c": parse_watts,
    "supported_motherboards": parse_list, "memory_types": parse_list,
    "power_connectors": parse_list,
    "interface": parse_text, "efficiency": parse_text, "atx_version": parse_text,
    "form_factor": parse_text, "tower_size": parse_text, "chipset": parse_text,
    "memory_type": parse_text, "modular": parse_text, "voltage_v": parse_text,
    "pcie_gen": parse_text, "color": parse_text, "material": parse_text,
    "graphics_chipset": parse_text, "pcie_version": parse_text, "main_connector": parse_text,
}


def match_label(label: str, candidates: Iterable[str]) -> bool:
    lowered = label.strip().lower()
    for candidate in candidates:
        if candidate.startswith("re:"):
            if re.search(candidate[3:], lowered, re.IGNORECASE):
                return True
        elif candidate.lower() == lowered or candidate.lower() in lowered:
            return True
    return False


# --------------------------------------------------------------------------- page reading

def extract_features(html: str) -> Tuple[List[Tuple[str, str]], str]:
    """Return (features, method) from a product page.

    Primary: the embedded JSON array the shop uses to render its own data sheet.
    Fallback: the rendered definition list (<dt>/<dd>), so a markup change does not
    silently produce an empty result.
    """
    unescaped = html_module.unescape(html)
    match = re.search(r'"features"\s*:\s*(\[.*?\])', unescaped, re.DOTALL)
    if match:
        try:
            raw = json.loads(match.group(1))
            pairs = [(str(f.get("name", "")).strip(), str(f.get("value", "")).strip())
                     for f in raw if f.get("name")]
            if pairs:
                return pairs, "embedded_json"
        except json.JSONDecodeError:
            pass

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    pairs: List[Tuple[str, str]] = []
    for term in soup.find_all("dt"):
        value = term.find_next_sibling("dd")
        if value:
            pairs.append((term.get_text(" ", strip=True), value.get_text(" ", strip=True)))
    return pairs, "definition_list" if pairs else "none"


def parse_specs(category: str, features: List[Tuple[str, str]]) -> Tuple[Dict[str, Any], List[str]]:
    """Map (label, value) pairs onto canonical fields. Returns (specs, unmapped labels)."""
    field_map = FIELD_MAP.get(category, {})
    specs: Dict[str, Any] = {}
    unmapped: List[str] = []

    for label, value in features:
        if not label or not value:
            continue
        for field, candidates in field_map.items():
            if field in specs:  # first match wins: data sheets list the primary value first
                continue
            if not match_label(label, candidates):
                continue
            parser = PARSERS.get(field, parse_text)
            parsed = parser(value)
            if parsed in (None, [], ""):
                unmapped.append(f"{label} (unparsable: {value[:40]})")
            else:
                specs[field] = parsed
            break
        else:
            unmapped.append(label)

    return specs, unmapped


# --------------------------------------------------------------------------- run

def iter_listings(raw_dir: Path, categories: Optional[List[str]]) -> List[Dict[str, str]]:
    """Every product URL found in data/raw/*.json, with its category and shop."""
    seen: Dict[str, Dict[str, str]] = {}
    for path in sorted(raw_dir.glob("*.json")):
        if path.name in {"scrape_runs.jsonl"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or "items" not in payload:
            continue
        category = payload.get("category")
        shop = payload.get("shop", "?")
        if category is None or (categories and category not in categories):
            continue
        for item in payload["items"]:
            url = item.get("url")
            if not url or url in seen:
                continue
            seen[url] = {"url": url, "category": category, "name": item.get("name", ""),
                         "external_id": str(item.get("external_id") or ""), "shop": shop}
    return list(seen.values())


def cache_path(url: str, external_id: str, run_date: str) -> Path:
    key = external_id or re.sub(r"\W+", "_", url)[-40:]
    return CACHE_DIR / run_date / f"{key}.html"


def fetch_page(session: requests.Session, url: str, external_id: str, run_date: str,
               force: bool) -> Tuple[str, str]:
    """Return (html, origin). origin is 'cache' when today's copy was reused."""
    path = cache_path(url, external_id, run_date)
    if path.exists() and not force:
        return path.read_text(encoding="utf-8"), "cache"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    text = response.text
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, "network"


def load_store(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
            store.setdefault("items", {})
            return store
        except json.JSONDecodeError:
            pass
    return {"generated_at": date.today().isoformat(),
            "source": "Datatronic product pages (data sheet)",
            "items": {}}


def write_store(path: Path, store: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    store["generated_at"] = date.today().isoformat()
    store["item_count"] = len(store["items"])
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def write_report(out_dir: Path, store: Dict[str, Any]) -> Path:
    items = store["items"]
    by_field: Dict[str, Dict[str, int]] = {}
    unmapped_counts: Dict[str, int] = {}
    per_category_total: Dict[str, int] = {}
    per_category_ok: Dict[str, int] = {}
    failures: List[Tuple[str, str, str]] = []

    for url, entry in items.items():
        category = entry.get("category", "?")
        per_category_total[category] = per_category_total.get(category, 0) + 1
        if entry.get("status") == "ok":
            per_category_ok[category] = per_category_ok.get(category, 0) + 1
        else:
            failures.append((category, entry.get("name", "")[:60], entry.get("error", "?")))
        counts = by_field.setdefault(category, {})
        for field, value in (entry.get("specs") or {}).items():
            if value not in (None, [], ""):
                counts[field] = counts.get(field, 0) + 1
        for label in entry.get("unmapped", []):
            key = f"{category}: {label}"
            unmapped_counts[key] = unmapped_counts.get(key, 0) + 1

    lines: List[str] = []
    lines.append(f"# Product-page data sheet report — {date.today().isoformat()}")
    lines.append("")
    lines.append(f"Fetched **{len(items)}** product pages; **{sum(per_category_ok.values())}** "
                 f"parsed successfully, {len(failures)} failed.")
    lines.append("")
    lines.append("Values here are **parsed from the shop's own data sheet**, not inferred from the "
                 "product name. Unmapped labels are listed below instead of being guessed.")
    lines.append("")

    lines.append("## Coverage per category and field")
    lines.append("")
    lines.append("| Category | Products | Field | Parsed | Coverage |")
    lines.append("|---|---|---|---|---|")
    for category in CATEGORIES:
        total = per_category_total.get(category)
        if not total:
            continue
        for field in FIELD_MAP.get(category, {}):
            found = by_field.get(category, {}).get(field, 0)
            pct = round(100 * found / total)
            status = "✅" if pct >= 80 else ("⚠️" if pct >= 40 else "❌")
            lines.append(f"| {category} | {total} | `{field}` | {found} | {status} {pct}% |")
    lines.append("")

    if unmapped_counts:
        lines.append("## Labels we could not map (top 25)")
        lines.append("")
        lines.append("These are preserved for review — add them to `FIELD_MAP` in `specs.py` "
                     "when they matter for a compatibility rule.")
        lines.append("")
        for key, count in sorted(unmapped_counts.items(), key=lambda kv: -kv[1])[:25]:
            lines.append(f"- {count:>4}× {key}")
        lines.append("")

    if failures:
        lines.append("## Failed pages")
        lines.append("")
        for category, name, error in failures[:20]:
            lines.append(f"- **{category}** `{name}` — {error}")
        lines.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "specs_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract product-page data sheets.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--category", action="append", choices=CATEGORIES,
                        help="repeatable; default is every category")
    parser.add_argument("--limit", type=int, help="stop after N products (smoke test)")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--force", action="store_true", help="refetch even if cached today")
    parser.add_argument("--reparse", action="store_true",
                        help="no network: re-run the field mapper over today's cached HTML")
    parser.add_argument("--status", action="store_true",
                        help="print the coverage table from specs.json and exit")
    parser.add_argument("--checkpoint-every", type=int, default=25,
                        help="write specs.json every N products so a long run is not lost")
    args = parser.parse_args()

    if args.status:
        store = load_store(args.out / "specs.json")
        items = store.get("items", {})
        if not items:
            print("specs.json is empty — run the extractor first", file=sys.stderr)
            return 1
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for entry in items.values():
            by_category.setdefault(entry.get("category", "?"), []).append(entry)
        print(f"specs.json — {len(items)} products ({store.get('generated_at')})")
        for category in CATEGORIES:
            entries = by_category.get(category)
            if not entries:
                continue
            print(f"\n[{category}] {len(entries)} products, "
                  f"{sum(1 for e in entries if e.get('status') == 'ok')} parsed ok")
            for field in FIELD_MAP.get(category, {}):
                found = sum(1 for e in entries if (e.get("specs") or {}).get(field) is not None)
                pct = round(100 * found / len(entries))
                mark = "  " if pct == 0 else ("!!" if pct < 40 else "ok")
                print(f"   {mark} {field:24} {found:>3}/{len(entries):<3} {pct:>3}%")
        print(f"\nreport: {write_report(args.out, store)}")
        return 0

    listings = iter_listings(args.raw_dir, args.category)
    if not listings:
        print("no listings found — run scraper/scrape.py first", file=sys.stderr)
        return 1
    if args.limit:
        listings = listings[:args.limit]

    store_path = args.out / "specs.json"
    store = load_store(store_path)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT,
                            "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8"})
    run_date = date.today().isoformat()

    done = parsed_ok = skipped = failed = no_cache = 0
    started = time.monotonic()
    print(f"{len(listings)} products to read (cache: {CACHE_DIR / run_date})", flush=True)

    for listing in listings:
        url = listing["url"]
        existing = store["items"].get(url)

        if args.reparse:
            # Offline mode: re-run the field mapper over today's cached HTML,
            # so fixing FIELD_MAP costs zero requests.
            cached = cache_path(url, listing["external_id"], run_date)
            if not cached.exists():
                no_cache += 1
                continue
            html, origin = cached.read_text(encoding="utf-8"), "cache"
        else:
            # Incremental: a successfully parsed product is not fetched again today.
            if existing and existing.get("status") == "ok" and not args.force \
                    and str(existing.get("fetched_at", "")).startswith(run_date):
                skipped += 1
                continue
            try:
                html, origin = fetch_page(session, url, listing["external_id"], run_date, args.force)
            except (requests.RequestException, OSError) as exc:
                failed += 1
                store["items"][url] = {
                    "category": listing["category"], "name": listing["name"],
                    "external_id": listing["external_id"], "shop": listing["shop"],
                    "specs": {}, "status": "failed", "error": str(exc)[:120],
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source": "product_page",
                }
                print(f"  [{listing['category']:11}] FAILED {url} — {exc}", file=sys.stderr, flush=True)
                continue

        try:
            features, method = extract_features(html)
            specs, unmapped = parse_specs(listing["category"], features)
            store["items"][url] = {
                "category": listing["category"],
                "name": listing["name"],
                "external_id": listing["external_id"],
                "shop": listing["shop"],
                "specs": specs,
                "spec_count": len(specs),
                "feature_count": len(features),
                "extraction": method,
                "unmapped": unmapped,
                "status": "ok" if features else "empty",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "product_page",
                "origin": origin,
            }
            parsed_ok += 1
            print(f"  [{listing['category']:11}] {len(specs):>2} specs / {len(features):>2} fields "
                  f"· {listing['name'][:52]}", flush=True)
            done += 1
        except Exception as exc:  # parsing must never kill a long run
            failed += 1
            store["items"][url] = {
                "category": listing["category"], "name": listing["name"],
                "external_id": listing["external_id"], "shop": listing["shop"],
                "specs": {}, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:120],
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "product_page",
            }
            print(f"  [{listing['category']:11}] PARSE FAILED {listing['name'][:40]} — {exc}",
                  file=sys.stderr, flush=True)

        if done and done % args.checkpoint_every == 0:
            write_store(store_path, store)
            elapsed = time.monotonic() - started
            print(f"  … checkpoint: {done} fetched, {parsed_ok} parsed, {skipped} skipped, "
                  f"{failed} failed ({elapsed/60:.1f} min)", flush=True)
        if not args.reparse:
            time.sleep(args.delay)

    write_store(store_path, store)
    report = write_report(args.out, store)

    print(f"\nfetched {done} pages ({skipped} already done today, {no_cache} not in cache, "
          f"{failed} failed)")
    print(f"parsed specs for {parsed_ok} products → {store_path}")
    print(f"report → {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
