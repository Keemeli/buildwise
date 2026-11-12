"""Proshop GPU prices and specification-parser factory; shared workers own I/O."""
from dataclasses import replace
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup

from scraper.common.prices import parse_price_cents
from scraper.common.raw_data import RawProduct
from scraper.retailers.contracts import (
    CategoryResult, ExcludedProduct, ParseIssue, RetailerCapabilities,
    RetailerConfig, UnsupportedOperationError, listing_page_url,
)


class ProshopAdapter:
    """Keep displayed VAT-inclusive prices; exclude explicitly marked DEMO items."""
    config = RetailerConfig(
        key='proshop', name='Proshop', base_url='https://www.proshop.fi',
        allowed_hosts=frozenset({'www.proshop.fi'}),
        category_paths={'gpu': '/Naeytoenohjaimet'},
        capabilities=RetailerCapabilities(category_prices=True, product_prices=False,
                                          specifications=True))

    def category_url(self, category):
        return self.config.category_url(category)

    def page_url(self, category, page, *, category_url=None):
        self.category_url(category)
        url = listing_page_url(category_url or self.category_url(category), page, page_parameter='pn')
        self.config.validate_url(url)
        return url

    @staticmethod
    def _price(card):
        amounts = card.select('.priceContainer .site-currency-lg')
        texts = [amount.get_text(' ', strip=True) for amount in amounts]
        texts = [text for text in texts if text]
        if not texts:
            return None, 'missing_price'
        values = [parse_price_cents(text) for text in texts]
        if any(value is None for value in values) or any(
                '€' not in text and not re.search(r'\bEUR\b', text, re.I) for text in texts):
            return None, 'invalid_price'
        if len(set(values)) != 1:
            return None, 'conflicting_price'
        return values[0], None

    def parse_category(self, html, category, source_url):
        self.category_url(category)
        self.config.validate_url(source_url)
        soup = BeautifulSoup(html, 'html.parser')
        listing = soup.select_one('#products')
        if listing is None:
            raise ValueError('missing Proshop category listing #products')
        cards = listing.select(':scope > li')
        total = soup.select_one('#product-count')
        total_text = re.sub(r'\s+', '', total.get_text(strip=True)) if total is not None else ''
        total_count = int(total_text) if total_text.isdecimal() else None
        products, exclusions, issues = {}, {}, []
        for card in cards:
            link = card.select_one('a.site-product-link[href]')
            title = link.select_one('h2') if link is not None else None
            identity = card.select_one('input[name="productId"]')
            name = title.get_text(' ', strip=True) if title is not None else ''
            external_id = str(identity.get('value') or '').strip() if identity is not None else ''
            if not name or not external_id or link is None or not link['href'].strip():
                issues.append(ParseIssue('missing_identity', 'Proshop card has no name, URL or retailer ID'))
                continue
            try:
                url = urljoin(source_url, link['href'])
                self.config.validate_url(url)
                parsed = urlsplit(url)
                if not parsed.path.startswith('/Naeytoenohjaimet/') or parsed.path.rstrip('/').rsplit('/', 1)[-1] != external_id:
                    raise ValueError('Proshop URL conflicts with its category or retailer listing ID')
                url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
            except ValueError as exc:
                issues.append(ParseIssue('invalid_identity', str(exc)))
                continue
            if url in exclusions:
                issues.append(ParseIssue('duplicate_url', 'repeated excluded Proshop card', url))
                continue
            badges = ' '.join(el.get_text(' ', strip=True) for el in card.select('[class*="site-image-badge"]'))
            if re.search(r'\bDEMO\b', name + ' ' + badges, re.I) or external_id.lower().endswith('d'):
                products.pop(url, None)
                exclusions[url] = ExcludedProduct(name, url, external_id, 'demo_listing')
                continue
            price, reason = self._price(card)
            product = RawProduct(name, price, url, external_id=external_id,
                                 extraction='category:.priceContainer .site-currency-lg')
            previous = products.get(url)
            if previous is not None:
                issues.append(ParseIssue('duplicate_url', 'repeated Proshop product card', url))
                if previous.price_cents != product.price_cents or previous.name != product.name:
                    products[url] = replace(previous, price_cents=None)
                    issues.append(ParseIssue('conflicting_price', 'conflicting duplicate Proshop cards', url))
                continue
            products[url] = product
            if reason:
                issues.append(ParseIssue(reason, 'no unambiguous displayed EUR price on Proshop card', url))
        issues = [issue for issue in issues if issue.url not in exclusions or issue.code == 'duplicate_url']
        confirmed_empty = not cards and not issues and total_count == 0
        return CategoryResult(observations=tuple(products.values()), exclusions=tuple(exclusions.values()),
                              site_total_products=total_count, issues=tuple(issues),
                              end_of_category=confirmed_empty,
                              end_reason='published_total_zero' if confirmed_empty else None)

    def parse_product(self, html, request):
        raise UnsupportedOperationError('Proshop product-page price extraction is not implemented')

    def specification_parser(self):
        from scraper.retailers.proshop_specs import ProshopSpecParser
        return ProshopSpecParser()
