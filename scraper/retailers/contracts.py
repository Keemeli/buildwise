"""Shared retailer adapter contract; parsing performs no requests or file writes."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable
from urllib.parse import urljoin, urlsplit

from scraper.common.raw_data import RawProduct
from scraper.config import CATEGORIES


class UnsupportedCategoryError(ValueError):
    """The adapter has no configured URL for the requested category."""


class UnsupportedOperationError(ValueError):
    """The adapter does not implement the requested extraction operation."""


@dataclass(frozen=True)
class RetailerCapabilities:
    category_prices: bool
    product_prices: bool
    specifications: bool = False


@dataclass(frozen=True)
class RetailerConfig:
    key: str
    name: str
    base_url: str
    allowed_hosts: frozenset[str]
    category_paths: Mapping[str, str]
    capabilities: RetailerCapabilities

    def __post_init__(self):
        base = urlsplit(self.base_url)
        if not self.key or not self.name or base.scheme != 'https' or base.hostname not in self.allowed_hosts:
            raise ValueError('retailer identity and an allowed HTTPS base URL are required')
        paths = dict(self.category_paths)
        if any(category not in CATEGORIES for category in paths):
            raise ValueError('unsupported canonical category in retailer configuration')
        for path in paths.values():
            if not path.startswith('/') or path.startswith('//') or urlsplit(path).scheme:
                raise ValueError('category paths must be relative to the retailer base URL')
        object.__setattr__(self, 'allowed_hosts', frozenset(self.allowed_hosts))
        object.__setattr__(self, 'category_paths', MappingProxyType(paths))

    def category_url(self, category: str) -> str:
        try:
            return urljoin(self.base_url, self.category_paths[category])
        except KeyError:
            raise UnsupportedCategoryError(f'{self.name} has no configured category: {category}') from None


    def validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in self.allowed_hosts
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError(f'URL is outside {self.name} allowed HTTPS hosts')


@dataclass(frozen=True)
class ProductRequest:
    category: str
    url: str
    external_id: str | None = None
    reason: str = 'missing_price'
    retailer_sku: str | None = None

    def __post_init__(self):
        if self.category not in CATEGORIES or not self.url.strip() or not self.reason.strip():
            raise ValueError('product request needs a supported category, URL and reason')
        if any(value is not None and not isinstance(value, str)
               for value in (self.external_id, self.retailer_sku)):
            raise ValueError('product request identifiers must be strings or null')


@dataclass(frozen=True)
class ParseIssue:
    code: str
    message: str
    url: str | None = None


@dataclass(frozen=True)
class CategoryResult:
    observations: tuple[RawProduct, ...] = ()
    product_requests: tuple[ProductRequest, ...] = ()
    site_total_products: int | None = None
    issues: tuple[ParseIssue, ...] = ()


@runtime_checkable
class RetailerAdapter(Protocol):
    config: RetailerConfig

    def category_url(self, category: str) -> str: ...
    def page_url(self, category: str, page: int, *, category_url: str | None = None) -> str: ...
    def parse_category(self, html: str, category: str, source_url: str) -> CategoryResult: ...
    def parse_product(self, html: str, request: ProductRequest) -> RawProduct: ...


def listing_page_url(url: str, page: int, *, include_first: bool = False) -> str:
    """Preserve category filters and replace only the page parameter."""
    from urllib.parse import parse_qsl, urlencode, urlunsplit
    if type(page) is not int or page < 1:
        raise ValueError('page must be a positive integer')
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key.lower() != 'page']
    if page != 1 or include_first:
        query.append(('page', str(page)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))
