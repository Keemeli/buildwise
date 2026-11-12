"""Proshop GPU specification groups and exact labels; no requests or storage."""
import re
from bs4 import BeautifulSoup

from scraper.common.specifications import (
    PARSERS, SpecificationFieldParser, parse_gb, parse_mm,
)
from scraper.retailers.contracts import UnsupportedCategoryError

FIELD_MAP = {
    'gpu': {
        'graphics_chipset': ['Yleistä/Grafiikkamoottori'],
        'interface': ['Yleistä/Väylätyyppi'],
        'vram_gb': ['Muisti/Koko'],
        'memory_type': ['Muisti/Tekniikka'],
        'memory_bus_bit': ['Muisti/Väyläleveys'],
        'recommended_psu_w': ['Järjestelmävaatimukset/Vaadittava virtalähde'],
        # These GPU axes are corroborated by the two saved product summaries.
        'length_mm': ['Muuta/Syvyys'],
        'width_mm': ['Muuta/Leveys'],
        'height_mm': ['Muuta/Korkeus'],
        # A server-GPU sample publishes operating consumption explicitly.
        # The remaining fields lack unambiguous standalone values.
        'power_w': ['Muuta/Virran kulutus (toiminnassa)'],
        'slot_width': [],
        'power_connectors': [],
    },
}


def _dimension(value):
    """Accept a single measurement, never a range or composite shipping size."""
    if not re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*(?:mm|cm|m)\s*', value, re.I):
        return None
    parsed = parse_mm(value)
    return parsed if parsed is not None and parsed > 0 else None


def _gpu_memory(value):
    """Normalise Finnish Gt/Tt units before the shared capacity conversion."""
    if not re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*(?:GB|Gt|TB|Tt)\s*', value, re.I):
        return None
    value = re.sub(r'Gt\b', 'GB', value, flags=re.I)
    value = re.sub(r'Tt\b', 'TB', value, flags=re.I)
    parsed = parse_gb(value)
    return parsed if parsed is not None and parsed > 0 else None


class ProshopSpecParser(SpecificationFieldParser):
    """Read the primary data sheet, preserving section/label context.

    General summaries, accessories and shipping dimensions cannot supply GPU
    dimensions. Unsupported or ambiguous fields remain absent from parsed values;
    the shared worker represents the supported unknown fields as null.
    """
    def __init__(self, field_map=None, parsers=None, category_parsers=None):
        if parsers is None:
            parsers = {**PARSERS, 'vram_gb': _gpu_memory,
                       **dict.fromkeys(('length_mm', 'width_mm', 'height_mm'), _dimension)}
        super().__init__(FIELD_MAP if field_map is None else field_map, parsers, category_parsers)

    def matches(self, label, candidates):
        return any(label.casefold() == candidate.casefold() for candidate in candidates)

    def extract_features(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        container = soup.select_one('#accordionPanel_specs #specItemsAccordion')
        if container is None:
            return [], 'none'
        features, section = [], ''
        for row in container.find_all(recursive=False):
            if 'sectionTitle' in row.get('class', []):
                section = row.get_text(' ', strip=True).rstrip(':')
                continue
            label = row.select_one('.specItemTitle')
            value = row.select_one('.specItemValue')
            if section and label is not None and value is not None:
                label_text = label.get_text(' ', strip=True).rstrip(':')
                features.append((f'{section}/{label_text}', value.get_text(' ', strip=True)))
        return features, 'grouped_specification_rows' if features else 'none'

    def parse_specs(self, category, features):
        if category not in self.field_map:
            raise UnsupportedCategoryError(f'Proshop has no specification mapping for {category}')
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
