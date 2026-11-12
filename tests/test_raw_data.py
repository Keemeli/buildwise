"""Raw observation schema, immutable writes, compatibility and exact prices."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.common.prices import parse_price_cents
from scraper.common.raw_data import RawDataWriter, RawDocument, RawProduct
from scraper.pipeline.normalisation import iter_raw_items


class RawDataTests(unittest.TestCase):
    def test_both_source_types_have_identical_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / 'raw/html/page.html'
            html.parent.mkdir(parents=True)
            html.write_text('cached page')
            observed = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
            os.utime(html, (observed.timestamp(), observed.timestamp()))
            writer = RawDataWriter(root)
            payloads = []
            for shop, kind, page in [('Datatronic', 'category', 2), ('Jimms', 'product', None)]:
                path = writer.write(shop=shop, category='gpu', source_type=kind,
                    source_url=f'https://{shop.lower()}.fi/source', raw_path=html,
                    items=[RawProduct('GPU', 29999, f'https://{shop.lower()}.fi/gpu')],
                    page=page, origin='cache')
                payload = json.loads(path.read_text())
                self.assertEqual(payload['raw_html'], 'raw/html/page.html')
                self.assertEqual(payload['fetched_at'], observed.isoformat(timespec='seconds'))
                self.assertEqual(payload['item_count'], len(payload['items']))
                self.assertEqual(payload['schema_version'], 2)
                payloads.append(payload)
            self.assertEqual(set(payloads[0]), set(payloads[1]))
            self.assertEqual(set(payloads[0]['items'][0]), set(payloads[1]['items'][0]))
            self.assertEqual(payloads[0]['page'], 2)
            self.assertIsNone(payloads[1]['page'])

    def test_missing_price_and_id_stay_null(self):
        product = RawProduct.from_item({'name': 'GPU', 'url': 'https://shop.fi/gpu'})
        self.assertIsNone(product.price_cents)
        self.assertIsNone(product.external_id)
        self.assertIsNone(product.extraction)
        for value in ('29999', 299.99, True, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RawProduct('GPU', value, 'https://shop.fi/gpu')

    def test_product_page_cannot_claim_a_listing_page_number(self):
        with self.assertRaisesRegex(ValueError, 'null page'):
            RawDocument('Jimms', 'gpu', 'product', 'https://shop.fi/gpu',
                        '2026-11-05T12:00:00+00:00', 'raw/html/page.html', 'cache',
                        (RawProduct('GPU', 29999, 'https://shop.fi/gpu'),), page=1)

    def test_normaliser_reads_legacy_and_versioned_payloads_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / 'raw/html/page.html'
            html.parent.mkdir(parents=True)
            html.write_text('cached')
            writer = RawDataWriter(root)
            writer.write(shop='Jimms', category='gpu', source_type='product',
                source_url='https://www.jimms.fi/gpu', raw_path=html,
                items=[RawProduct('GPU', 29999, 'https://www.jimms.fi/gpu')])
            (root / 'raw/legacy.json').write_text(json.dumps({'shop': 'Datatronic', 'category': 'gpu',
                'fetched_at': '2026-11-05T12:00:00+00:00', 'items': [
                    {'name': 'GPU', 'url': 'https://datatronic.fi/gpu', 'price_cents': 30000}]}))
            self.assertEqual({item['shop'] for item in iter_raw_items(root / 'raw', None)}, {'Jimms', 'Datatronic'})

    def test_real_workers_write_the_same_contract_and_normalise_together(self):
        import contextlib
        import io
        from unittest.mock import Mock
        from scraper.workers.collection_worker import CollectionWorker
        from scraper.retailers.datatronic import DatatronicAdapter
        from scraper.retailers.jimms import JimmsAdapter
        from scraper.retailers.contracts import ProductRequest
        from scraper.pipeline.normalisation import ComponentNormaliser
        from scraper.workers.specifications import iter_listings

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data'
            cache = data / 'raw/html'
            cache.mkdir(parents=True)
            listing = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
                       '<h3 class="product-title"><a href="/gpu">MSI RTX 5070 12GB GDDR7</a></h3>'
                       '<span class="price">300,00 €</span></article></div>')
            product = '<h1>MSI RTX 5070 12GB GDDR7</h1><meta property="product:price:amount" content="299.99">'
            listing_path, product_path = cache / 'listing.html', cache / 'product.html'
            listing_path.write_text(listing)
            product_path.write_text(product)
            datatronic, jimms = Mock(), Mock()
            datatronic.fetch.return_value = (listing, listing_path, 'cache')
            jimms.fetch.return_value = (product, product_path, 'cache')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(CollectionWorker(DatatronicAdapter(), data, datatronic, ['gpu']).run().exit_code, 0)
                self.assertEqual(CollectionWorker(JimmsAdapter(), data, jimms, product_requests=(
                    ProductRequest('gpu', 'https://www.jimms.fi/fi/Product/Show/123/gpu'),)).run().exit_code, 0)
                self.assertEqual(ComponentNormaliser(data / 'raw', data / 'normalised').run(), 0)
            documents = [json.loads(path.read_text()) for path in (data / 'raw').glob('*.json')]
            self.assertEqual(len(documents), 2)
            self.assertEqual(set(documents[0]), set(documents[1]))
            self.assertEqual(set(documents[0]['items'][0]), set(documents[1]['items'][0]))
            for document in documents:
                self.assertTrue((data / document['raw_html']).is_file())
                self.assertEqual(document['origin'], 'cache')
            catalogue = json.loads((data / 'normalised/components.json').read_text())
            self.assertEqual(catalogue['component_count'], 2)
            self.assertTrue(all(len(component['listings']) == 1 for component in catalogue['components']))
            self.assertEqual({component['listings'][0]['shop'] for component in catalogue['components']}, {'Jimms', 'Datatronic'})
            self.assertEqual([entry['shop'] for entry in iter_listings(data / 'raw', None)], ['Datatronic'])

    def test_writer_preserves_previous_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / 'raw/html/page.html'
            html.parent.mkdir(parents=True)
            html.write_text('cached')
            writer = RawDataWriter(root)
            args = dict(shop='Jimms', category='gpu', source_type='product',
                source_url='https://www.jimms.fi/gpu', raw_path=html,
                items=[RawProduct('GPU', 29999, 'https://www.jimms.fi/gpu')])
            self.assertNotEqual(writer.write(**args), writer.write(**args))
            self.assertEqual(len(list((root / 'raw').glob('*.json'))), 2)

    def test_retailer_id_and_sku_are_distinct_and_unknown_values_stay_null(self):
        product = RawProduct.from_item({'name': 'GPU', 'url': 'https://shop.fi/gpu',
                                        'external_id': 209432, 'retailer_sku': 'PRIME-RTX5070-O12G'})
        self.assertEqual(product.external_id, '209432')
        self.assertEqual(product.retailer_sku, 'PRIME-RTX5070-O12G')
        self.assertIsNone(RawProduct('GPU', None, 'https://shop.fi/gpu').retailer_sku)
        with self.assertRaises(ValueError):
            RawProduct('GPU', 100, 'https://shop.fi/gpu', retailer_sku=209432)


class PriceParsingTests(unittest.TestCase):
    def test_exact_cents(self):
        self.assertEqual(parse_price_cents('0,29 €'), 29)
        for value in ('-1', 'NaN', '0', '1.234', '1,234.56'):
            self.assertIsNone(parse_price_cents(value))


if __name__ == '__main__':
    unittest.main()
