"""Milestone 4 integration: collection, retry and normalisation in isolation."""
import contextlib
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scraper.cli import main
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from test_collection_policy_matrix import listing, product_page, product_url


class PriceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.context.enter_context(patch('requests.Session.get', side_effect=AssertionError('live request forbidden')))

    def test_collection_null_retry_and_cached_reparse_for_both_retailers(self):
        for adapter in (JimmsAdapter(), DatatronicAdapter()):
            with self.subTest(shop=adapter.config.key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                raw, out = root / 'raw', root / 'normalised'
                category, product = adapter.page_url('gpu', 1), product_url(adapter)
                def cache(url, html, timestamp):
                    path = raw / 'html' / adapter.config.key / date.today().isoformat() / (
                        hashlib.sha256(url.encode()).hexdigest() + '.html')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(html)
                    os.utime(path, (timestamp, timestamp))
                def collect():
                    return main(['collect', '--shop', adapter.config.key, '--category', 'gpu',
                                 '--data-dir', str(root), '--offline'])
                def normalise():
                    self.assertEqual(main(['normalise', '--raw-dir', str(raw), '--out', str(out)]), 0)
                    return json.loads((out / 'components.json').read_text())['components'][0]['listings'][0]
                def originals():
                    return {p: p.read_bytes() for p in raw.glob('*.json')}
                cache(category, listing(adapter), 1700000000)
                self.assertEqual(collect(), 0)
                self.assertEqual(normalise()['price_cents'], 29999)
                original = originals()
                cache(category, listing(adapter, price=None), 1700003600)
                if adapter.config.capabilities.product_prices:
                    cache(product, product_page(price=None), 1700003600)
                self.assertEqual(collect(), 1)
                unknown = normalise()
                self.assertIsNone(unknown['price_cents'])
                self.assertEqual(unknown['last_known_price_cents'], 29999)
                self.assertEqual(unknown['last_known_price_fetched_at'], '2023-11-14T22:13:20+00:00')
                before_retry = originals()
                cache(product if adapter.config.capabilities.product_prices else category,
                      product_page('249.99') if adapter.config.capabilities.product_prices else listing(adapter, '249,99 €'),
                      1700007200)
                self.assertEqual(main(['retry', '--shop', adapter.config.key, '--data-dir', str(root), '--offline']), 0)
                recovered = normalise()
                self.assertEqual(recovered['price_cents'], 24999)
                self.assertEqual(recovered['fetched_at'], '2023-11-15T00:13:20+00:00')
                self.assertEqual(recovered['external_id'], '123')
                if adapter.config.key == 'jimms':
                    self.assertEqual(recovered['retailer_sku'], 'SKU-123')
                pending = json.loads((root / 'pending/collection.json').read_text())
                entry = next(iter(pending['entries'].values()))
                self.assertEqual(entry['status'], 'resolved')
                self.assertEqual(recovered['provenance']['run_id'], entry['resolved_run_id'])
                # Reprocessing older cached HTML does not become a new source time.
                cache(category, listing(adapter), 1700000000)
                self.assertEqual(collect(), 0)
                self.assertEqual(normalise()['price_cents'], 24999)
                for path, content in {**original, **before_retry}.items():
                    self.assertEqual(path.read_bytes(), content)
                target = root / 'web/components.json'
                self.assertEqual(main(['export', '--source', str(out / 'components.json'), '--target', str(target)]), 0)
                self.assertEqual(json.loads(target.read_text()), json.loads((out / 'components.json').read_text()))

    def test_legacy_and_versioned_ties_are_reported_without_cross_shop_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, out = root / 'raw', root / 'out'
            raw.mkdir()
            for filename, version, shop, price, timestamp in [
                ('legacy', None, 'Jimms', 100, '2026-11-09'),
                ('v1', 1, 'Jimms', 200, '2026-11-10T12:00:00+02:00'),
                ('v2', 2, 'Jimms', 300, '2026-11-10T10:00:00Z'),
                ('null', 2, 'Jimms', None, '2026-11-10T10:00:00Z'),
                ('datatronic', 2, 'Datatronic', None, '2026-11-10T10:00:00Z')]:
                payload = {'shop': shop, 'category': 'gpu', 'fetched_at': timestamp, 'items': [{
                    'name': 'MSI RTX 5070 12GB GDDR7', 'url': 'https://shop/product',
                    'external_id': shop, 'price_cents': price}]}
                if version is not None:
                    payload['schema_version'] = version
                (raw / f'{filename}.json').write_text(json.dumps(payload))
            self.assertEqual(main(['normalise', '--raw-dir', str(raw), '--out', str(out)]), 0)
            listings = {item['shop']: item for item in json.loads((out / 'components.json').read_text())['components'][0]['listings']}
            self.assertEqual(listings['Jimms']['price_status'], 'conflict')
            self.assertIsNone(listings['Jimms']['price_cents'])
            self.assertEqual(listings['Jimms']['last_known_price_cents'], 100)
            self.assertIsNone(listings['Datatronic']['last_known_price_cents'])
            report = '\n'.join(path.read_text() for path in out.glob('*.md'))
            self.assertIn('Price conflicts requiring inspection', report)


if __name__ == '__main__':
    unittest.main()
