"""BuildWise — one raw observation contract for every retailer.

A document describes one fetched source response. Category responses may contain
many products; product responses contain one. HTML references are always relative
to the configured data directory, including when --data-dir points outside the repo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from scraper.config import CATEGORIES

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class RawProduct:
    """Shared item shape. Retailer record ID and SKU have separate meanings.

    external_id is the retailer's internal product ID, stored as text.
    retailer_sku is its displayed SKU/model code; neither is a BuildWise ID."""

    name: str
    price_cents: int | None
    url: str
    external_id: str | None = None
    extraction: str | None = None
    retailer_sku: str | None = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("raw product needs a name")
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("raw product needs a URL")
        if self.price_cents is not None and (type(self.price_cents) is not int or self.price_cents < 0):
            raise ValueError("price_cents must be a non-negative integer or null")
        for value in (self.external_id, self.extraction, self.retailer_sku):
            if value is not None and not isinstance(value, str):
                raise ValueError("external_id, extraction and retailer_sku must be strings or null")

    @classmethod
    def from_item(cls, item: dict, extraction: str | None = None) -> RawProduct:
        """Adapt parser results without persisting retailer-specific extra keys."""
        external_id = item.get("external_id")
        return cls(name=item.get("name"), price_cents=item.get("price_cents"),
                   url=item.get("url"), external_id=str(external_id) if external_id is not None else None,
                   extraction=item.get("extraction") or extraction, retailer_sku=item.get("retailer_sku"))


@dataclass(frozen=True)
class RawDocument:
    """One observation envelope; page means listing page, never product index."""

    shop: str
    category: str
    source_type: str
    source_url: str
    fetched_at: str
    raw_html: str
    origin: str | None
    items: tuple[RawProduct, ...]
    page: int | None = None
    site_total_products: int | None = None
    run_id: str | None = None

    def __post_init__(self):
        if self.category not in CATEGORIES or not self.shop.strip():
            raise ValueError("raw document needs a shop and supported category")
        if self.source_type not in {"category", "product"}:
            raise ValueError("source_type must be category or product")
        if self.source_type == "category" and (type(self.page) is not int or self.page < 1):
            raise ValueError("category sources need a positive listing page")
        if self.source_type == "product" and (self.page is not None or len(self.items) != 1
                                               or self.site_total_products is not None):
            raise ValueError("product sources need one item, a null page and a null category total")
        if self.origin not in {"cache", "network", None}:
            raise ValueError("origin must be cache, network or null")
        if self.site_total_products is not None and (type(self.site_total_products) is not int
                                                     or self.site_total_products < 0):
            raise ValueError("site_total_products must be a non-negative integer or null")
        if not all(isinstance(item, RawProduct) for item in self.items):
            raise ValueError("items must contain RawProduct objects")
        if self.run_id is not None and (not isinstance(self.run_id, str) or not self.run_id.strip()):
            raise ValueError("run_id must be non-empty text or null")
        timestamp = datetime.fromisoformat(self.fetched_at)
        if timestamp.tzinfo is None:
            raise ValueError("fetched_at needs an explicit timezone")
        if not self.source_url.strip() or not self.raw_html.strip() or Path(self.raw_html).is_absolute() or '..' in Path(self.raw_html).parts:
            raise ValueError("source URL is required and raw_html must be data-relative")

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["items"] = [asdict(item) for item in self.items]
        return {"schema_version": SCHEMA_VERSION, **payload, "item_count": len(self.items)}


class RawDataWriter:
    """Create validated envelopes and persist them using one filename convention.

    The fetch time comes from cached HTML, so offline replay is not a fresh price
    observation. The filename uses the write time to preserve earlier snapshots.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()
        self.raw_dir = self.data_dir / "raw"

    def write(self, *, shop: str, category: str, source_type: str, source_url: str,
              raw_path: Path, items: list[RawProduct], page: int | None = None,
              site_total_products: int | None = None, origin: str | None = None,
              run_id: str | None = None) -> Path:
        raw_path = raw_path.resolve()
        document = RawDocument(
            shop=shop, category=category, source_type=source_type, source_url=source_url,
            fetched_at=datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            raw_html=raw_path.relative_to(self.data_dir).as_posix(), origin=origin,
            items=tuple(items), page=page, site_total_products=site_total_products, run_id=run_id)
        payload = document.to_dict()
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", shop.lower()).strip('_')
        digest = hashlib.sha256(source_url.encode('utf-8')).hexdigest()[:16]
        written_at = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        path = self.raw_dir / f"{slug}_{category}_{source_type}_{digest}_{written_at}.json"
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.raw_dir,
                                    prefix='.', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path
