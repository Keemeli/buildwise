"""BuildWise — Jimms metadata parser and category-price adapter.

    Primary price: meta[property="product:price:amount"]
    Fallback price: [itemprop="price"]

Missing data is reported, never invented. This parser does not fetch pages or
extract hardware specifications. Selectors must be checked against live samples.
"""

from __future__ import annotations

import re
from bs4 import BeautifulSoup
from scraper.common.prices import parse_price_cents

from urllib.parse import urljoin, urlsplit, urlunsplit
from scraper.common.raw_data import RawProduct
from scraper.retailers.contracts import (
    CategoryResult, ParseIssue, ProductRequest, RetailerConfig,
    RetailerCapabilities, listing_page_url, PriceExtractionError,
)

SHOP = "Jimms"
HOSTS = {"jimms.fi", "www.jimms.fi"}


# Category URLs observed in Jimms public navigation. Other categories can use
# an explicit --url until their paths have been verified.
CATEGORY_URLS = {
    "gpu": "https://www.jimms.fi/fi/Product/List/000-00P/komponentit--naytonohjaimet",
    "cpu": "https://www.jimms.fi/fi/Product/List/000-00R/komponentit--prosessorit",
}


class JimmsParser:
    """Own Jimms selectors and allowed hosts; performs no network access."""

    def __init__(self, hosts: set[str] | None = None):
        self.hosts = set(HOSTS if hosts is None else hosts)

    def parse_name(self, soup) -> str:
        """Read product identity independently of price availability."""
        name = None
        for selector in ('h1[itemprop="name"]', 'h1', 'meta[property="og:title"]'):
            element = soup.select_one(selector)
            if element:
                name = " ".join((element.get("content") or element.get_text(" ", strip=True)).split())
                if name:
                    break
        if not name:
            raise ValueError("missing product name")

        return name

    def parse_product(self, html: str) -> dict:
        """Return name + price, rejecting missing, invalid or conflicting metadata."""
        soup = BeautifulSoup(html, "html.parser")
        name = self.parse_name(soup)

        currencies = {str(el.get("content") or el.get_text(strip=True)).strip().upper()
                      for el in soup.select('meta[property="product:price:currency"], [itemprop="priceCurrency"]')}
        if currencies and currencies != {"EUR"}:
            raise ValueError(f"unsupported or conflicting currency: {sorted(currencies)}")

        prices = []
        methods = []
        for selector in ('meta[property="product:price:amount"]', '[itemprop="price"]'):
            for element in soup.select(selector):
                raw = element.get("content") or element.get("value") or element.get_text(" ", strip=True)
                price = parse_price_cents(raw)
                if price is None:
                    raise ValueError(f"invalid price metadata: {raw!r}")
                prices.append(price)
                methods.append(selector)
        if not prices:
            raise ValueError("missing price metadata")
        if len(set(prices)) != 1:
            raise ValueError("conflicting price metadata")
        return {"name": name, "price_cents": prices[0], "extraction": methods[0]}

    def parse_category(self, html: str, source_url: str) -> list[str]:
        """Read only the actual listing, excluding menus and recommended products.

        Jimms currently renders product-box links inside #initproductlist in the
        initial HTML, even though its pagination controls use JavaScript.
        """
        from urllib.parse import urljoin, urlsplit, urlunsplit
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one('#initproductlist')
        if container is None:
            raise ValueError("missing Jimms category listing #initproductlist")
        urls = []
        for anchor in container.select('product-box a[href]'):
            parsed = urlsplit(urljoin(source_url, anchor['href']))
            if (parsed.scheme != 'https' or parsed.hostname not in self.hosts
                    or not parsed.path.startswith('/fi/Product/Show/')):
                continue
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
            if url not in urls:
                urls.append(url)
        if not urls:
            raise ValueError("no product links found; inspect cached category HTML")
        return urls


def parse_product(html: str) -> dict:
    """Compatibility function; delegate to JimmsParser."""
    return JimmsParser().parse_product(html)


def parse_category(html: str, source_url: str) -> list[str]:
    """Compatibility function; delegate to JimmsParser."""
    return JimmsParser().parse_category(html, source_url)


class JimmsAdapter:
    """Read displayed category prices; leave optional product follow-ups explicit.

    Only the GPU category has been checked against saved product-page prices.
    Analytics prices are deliberately excluded from extraction.
    """

    config = RetailerConfig(
        key='jimms', name=SHOP, base_url='https://www.jimms.fi', allowed_hosts=frozenset(HOSTS),
        category_paths={key: urlsplit(url).path for key, url in CATEGORY_URLS.items()},
        capabilities=RetailerCapabilities(category_prices=True, product_prices=True, specifications=True))

    def __init__(self, parser: JimmsParser | None = None):
        self.parser = parser if parser is not None else JimmsParser(set(self.config.allowed_hosts))

    @staticmethod
    def product_id_from_url(url: str) -> str:
        """Read Jimms' internal record ID; never substitute a SKU or our own ID."""
        match = re.fullmatch(r'/fi/Product/Show/([0-9]+)(?:/.*)?', urlsplit(url).path)
        if match is None:
            raise ValueError('Jimms product URL has no numeric retailer product ID')
        return match.group(1)

    def category_url(self, category: str) -> str:
        return self.config.category_url(category)

    def page_url(self, category: str, page: int, *, category_url: str | None = None) -> str:
        return listing_page_url(category_url or self.category_url(category), page, include_first=True)

    def parse_category(self, html: str, category: str, source_url: str) -> CategoryResult:
        self.category_url(category)
        self.config.validate_url(source_url)
        soup = BeautifulSoup(html, 'html.parser')
        container = soup.select_one('#initproductlist')
        if container is None:
            raise ValueError('missing Jimms category listing #initproductlist')
        observations, requests, issues, seen = [], [], [], set()
        for card in container.select('product-box'):
            name_el = card.select_one('.product-box-name a[href]')
            if name_el is None:
                issues.append(ParseIssue('missing_identity', 'product card has no name/link'))
                continue
            name = ' '.join(name_el.get_text(' ', strip=True).split())
            parsed = urlsplit(urljoin(source_url, name_el['href']))
            if (not name or parsed.scheme != 'https' or parsed.hostname not in self.config.allowed_hosts
                    or parsed.username or parsed.password or parsed.port not in (None, 443)
                    or not parsed.path.startswith('/fi/Product/Show/')):
                issues.append(ParseIssue('invalid_identity', 'product card has an invalid name or URL'))
                continue
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
            try:
                external_id = self.product_id_from_url(url)
            except ValueError as exc:
                issues.append(ParseIssue('invalid_product_id', str(exc), url))
                continue
            if url in seen:
                issues.append(ParseIssue('duplicate_url', 'product URL repeated in listing', url))
                continue
            seen.add(url)
            sku_el = card.select_one('.product-box-sku')
            sku = sku_el.get_text(strip=True) if sku_el else None
            amounts = [parse_price_cents(el.get_text(' ', strip=True)) for el in card.select('.price__amount')]
            if not amounts:
                reason = 'missing_price'
            elif any(value is None for value in amounts):
                reason = 'invalid_price'
            elif len(set(amounts)) != 1:
                reason = 'conflicting_price'
            else:
                reason = None
            if reason:
                issues.append(ParseIssue(reason, 'no unambiguous displayed price on product card', url))
                observations.append(RawProduct(name, None, url, external_id=external_id,
                                               retailer_sku=sku or None, extraction='category:.price__amount'))
                requests.append(ProductRequest(category, url, external_id=external_id, reason=reason, retailer_sku=sku or None))
                continue
            observations.append(RawProduct(name, amounts[0], url, external_id=external_id,
                                           extraction='category:.price__amount', retailer_sku=sku or None))
        if not seen and not issues:
            raise ValueError('no identifiable products found in Jimms category listing')
        # The saved page's totalCount element is a JS placeholder, not a total.
        return CategoryResult(observations=tuple(observations), product_requests=tuple(requests),
                              issues=tuple(issues), site_total_products=None)

    def parse_product(self, html: str, request: ProductRequest) -> RawProduct:
        self.config.validate_url(request.url)
        external_id = self.product_id_from_url(request.url)
        if request.external_id is not None and request.external_id != external_id:
            raise ValueError('Jimms request product ID conflicts with its URL')
        try:
            result = self.parser.parse_product(html)
        except ValueError as exc:
            message = str(exc)
            if not any(token in message for token in ('price metadata', 'currency')):
                raise
            name = self.parser.parse_name(BeautifulSoup(html, 'html.parser'))
            product = RawProduct(name, None, request.url, external_id=external_id,
                                 retailer_sku=request.retailer_sku, extraction='product:metadata',
                                 identity=self.extract_identity(html, request.url, external_id))
            reason = 'missing_price' if 'missing price' in message else 'conflicting_price' if 'conflicting' in message else 'invalid_price'
            raise PriceExtractionError(message, product, reason) from exc
        return RawProduct.from_item({**result, 'url': request.url, 'external_id': external_id,
                                     'retailer_sku': request.retailer_sku,
                                     'identity': self.extract_identity(html, request.url, external_id)})

    def specification_parser(self):
        """Create the retailer's parser; shared workers own requests and storage."""
        from scraper.retailers.jimms_specs import JimmsSpecParser
        return JimmsSpecParser()

    def extract_identity(self, html, source_url, external_id=None):
        """Read explicit identifiers from an already-fetched product response."""
        from scraper.retailers.identifiers import product_identity
        self.config.validate_url(source_url)
        # URL identity also supports historical manifests whose external_id
        # once contained a model code instead of the retailer's numeric ID.
        return product_identity(html, source_url, self.product_id_from_url(source_url),
                                metadata_selector='jim-product-sku-ean-warranty-info')
