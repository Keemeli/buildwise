"""Datatronic data-sheet value conversion, field maps and HTML parsing.

This module performs no file reads, network requests or run orchestration.
"""
from __future__ import annotations
import html as html_module
import json
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

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


_DDR_RE = re.compile(r"(G?DDR\d)", re.IGNORECASE)


def parse_memory_type(text: str):
    """'DDR4-SDRAM' -> 'DDR4' ; 'GDDR7' -> 'GDDR7' ; 'DDR4-SDRAM, DDR5-SDRAM' -> ['DDR4', 'DDR5'].

    Shops and data sheets spell the same generation in several ways ('DDR4',
    'DDR4-SDRAM', 'DDR4 SDRAM') while product names use the bare generation. Keeping
    the raw wording made two compatible parts look incompatible (DDR4 vs DDR4-SDRAM),
    so the canonical value is the generation. A board that supports two generations
    keeps both, as a list, because that is real information.
    """
    tokens: List[str] = []
    for match in _DDR_RE.finditer(text or ""):
        token = match.group(1).upper()
        if token not in tokens:
            tokens.append(token)
    if not tokens:
        return None
    return tokens[0] if len(tokens) == 1 else tokens


def parse_storage_form_factor(text: str) -> Optional[str]:
    """'M.2', '2280 (22 x 80 mm)', 'M.2 2280' -> 'M.2 2280' ; '2.5"' -> '2.5"' ; '3,5"' -> '3.5"'.

    The same physical size is written three ways across data sheets, which would split
    a UI filter into three near-duplicate buckets.
    """
    lowered = (text or "").lower().replace("”", '"').replace("″", '"')
    code = re.search(r"\b(2230|2242|2260|2280|22110)\b", lowered)
    if "m.2" in lowered or "m2" in lowered or code:
        return f"M.2 {code.group(1)}" if code else "M.2"
    size = re.search(r"(\d(?:[.,]\d)?)\s*(?:\"|''|tuumaa)", lowered)
    if size:
        return f"{size.group(1).replace(',', '.')}\""
    return parse_text(text)


def parse_storage_interface(text: str) -> Optional[str]:
    """'Serial ATA III' -> 'SATA III' ; 'SATA' -> 'SATA' ; 'PCI Express 4.0' stays as is.

    Two spellings of the same bus would make a filter show two buckets for one thing.
    A bare 'SATA' keeps its own value on purpose: the generation really is unknown.
    """
    cleaned = parse_text(text)
    lowered = cleaned.lower()
    if "sata" in lowered or "serial ata" in lowered:
        generation = re.search(r"\b(I{1,3})\b", cleaned)
        return f"SATA {generation.group(1).upper()}" if generation else "SATA"
    return cleaned


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
    "supported_motherboards": parse_list,
    "power_connectors": parse_list,
    "interface": parse_text, "efficiency": parse_text, "atx_version": parse_text,
    "form_factor": parse_text, "tower_size": parse_text, "chipset": parse_text,
    "memory_type": parse_memory_type, "memory_types": parse_memory_type,
    "modular": parse_text, "voltage_v": parse_text,
    "pcie_gen": parse_text, "color": parse_text, "material": parse_text,
    "graphics_chipset": parse_text, "pcie_version": parse_text, "main_connector": parse_text,
}

# Some fields share a name across categories but need a category-specific value shape:
# a storage device's form factor ("M.2 2280") is not a motherboard's ("mikro ATX").
# Anything listed here wins over the generic parser above.
PARSERS_BY_CATEGORY: Dict[Tuple[str, str], Callable[[str], Any]] = {
    ("storage", "form_factor"): parse_storage_form_factor,
    ("storage", "interface"): parse_storage_interface,
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


class DatatronicSpecParser:
    """Translate Datatronic data-sheet markup and labels into canonical fields.

    Field maps and value parsers belong to this instance so another mapping can
    be tested without changing module-level configuration.
    """

    def __init__(self, field_map=None, parsers=None, category_parsers=None):
        self.field_map = FIELD_MAP if field_map is None else field_map
        self.parsers = PARSERS if parsers is None else parsers
        self.category_parsers = PARSERS_BY_CATEGORY if category_parsers is None else category_parsers

    def extract_features(self, html: str) -> Tuple[List[Tuple[str, str]], str]:
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

    def parse_specs(self, category: str, features: List[Tuple[str, str]]) -> Tuple[Dict[str, Any], List[str]]:
        """Map (label, value) pairs onto canonical fields. Returns (specs, unmapped labels)."""
        field_map = self.field_map.get(category, {})
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
                parser = self.category_parsers.get((category, field), self.parsers.get(field, parse_text))
                parsed = parser(value)
                if parsed in (None, [], ""):
                    unmapped.append(f"{label} (unparsable: {value[:40]})")
                else:
                    specs[field] = parsed
                break
            else:
                unmapped.append(label)

        return specs, unmapped


def extract_features(html: str) -> Tuple[List[Tuple[str, str]], str]:
    """Compatibility function; delegate to DatatronicSpecParser."""
    return DatatronicSpecParser().extract_features(html)


def parse_specs(category: str, features: List[Tuple[str, str]]) -> Tuple[Dict[str, Any], List[str]]:
    """Compatibility function; delegate to DatatronicSpecParser."""
    return DatatronicSpecParser().parse_specs(category, features)


