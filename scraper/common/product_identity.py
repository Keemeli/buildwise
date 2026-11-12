"""Validated product identifiers and source evidence; no product matching or I/O."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

FIELDS = ('gtin', 'manufacturer_part_number', 'brand')
PLACEHOLDERS = {'-', 'n/a', 'unknown', 'not available', 'none'}


def normalise_identifier(field, raw):
    """Return (canonical text, error). A checksum does not prove GS1 registration."""
    if not isinstance(raw, str):
        return None, 'not_text'
    value = ' '.join(raw.split())
    if not value or value.casefold() in PLACEHOLDERS:
        return None, 'missing_or_placeholder'
    if field == 'gtin':
        value = re.sub(r'\s+', '', value)
        if not re.fullmatch(r'(?:[0-9]{8}|[0-9]{12,14})', value):
            return None, 'invalid_length_or_characters'
        if set(value) == {'0'}:
            return None, 'all_zero_placeholder'
        total = sum(int(digit) * (1 if index % 2 == 0 else 3)
                    for index, digit in enumerate(reversed(value)))
        if total % 10:
            return None, 'invalid_check_digit'
        return value.zfill(14), None
    if field not in FIELDS:
        raise ValueError(f'unknown identity field: {field}')
    return value, None


@dataclass(frozen=True)
class IdentifierEvidence:
    field: str
    raw_value: object
    source: str
    value: str | None
    error: str | None = None

    def __post_init__(self):
        if self.field not in FIELDS or not isinstance(self.source, str) or not self.source.strip():
            raise ValueError('identifier evidence needs a known field and source')
        if self.value is not None and normalise_identifier(self.field, self.value) != (self.value, None):
            raise ValueError('identifier evidence values must be canonical text or null')


@dataclass(frozen=True)
class ProductIdentity:
    gtin: str | None = None
    manufacturer_part_number: str | None = None
    brand: str | None = None
    evidence: tuple[IdentifierEvidence, ...] = ()
    issues: tuple[str, ...] = ()

    def __post_init__(self):
        if not all(isinstance(item, IdentifierEvidence) for item in self.evidence):
            raise ValueError('identity evidence must contain IdentifierEvidence records')
        if not all(isinstance(issue, str) and issue for issue in self.issues):
            raise ValueError('identity issues must contain nonempty text')
        for field in FIELDS:
            value = getattr(self, field)
            if value is not None and normalise_identifier(field, value) != (value, None):
                raise ValueError(f'{field} must be canonical validated text or null')

    @classmethod
    def from_candidates(cls, candidates, issues=()):
        evidence, values, issues = [], {field: set() for field in FIELDS}, list(issues)
        for field, raw, source in candidates:
            if field not in FIELDS:
                raise ValueError(f'unknown identity field: {field}')
            value, error = normalise_identifier(field, raw)
            evidence.append(IdentifierEvidence(field, raw, source, value, error))
            if error:
                issues.append(f'{field}:{error}')
            else:
                values[field].add(value)
        fields = {}
        for field, candidates in values.items():
            fields[field] = next(iter(candidates)) if len(candidates) == 1 else None
            if len(candidates) > 1:
                issues.append(f'{field}:conflicting_values')
        return cls(**fields, evidence=tuple(evidence), issues=tuple(dict.fromkeys(issues)))

    @classmethod
    def from_dict(cls, value):
        if value is None or isinstance(value, cls):
            return value
        return cls(**{field: value.get(field) for field in FIELDS},
                   evidence=tuple(IdentifierEvidence(**item) for item in value.get('evidence', [])),
                   issues=tuple(value.get('issues', [])))

    def to_dict(self):
        return asdict(self)
