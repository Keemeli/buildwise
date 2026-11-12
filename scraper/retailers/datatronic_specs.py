"""Datatronic data-sheet labels and HTML extraction; values use shared parsers."""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Tuple
from scraper.common.specifications import (
    to_number, parse_watts, parse_mm, parse_mhz, parse_mb, parse_gb,
    parse_socket, parse_bool, parse_channels, parse_modules, parse_memory_type,
    parse_storage_form_factor, parse_storage_interface, parse_list, parse_text,
    PARSERS, PARSERS_BY_CATEGORY, match_label, SpecificationFieldParser,
)

# --------------------------------------------------------------------------- field mapping
#
# canonical field -> candidate labels as they appear in Finnish data sheets.
# Matching is case-insensitive; a candidate may also be a "re:" pattern.

FIELD_MAP: Dict[str, Dict[str, List[str]]] = {
    "gpu": {
        "power_w": ["Tehonkulutus (maks.)", "Virrankulutus (maks.)", "Tehonkulutus", "TDP", "Thermal Design Power (TDP)"],
        "length_mm": ["Pituus", "Tuotteen pituus"],
        # This primary GPU sheet publishes depth as card thickness; its 50 mm
        # value is corroborated by the saved Proshop sheet. Package axes are
        # separate labels and must never supply card measurements.
        "width_mm": ["Leveys", "Tuotteen leveys", "Tuotteen syvyys"],
        "height_mm": ["Korkeus", "Tuotteen korkeus"],
        "slot_width": ["Korttipaikkojen lukumäärä", "Laajennuspaikkoja"],
        "power_connectors": ["Virransyöttöliitäntä", "Virransyöttöliitännät", "Lisävirran liittimet"],
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

# --------------------------------------------------------------------------- page reading


def _gpu_dimension(value):
    """One explicit, positive measurement; ranges and composite axes stay unknown."""
    if not re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*(?:mm|cm|m)\s*', value, re.I):
        return None
    number = parse_mm(value)
    return number if number is not None and number > 0 else None


class _GpuFieldParser(SpecificationFieldParser):
    """Exact GPU labels and agreement across aliases, without first-value guesses."""
    def matches(self, label, candidates):
        label = ' '.join(label.split()).casefold()
        return any(re.fullmatch(candidate[3:], label, re.I) if candidate.startswith('re:')
                   else label == ' '.join(candidate.split()).casefold()
                   for candidate in candidates)

    def parse_specs(self, category, features):
        candidates, unmapped = {}, []
        for feature in features:
            parsed, unknown = super().parse_specs(category, [feature])
            unmapped.extend(unknown)
            for field, value in parsed.items():
                candidates.setdefault(field, []).append(value)
        specs = {}
        for field, values in candidates.items():
            if all(value == values[0] for value in values):
                specs[field] = values[0]
            else:
                unmapped.append(f'{field} (conflicting values)')
        return specs, unmapped


class DatatronicSpecParser(SpecificationFieldParser):
    """Translate Datatronic data-sheet markup and labels into canonical fields.

    Field maps and value parsers belong to this instance so another mapping can
    be tested without changing module-level configuration.
    """

    def __init__(self, field_map=None, parsers=None, category_parsers=None):
        super().__init__(FIELD_MAP if field_map is None else field_map, parsers, category_parsers)
        gpu_parsers = dict(self.parsers)
        if parsers is None:
            gpu_parsers.update(dict.fromkeys(('length_mm', 'width_mm', 'height_mm'), _gpu_dimension))
        self.gpu_parser = _GpuFieldParser(self.field_map, gpu_parsers, self.category_parsers)

    def parse_specs(self, category, features):
        if category == 'gpu':
            return self.gpu_parser.parse_specs(category, features)
        return super().parse_specs(category, features)

    @staticmethod
    def _feature_pairs(raw):
        if not isinstance(raw, list):
            return []
        return [(str(item['name']).strip(), str(item.get('value', '')).strip())
                for item in raw if isinstance(item, dict) and item.get('name')]

    def extract_features(self, html: str) -> Tuple[List[Tuple[str, str]], str]:
        """Prefer the primary product JSON; fall back to its rendered data sheet.

        Standalone JSON scripts and unscoped definition lists remain readable for
        historical cache snippets that have no primary product container.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one('#product-details')
        if container is not None:
            try:
                data = json.loads(container.get('data-product') or '{}')
                pairs = self._feature_pairs(data.get('features')) if isinstance(data, dict) else []
            except (ValueError, TypeError):
                pairs = []
            if pairs:
                return pairs, "embedded_json"
        else:
            # Compatibility with old saved extracts; do not scan unrelated
            # scripts when a primary product container is available.
            sources = []
            for script in soup.find_all('script'):
                try:
                    data = json.loads(script.get_text())
                except (ValueError, TypeError):
                    continue
                pairs = self._feature_pairs(data.get('features')) if isinstance(data, dict) else []
                if pairs:
                    sources.append(pairs)
            if len(sources) == 1:
                return sources[0], "embedded_json"
        pairs = []
        for term in (container if container is not None else soup).find_all("dt"):
            value = term.find_next_sibling("dd")
            if value:
                pairs.append((term.get_text(" ", strip=True), value.get_text(" ", strip=True)))
        return pairs, "definition_list" if pairs else "none"


def extract_features(html: str) -> Tuple[List[Tuple[str, str]], str]:
    """Compatibility function; delegate to DatatronicSpecParser."""
    return DatatronicSpecParser().extract_features(html)


def parse_specs(category: str, features: List[Tuple[str, str]]) -> Tuple[Dict[str, Any], List[str]]:
    """Compatibility function; delegate to DatatronicSpecParser."""
    return DatatronicSpecParser().parse_specs(category, features)


