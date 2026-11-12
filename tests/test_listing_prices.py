"""Current versus last-known prices, independent of source order and retailer."""
import contextlib
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from scraper.pipeline.listing_prices import ListingPriceSelector
from scraper.pipeline.normalisation import ComponentNormaliser


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


if __name__ == '__main__':
    unittest.main()
