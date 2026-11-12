"""BuildWise — Datatronic category paths and listing-card parsing.

Retailer markup stays here; requests and cache handling are shared.
"""
import re
from bs4 import BeautifulSoup
from scraper.common.prices import parse_price_cents

from scraper.common.raw_data import RawProduct
from scraper.retailers.contracts import (
    CategoryResult, ParseIssue, ProductRequest, RetailerConfig,
    RetailerCapabilities, UnsupportedOperationError, listing_page_url,
)

BASE_URL = "https://datatronic.fi"
USER_AGENT = "BuildWise-course-project/0.1 (eekarjal24@students.oamk.fi)"

SHOP = {
    "name": "Datatronic",
    "domain": "datatronic.fi",
    "base_url": BASE_URL,
}

# verified 3.11.2026 — (slug on datatronic.fi, total products on the site)
CATEGORIES = {
    "gpu": "/naytonohjaimet",
    "cpu": "/prosessorit",
    "motherboard": "/emolevyt",
    "memory": "/muistit",
    "storage": "/kiintolevyt-ssd-levyt",
    "case": "/kotelot",
    "psu": "/virtalahteet",
}


class DatatronicParser:
    """Own Datatronic listing markup and base URL; performs no requests."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def parse_listing(self, html: str) -> tuple[list[dict], int | None]:
        """Parse the category listing container.

        The page also contains a 'featured products' block; only the container with
        id="js-product-list" holds the actual category results.
        """
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find(id="js-product-list") or soup

        items: list[dict] = []
        for card in container.select("article.js-product-miniature, article.product-miniature"):
            name_el = card.select_one(".product-title a") or card.select_one("h3 a")
            link_el = card.select_one("a.js-product-image") or card.select_one("a[href]")
            price_el = card.select_one(".price")

            name = name_el.get_text(strip=True) if name_el else None
            href = link_el.get("href") if link_el else None
            price_cents = parse_price_cents(price_el.get_text(" ", strip=True) if price_el else "")

            if not name or not href:
                continue
            if href.startswith("/"):
                href = self.base_url + href

            items.append(
                {
                    "name": name,
                    "price_cents": price_cents,
                    "url": href,
                    "external_id": card.get("data-id-product"),
                }
            )

        total = None
        total_match = re.search(r"Yhteensä\s*([\d\s]+)\s*tuotetta", soup.get_text(" ", strip=True))
        if total_match:
            total = int(total_match.group(1).replace(" ", ""))

        return items, total


def parse_listing(html: str) -> tuple[list[dict], int | None]:
    """Compatibility function; delegate to DatatronicParser."""
    return DatatronicParser().parse_listing(html)


class DatatronicAdapter:
    """Expose existing category-card extraction through the common contract."""

    config = RetailerConfig(
        key='datatronic', name=SHOP['name'], base_url=BASE_URL,
        allowed_hosts=frozenset({'datatronic.fi', 'www.datatronic.fi'}),
        category_paths=CATEGORIES,
        capabilities=RetailerCapabilities(category_prices=True, product_prices=False, specifications=True))

    def __init__(self, parser: DatatronicParser | None = None):
        self.parser = parser if parser is not None else DatatronicParser(self.config.base_url)

    def category_url(self, category: str) -> str:
        return self.config.category_url(category)

    def page_url(self, category: str, page: int) -> str:
        return listing_page_url(self.category_url(category), page)

    def parse_category(self, html: str, category: str, source_url: str) -> CategoryResult:
        self.category_url(category)  # Reject unsupported categories explicitly.
        self.config.validate_url(source_url)
        items, total = self.parser.parse_listing(html)
        observations = tuple(RawProduct.from_item(item, extraction='listing_card') for item in items)
        issues = tuple(ParseIssue('missing_price', 'listing card has no parseable price', item.url)
                       for item in observations if item.price_cents is None)
        return CategoryResult(observations=observations, site_total_products=total, issues=issues)

    def parse_product(self, html: str, request: ProductRequest) -> RawProduct:
        raise UnsupportedOperationError('Datatronic product-page price extraction is not implemented')
