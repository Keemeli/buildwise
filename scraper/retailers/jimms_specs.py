"""Jimms specification labels and conservative product-description extraction."""
import re
from bs4 import BeautifulSoup
from scraper.common.specifications import SpecificationFieldParser

FIELD_MAP = {
    'gpu': {
        'graphics_chipset': ['GPU', 'Grafiikkaprosessori'],
        'vram_gb': ['Muisti/Määrä', 'Muistin määrä', 'Näytönohjaimen muisti', 'Näyttömuisti'],
        'memory_type': ['Muistityyppi', 'Näytönohjaimen muistityyppi'],
        'memory_bus_bit': ['Muistiväylä', 'Muisti/Muistiväylä'],
        'recommended_psu_w': ['Virtalähteen suosituskoko', 'Suositeltu virtalähteen koko', 'Suositeltu virtalähde'],
        'power_w': ['Tehonkulutus', 'Tehonkulutus (maks.)', 'TDP', 'Virrankulutus'],
        'power_connectors': ['Virtaliitännät', 'Virransyöttöliitännät', 'Virtaliitin'],
        'interface': ['Väylä', 'Väyläliitäntä'],
        'length_mm': ['Pituus'], 'width_mm': ['Leveys'], 'height_mm': ['Korkeus'],
        'slot_width': ['Korttipaikkojen lukumäärä'],
    },
    'cpu': {
        'socket': ['Kanta', 'Prosessorikanta', 'Prosessorin kanta'],
        'tdp_w': ['TDP', 'Tehonkulutus (TDP)', 'Thermal Design Power (TDP)'],
        'max_turbo_power_w': ['Enimmäisturboteho', 'Prosessorin enimmäisteho'],
        'cores': ['Ytimet', 'Ytimien määrä', 'Ytimien lukumäärä'],
        'threads': ['Säikeet', 'Säikeiden määrä', 'Säikeiden lukumäärä'],
        'cache_mb': ['Välimuisti', 'L3-välimuisti'],
        'base_clock_mhz': ['Peruskellotaajuus', 'Perustaajuus'],
        'boost_clock_mhz': ['Boost-kellotaajuus', 'Turbo-kellotaajuus'],
        'memory_types': ['Tuetut muistityypit'],
        'memory_channels': ['Muistikanavat'],
        'memory_speed_mhz': ['Tuettu muistinopeus'],
        'integrated_graphics': ['Integroitu näytönohjain', 'Sisäinen näytönohjain'],
        'cooler_included': ['Jäähdytin sisältyy'],
        'lithography_nm': ['Valmistusprosessi'],
        'pcie_version': ['PCI Express -versio'],
    },
}


class JimmsSpecParser(SpecificationFieldParser):
    """Read labelled fields only; marketing prose and product names are excluded."""
    def __init__(self, field_map=None, parsers=None, category_parsers=None):
        super().__init__(FIELD_MAP if field_map is None else field_map, parsers, category_parsers)

    def matches(self, label, candidates):
        return any(label.strip().casefold() == candidate.casefold() for candidate in candidates)

    def extract_features(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        container = soup.select_one('#description [itemprop="description"]') or soup.select_one('#description')
        if container is None:
            return [], 'none'
        pairs = []
        for row in container.select('tr'):
            cells = row.find_all(['th', 'td'], recursive=False)
            if len(cells) == 2:
                pairs.append(tuple(cell.get_text(' ', strip=True).rstrip(':') for cell in cells))
        for term in container.select('dt'):
            value = term.find_next_sibling('dd')
            if value is not None:
                pairs.append((term.get_text(' ', strip=True).rstrip(':'), value.get_text(' ', strip=True)))
        if pairs:
            return pairs, 'description_table'
        # Keep explicit section boundaries and <br> lines from the saved markup.
        text = container.get_text('\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        marker = next((index for index, line in enumerate(lines)
                       if line.casefold().rstrip(':').strip() == 'tekniset tiedot'), None)
        if marker is not None:
            lines = lines[marker + 1:]
        # Bold labels can be separate text nodes from their ': value' text.
        joined, index = [], 0
        while index < len(lines):
            if index + 1 < len(lines) and lines[index + 1].startswith(':') and lines[index + 1][1:].strip():
                joined.append(lines[index] + lines[index + 1])
                index += 2
            else:
                joined.append(lines[index])
                index += 1
        lines = joined
        section = ''
        for line in lines:
            if line in {'Muisti', 'GPU', 'Muuta', 'Prosessori', 'Liitännät'}:
                section = line
                continue
            match = re.fullmatch(r'([^:]{1,80}):\s*(.+)', line)
            if match:
                label, value = match.groups()
                if section == 'Muisti' and label.strip() in {'Määrä', 'Muistiväylä'}:
                    label = f'Muisti/{label.strip()}'
                pairs.append((label.strip(), value.strip()))
        return pairs, 'description_labels' if pairs else 'none'

    def parse_specs(self, category, features):
        expanded = list(features)
        if category == 'gpu':
            for label, value in features:
                if label in {'Muisti/Määrä', 'Muistin määrä', 'Näytönohjaimen muisti', 'Näyttömuisti'}:
                    expanded.append(('Näytönohjaimen muistityyppi', value))
                # Interpret axes only when their order is explicitly published.
                if label == 'Mitat (PxLxK)':
                    match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*mm', value, re.I)
                    if match:
                        expanded.extend(zip(('Pituus', 'Leveys', 'Korkeus'),
                                            (number + ' mm' for number in match.groups())))
        # Check canonical fields too: two different aliases may contradict.
        candidates, unmapped = {}, []
        for feature in expanded:
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
