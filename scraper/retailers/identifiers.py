"""Pure extraction of explicit identity evidence from a bound product response."""
import json
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup
from scraper.common.product_identity import ProductIdentity


def canonical_product_url(value, base):
    parsed = urlsplit(urljoin(base, value))
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, '', ''))


def structured_candidates(soup, source_url, external_id=None, *, sku_is_listing_id=False):
    """Ignore accessory/variant Product nodes that do not identify this request."""
    candidates, issues = [], []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            raw = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        pending = list(raw) if isinstance(raw, list) else [raw]
        while pending:
            node = pending.pop(0)
            if not isinstance(node, dict):
                continue
            graph = node.get('@graph')
            if isinstance(graph, list):
                pending.extend(graph)
            types = node.get('@type', [])
            if types != 'Product' and not (isinstance(types, list) and 'Product' in types):
                continue
            urls = [node['url']] if isinstance(node.get('url'), str) else []
            offers = node.get('offers', [])
            for offer in offers if isinstance(offers, list) else [offers]:
                if isinstance(offer, dict) and isinstance(offer.get('url'), str):
                    urls.append(offer['url'])
            try:
                matching_url = any(canonical_product_url(url, source_url) == canonical_product_url(source_url, source_url) for url in urls)
            except ValueError:
                issues.append('source_product_url_invalid')
                continue
            sku = node.get('sku')
            matching_id = sku_is_listing_id and external_id is not None and sku is not None and str(sku) == str(external_id)
            if not matching_url and not matching_id:
                continue
            # Contradictory identity is not evidence about the requested listing.
            if (urls and not matching_url) or (sku_is_listing_id and external_id is not None and sku is not None and not matching_id):
                issues.append('source_product_identity_conflict')
                continue
            for key in ('gtin', 'gtin8', 'gtin12', 'gtin13', 'gtin14'):
                if key in node:
                    candidates.append(('gtin', node[key], f'Product JSON-LD:{key}'))
            if 'mpn' in node:
                candidates.append(('manufacturer_part_number', node['mpn'], 'Product JSON-LD:mpn'))
            brand = node.get('brand')
            if isinstance(brand, dict):
                brand = brand.get('name')
            if brand is not None:
                candidates.append(('brand', brand, 'Product JSON-LD:brand'))
    return candidates, issues


def product_identity(html, source_url, external_id=None, *, metadata_selector=None, sku_is_listing_id=False):
    soup = BeautifulSoup(html, 'html.parser')
    candidates, issues = structured_candidates(soup, source_url, external_id, sku_is_listing_id=sku_is_listing_id)
    if metadata_selector:
        metadata = soup.select_one(metadata_selector)
        sku = metadata.select_one('[itemprop="sku"]') if metadata is not None else None
        observed_id = (sku.get('content') or sku.get_text(strip=True)) if sku is not None else None
        if metadata is not None and observed_id == str(external_id):
            for prop, field in [('gtin13', 'gtin'), ('gtin', 'gtin'), ('mpn', 'manufacturer_part_number')]:
                for element in metadata.select(f'[itemprop="{prop}"]'):
                    candidates.append((field, element.get('content') or element.get_text(' ', strip=True),
                                       f'{metadata_selector} [itemprop={prop}]'))
        elif metadata is not None and observed_id is not None:
            issues.append('source_product_identity_conflict')
    return ProductIdentity.from_candidates(candidates, issues)
