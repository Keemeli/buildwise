"""Canonical specification values and label mapping; no retailer HTML or I/O."""
from __future__ import annotations
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

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


class SpecificationFieldParser:
    """Map retailer labels using shared canonical conversions."""
    def __init__(self, field_map, parsers=None, category_parsers=None):
        self.field_map = field_map
        self.parsers = PARSERS if parsers is None else parsers
        self.category_parsers = PARSERS_BY_CATEGORY if category_parsers is None else category_parsers

    def matches(self, label, candidates):
        return match_label(label, candidates)

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
                if not self.matches(label, candidates):
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

# Canonical report fields, independent of retailer labels.
SPECIFICATION_FIELDS = {'gpu': ('power_w',
         'length_mm',
         'width_mm',
         'height_mm',
         'slot_width',
         'power_connectors',
         'recommended_psu_w',
         'interface',
         'vram_gb',
         'memory_type',
         'graphics_chipset',
         'memory_bus_bit'),
 'cpu': ('tdp_w',
         'max_turbo_power_w',
         'socket',
         'memory_types',
         'cores',
         'threads',
         'cache_mb',
         'base_clock_mhz',
         'boost_clock_mhz',
         'memory_channels',
         'memory_speed_mhz',
         'integrated_graphics',
         'cooler_included',
         'lithography_nm',
         'pcie_version'),
 'motherboard': ('socket',
                 'chipset',
                 'form_factor',
                 'memory_type',
                 'memory_slots',
                 'memory_max_gb',
                 'memory_channels',
                 'm2_slots',
                 'width_mm',
                 'depth_mm'),
 'memory': ('memory_type',
            'capacity_gb',
            'modules',
            'speed_mhz',
            'cas_latency',
            'form_factor',
            'voltage_v',
            'ecc'),
 'storage': ('capacity_gb',
             'interface',
             'form_factor',
             'pcie_gen',
             'nvme',
             'read_mb_s',
             'write_mb_s'),
 'psu': ('wattage_w',
         'efficiency',
         'atx_version',
         'form_factor',
         'length_mm',
         'width_mm',
         'depth_mm',
         'height_mm',
         'modular',
         'fan_size_mm',
         'main_connector',
         'pcie_connectors'),
 'case': ('max_gpu_length_mm',
          'max_cooler_height_mm',
          'max_psu_length_mm',
          'supported_motherboards',
          'tower_size',
          'width_mm',
          'height_mm',
          'depth_mm',
          'expansion_slots',
          'color',
          'material',
          'psu_included',
          'hdd_35_bays',
          'front_usb_c')}
