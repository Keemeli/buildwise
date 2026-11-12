"""Component parsing, price selection, provenance and collection-to-catalogue flows."""
import contextlib
import hashlib
import io
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scraper.cli import main
from scraper.pipeline.components import ComponentNameParser
from scraper.pipeline.listing_prices import ListingPriceSelector
from scraper.pipeline.normalisation import ComponentNormaliser
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter

from tests.support import ROOT, listing, product_page, product_url


class MultiShopNormalisationTests(unittest.TestCase):
    def test_multiple_shops_and_intraday_price(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / 'raw'
            raw.mkdir()
            # Deliberately make the older record sort last by filename.
            for filename, shop, timestamp, price in [
                ('a.json', 'Jimms', '2026-11-05T12:00:00+00:00', 100),
                ('z.json', 'Jimms', '2026-11-05T09:00:00+00:00', 200),
                ('b.json', 'Datatronic', '2026-11-05T11:00:00+00:00', 300)]:
                (raw / filename).write_text(json.dumps({'shop': shop, 'category': 'gpu',
                    'fetched_at': timestamp, 'items': [{'name': 'MSI RTX 5070 12GB GDDR7',
                    'url': f'https://{shop.lower()}.fi/product', 'price_cents': price}]}))
            result = subprocess.run([sys.executable, '-m', 'scraper', 'normalise',
                '--raw-dir', str(raw), '--out', str(Path(directory) / 'out')], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            catalogue = json.loads((Path(directory) / 'out/components.json').read_text())
            self.assertEqual(catalogue['component_count'], 2)
            listings = [listing for component in catalogue['components'] for listing in component['listings']]
            self.assertEqual({x['shop']: x['price_cents'] for x in listings}, {'Jimms': 100, 'Datatronic': 300})
            self.assertIn('Jimms', catalogue['source'])

    def test_new_identifiers_survive_normalisation_with_legacy_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            records = [
                ('new.json', 2, 'Jimms', 'https://www.jimms.fi/fi/Product/Show/209432/gpu',
                 '209432', 'PRIME-RTX5070-O12G'),
                ('old.json', 1, 'Datatronic', 'https://datatronic.fi/gpu', '168663', None),
                ('legacy.json', None, 'Jimms', 'https://www.jimms.fi/legacy-gpu', 'OLD-SKU', None),
            ]
            for filename, version, shop, url, external_id, sku in records:
                item = {'name': 'MSI RTX 5070 12GB GDDR7', 'url': url,
                        'price_cents': 29999, 'external_id': external_id}
                if sku is not None:
                    item['retailer_sku'] = sku
                payload = {'shop': shop, 'category': 'gpu', 'fetched_at': '2026-11-05T12:00:00+00:00',
                           'items': [item]}
                if version is not None:
                    payload['schema_version'] = version
                (raw / filename).write_text(json.dumps(payload))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ComponentNormaliser(raw, root / 'out').run(), 0)
            catalogue = json.loads((root / 'out/components.json').read_text())
            listings = {item['url']: item for component in catalogue['components'] for item in component['listings']}
            for _, _, _, url, external_id, sku in records:
                self.assertEqual(listings[url]['external_id'], external_id)
                self.assertEqual(listings[url].get('retailer_sku'), sku)
            self.assertNotIn('retailer_sku', listings['https://datatronic.fi/gpu'])


class NormaliserConfigurationTests(unittest.TestCase):
    def test_component_parser_configuration_does_not_change_default_parser(self):
        item = {'category': 'gpu', 'raw_name': 'MSI RTX 5070 12GB GDDR7',
                'shop': 'Jimms', 'url': 'https://www.jimms.fi/product',
                'external_id': None, 'price_cents': 29999,
                'fetched_at': '2026-11-05T12:00:00+00:00', 'snapshot_date': '2026-11-05'}
        custom = ComponentNameParser(parsers={'gpu': lambda name: {'custom': 42}},
                                     expected_fields={'gpu': ('custom',)})
        self.assertEqual(custom.parse(item)['specs'], {'custom': 42})
        self.assertEqual(ComponentNameParser().parse(item)['specs']['chipset'], 'RTX 5070')
        self.assertEqual(custom.parse(item)['missing_specs'], [])

    def test_normaliser_can_use_a_report_writer_without_replacing_parsing(self):
        class RecordingWriter:
            def write(self, out_dir, components, *args):
                self.components = components
                return out_dir / 'custom-report.md'

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            (raw / 'gpu.json').write_text(json.dumps({'shop': 'Jimms', 'category': 'gpu',
                'fetched_at': '2026-11-05T12:00:00+00:00', 'items': [
                    {'name': 'MSI RTX 5070 12GB GDDR7', 'url': 'https://www.jimms.fi/product',
                     'price_cents': 29999}]}))
            writer = RecordingWriter()
            worker = ComponentNormaliser(raw, root / 'out', report_writer=writer)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker.run(), 0)
            payload = json.loads((root / 'out/components.json').read_text())
            self.assertEqual(writer.components, payload['components'])
            self.assertEqual(payload['components'][0]['listings'][0]['shop'], 'Jimms')


def observation(price, timestamp, source='source.json', shop='Jimms'):
    return {'shop': shop, 'url': 'https://shop/product', 'price_cents': price,
            'fetched_at': timestamp, 'snapshot_date': timestamp[:10],
            'external_id': '123', 'retailer_sku': 'SKU',
            'provenance': {'source_file': source, 'run_id': source}}


class ListingPriceTests(unittest.TestCase):
    def test_priced_null_recovered_sequence_for_both_retailers(self):
        for shop in ('Jimms', 'Datatronic'):
            with self.subTest(shop=shop):
                rows = [observation(300, '2026-11-10T10:00:00Z', shop=shop),
                        observation(None, '2026-11-10T11:00:00Z', shop=shop),
                        observation(250, '2026-11-10T12:00:00Z', shop=shop)]
                selector = ListingPriceSelector()
                null = selector.select(rows[:2])
                self.assertIsNone(null['price_cents'])
                self.assertEqual(null['last_known_price_cents'], 300)
                self.assertEqual(null['last_known_price_fetched_at'], rows[0]['fetched_at'])
                recovered = selector.select(rows)
                self.assertEqual(recovered['price_cents'], 250)
                self.assertEqual(recovered['last_known_price_cents'], 250)
                self.assertEqual(recovered['retailer_sku'], 'SKU')

    def test_equal_timestamp_valid_beats_null_and_conflicts_are_order_independent(self):
        timestamp = '2026-11-10T10:00:00Z'
        rows = [observation(None, timestamp, 'null'), observation(300, timestamp, 'priced')]
        for ordered in itertools.permutations(rows):
            self.assertEqual(ListingPriceSelector().select(ordered)['price_cents'], 300)
        rows += [observation(400, timestamp, 'conflict'),
                 observation(200, '2026-11-09T10:00:00Z', 'old')]
        outputs = [ListingPriceSelector().select(ordered) for ordered in itertools.permutations(rows)]
        self.assertTrue(all(output == outputs[0] for output in outputs))
        self.assertEqual(outputs[0]['price_status'], 'conflict')
        self.assertIsNone(outputs[0]['price_cents'])
        self.assertEqual(outputs[0]['last_known_price_cents'], 200)
        self.assertEqual(len(outputs[0]['price_observations']), 3)

    def test_timezones_compare_as_instants_and_cached_reparse_stays_old(self):
        rows = [observation(300, '2026-11-10T12:00:00+03:00', 'z-new-filename'),
                observation(None, '2026-11-10T10:00:00Z', 'a-old-filename')]
        selected = ListingPriceSelector().select(rows)
        self.assertIsNone(selected['price_cents'])
        self.assertEqual(selected['last_known_price_cents'], 300)
        # Equivalent instants must conflict even when their spellings differ.
        rows.append(observation(400, '2026-11-10T09:00:00Z', 'same-instant'))
        selected = ListingPriceSelector().select(rows)
        self.assertIsNone(selected['last_known_price_cents'])

    def test_legacy_missing_times_and_all_null_are_not_given_processing_dates(self):
        row = observation(None, '', 'legacy')
        selected = ListingPriceSelector().select([row])
        self.assertEqual(selected['fetched_at'], '')
        self.assertEqual(selected['price_status'], 'unknown')
        self.assertIsNone(selected['last_known_price_fetched_at'])
        row['snapshot_date'] = '2026-11-09'
        self.assertEqual(ListingPriceSelector().observed_at(row).isoformat(), '2026-11-09T00:00:00+00:00')

    def test_identifier_fallback_preserves_source_evidence(self):
        old = observation(300, '2026-11-09T10:00:00Z', 'old')
        new = observation(None, '2026-11-10T10:00:00Z', 'new')
        new.update(external_id=None, retailer_sku=None)
        selected = ListingPriceSelector().select([old, new])
        self.assertEqual(selected['external_id'], '123')
        self.assertEqual(selected['retailer_sku'], 'SKU')
        self.assertEqual(selected['identifier_sources']['external_id']['provenance']['source_file'], 'old')
        self.assertEqual(selected['provenance']['source_file'], 'new')
        self.assertEqual(selected['last_known_price_source']['provenance']['source_file'], 'old')
        self.assertIsNone(selected['price_observations'][0]['external_id'])

    def test_normaliser_reports_conflicts_and_preserves_raw_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, out = root / 'raw', root / 'out'
            raw.mkdir()
            for name, price in [('a', 300), ('b', 400)]:
                payload = {'shop': 'Jimms', 'category': 'gpu', 'schema_version': 2,
                    'fetched_at': '2026-11-10T10:00:00Z', 'run_id': name,
                    'source_type': 'category', 'source_url': 'https://shop/gpu',
                    'raw_html': f'raw/html/{name}.html', 'items': [{
                        'name': 'MSI RTX 5070 12GB GDDR7', 'url': 'https://shop/product',
                        'price_cents': price, 'external_id': '123', 'retailer_sku': 'SKU'}]}
                (raw / f'{name}.json').write_text(json.dumps(payload))
            before = {p: p.read_bytes() for p in raw.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ComponentNormaliser(raw, out).run(), 0)
            listing = json.loads((out / 'components.json').read_text())['components'][0]['listings'][0]
            self.assertIsNone(listing['price_cents'])
            self.assertEqual({item['provenance']['run_id'] for item in listing['price_observations']}, {'a', 'b'})
            report = '\n'.join(p.read_text() for p in out.glob('*.md'))
            self.assertIn('Price conflicts requiring inspection', report)
            self.assertIn('300 cents', report)
            self.assertIn('400 cents', report)
            self.assertEqual({p: p.read_bytes() for p in raw.iterdir()}, before)


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
            listings = {item['shop']: item for component in json.loads((out / 'components.json').read_text())['components'] for item in component['listings']}
            self.assertEqual(listings['Jimms']['price_status'], 'conflict')
            self.assertIsNone(listings['Jimms']['price_cents'])
            self.assertEqual(listings['Jimms']['last_known_price_cents'], 100)
            self.assertIsNone(listings['Datatronic']['last_known_price_cents'])
            report = '\n'.join(path.read_text() for path in out.glob('*.md'))
            self.assertIn('Price conflicts requiring inspection', report)


if __name__ == '__main__':
    unittest.main()
