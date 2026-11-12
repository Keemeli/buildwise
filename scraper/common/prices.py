"""BuildWise — exact conversion of retailer prices into integer euro cents."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re


def parse_price_cents(text: str) -> int | None:
    """'1735.00' / '1 735,00 €' -> 173500; invalid values stay unknown.

    Supports decimal commas and points, but deliberately rejects ambiguous
    mixed separators and values with more than two decimal places.
    """
    value = re.sub(r"\s+", "", text or "").replace("€", "")
    value = re.sub(r"EUR$", "", value, flags=re.I)
    if not re.fullmatch(r"\d+(?:[.,]\d{1,2})?", value):
        return None
    try:
        amount = Decimal(value.replace(",", "."))
        return int(amount * 100) if amount > 0 else None
    except InvalidOperation:
        return None
