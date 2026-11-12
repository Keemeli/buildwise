"""Conservative GPU vocabulary resolution, preserving published source values."""
import json
import re
from collections import Counter


class SpecificationValueResolver:
    """Reconcile known spelling differences without discarding hardware details.

    Unsupported wording keeps its original value and requires exact agreement.
    Missing PCIe generation/lanes are unknown, not evidence against known values.
    """

    FIELDS = frozenset(('graphics_chipset', 'interface', 'power_connectors'))

    @classmethod
    def supports(cls, category, field):
        return category == 'gpu' and field in cls.FIELDS

    @staticmethod
    def _chipset(value):
        if not isinstance(value, str):
            return value
        text = ' '.join(value.split())
        match = re.fullmatch(r'(?:NVIDIA\s+)?GeForce\s+(RTX|GTX|GT|MX)\s*(\d{3,4})(?:\s*(Ti))?(?:\s*(SUPER))?', text, re.I)
        if match:
            family, model, ti, super_ = match.groups()
            return ' '.join(part for part in ('NVIDIA GeForce', family.upper(), model,
                                              'Ti' if ti else '', 'SUPER' if super_ else '') if part)
        match = re.fullmatch(r'(?:AMD\s+)?Radeon\s+RX\s*(\d{3,4})(?:\s*(XTX|XT|GRE))?', text, re.I)
        if match:
            return f'AMD Radeon RX {match[1]}' + (f' {match[2].upper()}' if match[2] else '')
        match = re.fullmatch(r'(?:Intel\s+)?Arc\s+([AB])\s*(\d{3})', text, re.I)
        if match:
            return f'Intel Arc {match[1].upper()}{match[2]}'
        return value

    @staticmethod
    def _pcie(value):
        if not isinstance(value, str):
            return None
        match = re.fullmatch(r'(?:PCI\s+Express|PCI[- ]?E)\s*(.*)', value.strip(), re.I)
        if not match:
            return None
        remainder = ' '.join(match[1].split())
        generation = r'([1-9][0-9]?(?:[.,][0-9])?)'
        lanes = r'x\s*(1|2|4|8|16|32)'
        if not remainder:
            return None, None
        match = re.fullmatch(generation + r'(?:\s+' + lanes + r')?', remainder, re.I)
        if match:
            version, width = match.groups()
        else:
            match = re.fullmatch(lanes + r'(?:\s+' + generation + r')?', remainder, re.I)
            if not match:
                return None
            width, version = match.groups()
        version = version.replace(',', '.') if version else None
        if version and '.' not in version:
            version += '.0'
        return version, int(width) if width else None

    @staticmethod
    def _pcie_text(attributes):
        version, width = attributes
        return 'PCI Express' + (f' {version}' if version else '') + (f' x{width}' if width else '')

    @staticmethod
    def _connectors(value):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return value
        counts, unknown = Counter(), []
        for item in value:
            match = re.fullmatch(r'\s*([1-9][0-9]*)\s*[x×]\s*(\d+(?:\s*\+\s*\d+)?)\s*[- ]?pin\s*', item, re.I)
            if match:
                pins = re.sub(r'\s+', '', match[2])
                counts[pins] += int(match[1])
            else:
                unknown.append(item)
        # Unknown connector types and duplicate entries remain explicit. An
        # uncounted "16-pin" never silently becomes "1 x 16-pin".
        return sorted([f'{count} x {pins}-pin' for pins, count in counts.items()] + unknown)

    def canonical(self, category, field, value):
        if not self.supports(category, field):
            return value
        if field == 'graphics_chipset':
            return self._chipset(value)
        if field == 'power_connectors':
            return self._connectors(value)
        parsed = self._pcie(value)
        return self._pcie_text(parsed) if parsed is not None else value

    def resolve(self, category, field, observations):
        """Return (resolved value, sorted source evidence, conflict flag)."""
        evidence = [dict(item) for item in observations]
        if self.supports(category, field):
            evidence = [{**item, 'canonical_value': self.canonical(category, field, item['value'])}
                        for item in observations]
        evidence.sort(key=lambda item: json.dumps(item, sort_keys=True))
        if not evidence:
            return None, evidence, False
        if category == 'gpu' and field == 'interface':
            attributes = [self._pcie(item['value']) for item in evidence]
            if all(item is not None for item in attributes):
                versions = {item[0] for item in attributes if item[0] is not None}
                widths = {item[1] for item in attributes if item[1] is not None}
                if len(versions) > 1 or len(widths) > 1:
                    return None, evidence, True
                return self._pcie_text((next(iter(versions), None), next(iter(widths), None))), evidence, False
        values = {json.dumps(item.get('canonical_value', item['value']), sort_keys=True) for item in evidence}
        return (json.loads(next(iter(values))), evidence, False) if len(values) == 1 else (None, evidence, True)
