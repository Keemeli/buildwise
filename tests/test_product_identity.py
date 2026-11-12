"""Identifier validation, product-bound evidence and preservation without matching."""
import contextlib
from datetime import date
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

from scraper.cli import main
from scraper.pipeline.identity_matching import ProductIdentityMatcher, VerifiedProductGrouper
from scraper.common.product_identity import ProductIdentity, normalise_identifier
from scraper.common.raw_data import RawProduct, RawDataWriter
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from scraper.retailers.proshop import ProshopAdapter
from tests.support import ROOT

FIXTURES = ROOT / 'tests/fixtures'


class ProductIdentityTests(unittest.TestCase):
    def test_gtin_formats_preserve_zeroes_and_validate_check_digits(self):
        for raw, expected in [('96385074', '00000096385074'),
                              ('036000291452', '00036000291452'),
                              ('4006381333931', '04006381333931'),
                              ('10012345000017', '10012345000017')]:
            with self.subTest(raw=raw):
                self.assertEqual(normalise_identifier('gtin', raw), (expected, None))
        for raw in (4006381333931, '4006381333932', '0000000000000', '123456789', 'abc'):
            with self.subTest(raw=raw):
                value, error = normalise_identifier('gtin', raw)
                self.assertIsNone(value)
                self.assertIsNotNone(error)

    def test_part_number_punctuation_and_raw_evidence_are_preserved(self):
        identity = ProductIdentity.from_candidates([
            ('gtin', '4713436175742', 'example:EAN'),
            ('manufacturer_part_number', ' RX9070XT-16G-L/OC ', 'example:mpn')])
        self.assertEqual(identity.manufacturer_part_number, 'RX9070XT-16G-L/OC')
        self.assertEqual(identity.evidence[1].raw_value, ' RX9070XT-16G-L/OC ')
        product = RawProduct.from_item({'name': 'GPU', 'url': 'https://shop/product',
                                       'external_id': '123', 'retailer_sku': 'SKU-123'})
        self.assertIsNone(product.identity)  # retailer SKU is not promoted to MPN
        with self.assertRaises(ValueError):
            ProductIdentity(gtin='4006381333931')  # canonical field is 14 digits

    def test_invalid_and_conflicting_identifiers_are_retained_without_choosing(self):
        identity = ProductIdentity.from_candidates([
            ('gtin', '4006381333931', 'one'), ('gtin', '4713436175742', 'two'),
            ('manufacturer_part_number', 'N/A', 'three')])
        self.assertIsNone(identity.gtin)
        self.assertIsNone(identity.manufacturer_part_number)
        self.assertIn('gtin:conflicting_values', identity.issues)
        self.assertEqual(len(identity.evidence), 3)
        self.assertEqual(identity.evidence[2].error, 'missing_or_placeholder')

    def test_saved_jimms_and_proshop_identifiers_are_explicit_and_scoped(self):
        source = json.loads((FIXTURES / 'jimms/product_identity.source.json').read_text())
        identity = JimmsAdapter().extract_identity((FIXTURES / 'jimms/product_identity.html').read_text(), source['source_url'])
        self.assertEqual(identity.gtin, '04713436175742')
        self.assertEqual(identity.manufacturer_part_number, 'RX9070XT-16G-L/OC')
        products = json.loads((FIXTURES / 'proshop/observations.json').read_text())['products']
        for product in products:
            identity = ProshopAdapter().extract_identity(
                (FIXTURES / f"proshop/product_{product['external_id']}.html").read_text(),
                product['source_url'], product['external_id'])
            self.assertEqual(identity.gtin, product['ean'].zfill(14))
            self.assertEqual(identity.manufacturer_part_number, product['manufacturer_part_number'])
        unknown = DatatronicAdapter().extract_identity('<h1>No verified identity markup</h1>', 'https://datatronic.fi/gpu', '123')
        self.assertIsNone(unknown.gtin)
        self.assertIsNone(unknown.manufacturer_part_number)

    def test_saved_datatronic_identifiers_bind_to_primary_product(self):
        source = json.loads((FIXTURES / 'datatronic/product_identity.source.json').read_text())
        html = (FIXTURES / 'datatronic/product_identity.html').read_text()
        identity = DatatronicAdapter().extract_identity(html, source['source_url'], '166662')
        self.assertEqual(identity.gtin, '04719331355579')
        self.assertEqual(identity.manufacturer_part_number, 'GV-N507TWF3OC-16GD')
        self.assertEqual(identity.brand, 'Gigabyte')
        self.assertFalse(identity.issues)
        # Recommendations precede the primary input and must not supply its ID.
        self.assertNotEqual(BeautifulSoup(html, 'html.parser').select_one('input[name=id_product]')['value'], '166662')
        proshop = json.loads((FIXTURES / 'proshop/observations.json').read_text())['products']
        same = next(product for product in proshop if product['external_id'] == '3331106')
        self.assertEqual(identity.gtin, same['ean'].zfill(14))
        self.assertEqual(identity.manufacturer_part_number, same['manufacturer_part_number'])

    def test_datatronic_conflicts_stay_unknown_and_unrelated_metadata_is_ignored(self):
        source = json.loads((FIXTURES / 'datatronic/product_identity.source.json').read_text())
        html = (FIXTURES / 'datatronic/product_identity.html').read_text()
        adapter = DatatronicAdapter()
        unrelated = '<meta itemprop="gtin13" content="4006381333931">' + html
        self.assertEqual(adapter.extract_identity(unrelated, source['source_url'], '166662').gtin, '04719331355579')
        for external_id, page in [('166663', html), ('166662', html.replace('id="product_page_product_id"', 'id="unbound"').replace('value="166662"', 'value="999"').replace('id="unbound"', 'id="product_page_product_id"'))]:
            with self.subTest(external_id=external_id):
                identity = adapter.extract_identity(page, source['source_url'], external_id)
                self.assertIsNone(identity.gtin)
                self.assertIn('source_product_identity_conflict', identity.issues)
        soup = BeautifulSoup(html, 'html.parser')
        soup.select_one('.product-reference [itemprop=sku]').string = 'OTHER-MPN'
        identity = adapter.extract_identity(str(soup), source['source_url'], '166662')
        self.assertIsNone(identity.manufacturer_part_number)
        self.assertIn('manufacturer_part_number:conflicting_values', identity.issues)

    def test_related_product_nodes_and_conflicting_source_identity_are_not_assigned(self):
        adapter = ProshopAdapter()
        url = 'https://www.proshop.fi/Naeytoenohjaimet/GPU/123'
        nodes = [{'@type': 'Product', 'sku': '999', 'url': url.replace('/123', '/999'), 'gtin13': '4006381333931'},
                 {'@type': 'Product', 'sku': '123', 'url': url, 'gtin13': '4713436175742'}]
        html = '<script type="application/ld+json">' + json.dumps({'@graph': nodes}) + '</script>'
        identity = adapter.extract_identity(html, url, '123')
        self.assertEqual(identity.gtin, '04713436175742')
        nodes[1]['sku'] = '456'
        html = '<script type="application/ld+json">' + json.dumps(nodes) + '</script>'
        identity = adapter.extract_identity(html, url, '123')
        self.assertIsNone(identity.gtin)
        self.assertIn('source_product_identity_conflict', identity.issues)

    def test_raw_roundtrip_preserves_identity_and_leaves_legacy_unknown(self):
        identity = ProductIdentity.from_candidates([('gtin', '036000291452', 'Product JSON-LD:gtin12')])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / 'raw/html/product.html'
            html.parent.mkdir(parents=True)
            html.write_text('source')
            path = RawDataWriter(root).write(shop='Jimms', category='gpu', source_type='product',
                source_url='https://www.jimms.fi/product', raw_path=html,
                items=[RawProduct('GPU', 100, 'https://www.jimms.fi/product', identity=identity)])
            payload = json.loads(path.read_text())
            self.assertEqual(payload['schema_version'], 2)
            restored = RawProduct.from_item(payload['items'][0])
            self.assertEqual(restored.identity, identity)
            self.assertIsNone(RawProduct.from_item({'name': 'Old GPU', 'url': 'https://shop/old'}).identity)


class IdentityWorkflowTests(unittest.TestCase):
    def test_specification_cache_reuse_preserves_ids_and_normaliser_source_evidence(self):
        product = json.loads((FIXTURES / 'proshop/observations.json').read_text())['products'][0]
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', side_effect=AssertionError('network forbidden')) as get:
            root = Path(directory)
            raw, out = root / 'raw', root / 'out'
            html = raw / 'html/proshop' / date.today().isoformat() / (hashlib.sha256(product['source_url'].encode()).hexdigest() + '.html')
            html.parent.mkdir(parents=True)
            original = (FIXTURES / 'proshop/product_3331069.html').read_text()
            html.write_text(original)
            os.utime(html, (1700000000, 1700000000))
            RawDataWriter(root).write(shop='Proshop', category='gpu', source_type='category',
                source_url='https://www.proshop.fi/Naeytoenohjaimet', raw_path=html, page=1,
                items=[RawProduct('ASUS RTX 5090 32GB GDDR7', 100, product['source_url'], external_id='3331069')])
            args = ['specs', '--shop', 'proshop', '--category', 'gpu', '--limit', '1',
                    '--raw-dir', str(raw), '--out', str(out), '--offline']
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(['normalise', '--raw-dir', str(raw), '--out', str(out)]), 0)
            entry = json.loads((out / 'specs.json').read_text())['items'][product['source_url']]
            self.assertEqual(entry['identity']['gtin'], product['ean'].zfill(14))
            self.assertEqual(entry['identity']['manufacturer_part_number'], product['manufacturer_part_number'])
            listing = json.loads((out / 'components.json').read_text())['components'][0]['listings'][0]
            observed = listing['identity_observations'][0]
            report = json.loads((out / 'identity_matches.json').read_text())
            self.assertEqual(report['listings'][0]['identity']['gtin'], entry['identity']['gtin'])
            for field in ProductIdentityMatcher.VARIANT_FIELDS:
                if entry['specs'].get(field) is not None:
                    self.assertEqual(report['listings'][0]['specs'].get(field), entry['specs'][field])
            self.assertEqual(report['listings'][0]['identity_observations'][0]['raw_html'], entry['raw_html'])
            self.assertEqual(observed['identity'], entry['identity'])
            self.assertEqual(observed['fetched_at'], '2023-11-14T22:13:20+00:00')
            self.assertEqual(observed['source_url'], product['source_url'])
            self.assertTrue((root / observed['raw_html']).exists())
            self.assertIn('Product identifier evidence', (out / 'specs_report.md').read_text())
            # Identity remains usable evidence even when the next spec parse is empty.
            soup = BeautifulSoup(original, 'html.parser')
            soup.select_one('#accordionPanel_specs').decompose()
            html.write_text(str(soup))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            retained = json.loads((out / 'specs.json').read_text())['items'][product['source_url']]
            self.assertEqual(retained['last_attempt']['identity']['gtin'], entry['identity']['gtin'])
            get.assert_not_called()

    @staticmethod
    def matching_input(shop, name='Different retailer title', gtin='4719331355579',
                       mpn='GV-N507TWF3OC-16GD', brand='Gigabyte', category='gpu', specs=None):
        candidates = [(field, value, 'test explicit metadata') for field, value in
                      [('gtin', gtin), ('manufacturer_part_number', mpn), ('brand', brand)]
                      if value is not None]
        identity = ProductIdentity.from_candidates(candidates).to_dict()
        return {'category': category, 'raw_name': name, 'specs': specs or {},
                'category_confidence': 'ok', 'listings': [{'shop': shop,
                'url': f'https://{shop.lower()}/product', 'external_id': '123',
                'identity_observations': [{'identity': identity, 'fetched_at': '2026-11-12'}]}]}

    def test_matching_exact_identifiers_ignore_title_spelling_and_retailer_ids(self):
        matcher = ProductIdentityMatcher()
        left = self.matching_input('Datatronic', name='GIGABYTE RTX 5070 Ti')
        right = self.matching_input('Proshop', name='Gigabyte GeForce WindForce OC', brand='GIGABYTE')
        report = matcher.build_report([left, right])
        self.assertEqual(report['decisions'][0]['status'], 'match')
        self.assertEqual(report['decisions'][0]['reasons'], ['exact_gtin'])
        right = self.matching_input('Proshop', gtin=None)
        report = matcher.build_report([left, right])
        self.assertEqual(report['decisions'][0]['reasons'], ['exact_brand_and_manufacturer_part_number'])
        self.assertEqual(report, matcher.build_report([right, left]))

    def test_matching_conflicts_override_positive_identifier(self):
        matcher = ProductIdentityMatcher()
        left = self.matching_input('Datatronic', specs={'vram_gb': 16})
        for change, reason in [({'gtin': '4006381333931'}, 'gtin_conflict'),
                               ({'mpn': 'OTHER-OC'}, 'manufacturer_part_number_conflict'),
                               ({'brand': 'Asus'}, 'brand_conflict'),
                               ({'category': 'cpu'}, 'category_conflict'),
                               ({'specs': {'vram_gb': 8}}, 'specification_conflict:vram_gb')]:
            with self.subTest(change=change):
                report = matcher.build_report([left, self.matching_input('Proshop', **change)])
                decision = report['decisions'][0]
                self.assertEqual(decision['status'], 'conflict')
                self.assertIn(reason, decision['reasons'])

    def test_matching_missing_evidence_never_uses_names_or_retailer_ids(self):
        inputs = [self.matching_input(shop, name='Identical title', gtin=None, mpn=None)
                  for shop in ('Jimms', 'Proshop')]
        report = ProductIdentityMatcher().build_report(inputs)
        self.assertEqual(report['decisions'], [])
        self.assertEqual(report['counts']['without_candidates'], 2)
        self.assertEqual(report['mode'], 'review_only')

    def test_matching_historical_conflicts_and_special_offers_require_review(self):
        matcher = ProductIdentityMatcher()
        left = self.matching_input('Jimms')
        old = self.matching_input('Jimms', gtin='4006381333931')
        report = matcher.build_report([left, old, self.matching_input('Proshop')])
        self.assertEqual(report['decisions'][0]['status'], 'review')
        listing = next(item for item in report['listings'] if item['shop'] == 'jimms')
        self.assertIsNone(listing['identity']['gtin'])
        self.assertIn('gtin:conflicting_observations', listing['identity']['issues'])
        self.assertEqual(len(listing['identity_observations']), 2)
        for name in ('RTX GPU bundle', 'GPU DEMO', 'GPU refurbished', 'GPU tray'):
            report = matcher.build_report([self.matching_input('Jimms', name=name), self.matching_input('Proshop')])
            self.assertEqual(report['decisions'][0]['status'], 'review')

    def test_matching_saved_datatronic_and_proshop_evidence(self):
        source = json.loads((FIXTURES / 'datatronic/product_identity.source.json').read_text())
        datatronic = DatatronicAdapter().extract_identity(
            (FIXTURES / 'datatronic/product_identity.html').read_text(), source['source_url'], '166662')
        product = next(item for item in json.loads((FIXTURES / 'proshop/observations.json').read_text())['products']
                       if item['external_id'] == '3331106')
        proshop = ProshopAdapter().extract_identity((FIXTURES / 'proshop/product_3331106.html').read_text(),
                                                  product['source_url'], '3331106')
        inputs = []
        for shop, identity, url in [('Datatronic', datatronic, source['source_url']),
                                    ('Proshop', proshop, product['source_url'])]:
            item = self.matching_input(shop)
            item['listings'][0]['url'] = url
            item['listings'][0]['identity_observations'] = [{'identity': identity.to_dict(), 'source_url': url}]
            inputs.append(item)
        report = ProductIdentityMatcher().build_report(inputs)
        self.assertEqual(report['decisions'][0]['status'], 'match')
        self.assertTrue(all(item['identity_observations'][0]['source_url'] == item['url'] for item in report['listings']))

    def test_verified_group_requires_every_pair_and_is_order_independent(self):
        inputs = [self.matching_input(shop) for shop in ('Jimms', 'Datatronic', 'Proshop')]
        expected = None
        for ordered in itertools.permutations(inputs):
            report = VerifiedProductGrouper().plan(ProductIdentityMatcher().build_report(ordered))
            self.assertEqual(report['groups'][0]['listings'], [0, 1, 2])
            self.assertEqual(report['groups'][0]['status'], 'verified')
            self.assertEqual(report['counts']['verified_groups'], 1)
            if expected is None:
                expected = report
            self.assertEqual(report, expected)

    def test_partial_identifier_bridge_and_duplicate_shop_offers_do_not_merge(self):
        left = self.matching_input('Jimms')
        bridge = self.matching_input('Datatronic', gtin=None)
        conflicting = self.matching_input('Proshop', gtin='4006381333931')
        duplicate = self.matching_input('Jimms')
        duplicate['listings'][0]['url'] += '-another-offer'
        for inputs in ([left, bridge, conflicting], [left, duplicate, self.matching_input('Proshop')]):
            for ordered in itertools.permutations(inputs):
                report = VerifiedProductGrouper().plan(ProductIdentityMatcher().build_report(ordered))
                self.assertEqual(report['counts']['verified_groups'], 0)
                self.assertEqual(report['counts']['ambiguous_groups'], 1)
                self.assertEqual(len(report['groups']), 3)
                self.assertTrue(all(group['status'] == 'review' for group in report['groups']))

    def test_normalisation_groups_verified_saved_pair_preserving_price_history_and_conflicting_specs(self):
        source = json.loads((FIXTURES / 'datatronic/product_identity.source.json').read_text())
        identity = DatatronicAdapter().extract_identity(
            (FIXTURES / 'datatronic/product_identity.html').read_text(), source['source_url'], '166662')
        product = next(item for item in json.loads((FIXTURES / 'proshop/observations.json').read_text())['products']
                       if item['external_id'] == '3331106')
        other = ProshopAdapter().extract_identity((FIXTURES / 'proshop/product_3331106.html').read_text(),
                                                 product['source_url'], '3331106')
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', side_effect=AssertionError('network forbidden')):
            root = Path(directory)
            raw, out = root / 'raw', root / 'out'
            raw.mkdir(); out.mkdir()
            entries = [('a', 'Datatronic', source['source_url'], '166662', 'GIGABYTE RTX 5070 Ti 16GB GDDR7', 100, identity, '2026-11-11'),
                       ('b', 'Datatronic', source['source_url'], '166662', 'GIGABYTE RTX 5070 Ti 16GB GDDR7', None, identity, '2026-11-12'),
                       ('c', 'Proshop', product['source_url'], '3331106', 'Gigabyte GeForce RTX 5070 Ti WindForce 16GB GDDR7', 200, other, '2026-11-12')]
            for filename, shop, url, external_id, name, price, ident, timestamp in entries:
                (raw / f'{filename}.json').write_text(json.dumps({'shop': shop, 'category': 'gpu',
                    'fetched_at': timestamp, 'items': [{'name': name, 'url': url, 'external_id': external_id,
                    'price_cents': price}]}))
            # Both identities come from already saved product responses, not raw prices.
            store = {'items': {url: {'shop': shop, 'category': 'gpu', 'status': 'ok',
                'fetched_at': timestamp, 'identity': ident.to_dict(), 'raw_html': f'raw/html/{shop}.html',
                'specs': {'power_w': power, 'vram_gb': 16}}
                for shop, url, ident, timestamp, power in [('Datatronic', source['source_url'], identity, '2026-11-12', 300),
                                                         ('Proshop', product['source_url'], other, '2026-11-12', 310)]}}
            (out / 'specs.json').write_text(json.dumps(store))
            before = {path: path.read_bytes() for path in [*raw.glob('*.json'), out / 'specs.json']}
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['normalise', '--raw-dir', str(raw), '--out', str(out)]), 0)
            result = json.loads((out / 'components.json').read_text())
            self.assertEqual(result['component_count'], 1)
            component = result['components'][0]
            self.assertEqual(component['identity_match']['status'], 'verified')
            listings = {item['shop']: item for item in component['listings']}
            self.assertIsNone(listings['Datatronic']['price_cents'])
            self.assertEqual(listings['Datatronic']['last_known_price_cents'], 100)
            self.assertEqual(listings['Datatronic']['external_id'], '166662')
            self.assertEqual(listings['Proshop']['external_id'], '3331106')
            self.assertEqual(listings['Proshop']['price_cents'], 200)
            self.assertIsNone(component['specs']['power_w'])
            self.assertEqual({item['value'] for item in component['spec_conflicts']['power_w']}, {300, 310})
            self.assertTrue(all(item['identity_observations'][0]['raw_html'] for item in listings.values()))
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            report = json.loads((out / 'identity_matches.json').read_text())
            self.assertEqual(report['counts']['verified_groups'], 1)

    def test_identical_titles_with_conflicting_gtins_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'; raw.mkdir()
            for shop, gtin in [('Jimms', '4719331355579'), ('Proshop', '4006381333931')]:
                identity = ProductIdentity.from_candidates([('gtin', gtin, 'test'),
                    ('brand', 'Gigabyte', 'test'), ('manufacturer_part_number', 'SAME-MPN', 'test')])
                (raw / f'{shop}.json').write_text(json.dumps({'shop': shop, 'category': 'gpu',
                    'fetched_at': '2026-11-12', 'items': [{'name': 'Gigabyte RTX 5070 Ti 16GB GDDR7',
                    'url': f'https://{shop}/product', 'price_cents': 100, 'identity': identity.to_dict()}]}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['normalise', '--raw-dir', str(raw), '--out', str(root / 'out')]), 0)
            result = json.loads((root / 'out/components.json').read_text())
            self.assertEqual(result['component_count'], 2)
            self.assertTrue(all(item['identity_match']['status'] == 'conflict' for item in result['components']))

    def test_same_shop_distinct_urls_are_not_merged_by_gtin_or_title(self):
        identity = ProductIdentity.from_candidates([('gtin', '4713436175742', 'verified sample')])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / 'raw/html/category.html'
            html.parent.mkdir(parents=True)
            html.write_text('saved category')
            items = [RawProduct(name, 100, f'https://shop/{index}', identity=identity) for index, name in enumerate([
                'MSI RTX 5070 12GB GDDR7', 'MSI GeForce RTX 5070 12GB GDDR7'])]
            RawDataWriter(root).write(shop='Sample', category='gpu', source_type='category',
                source_url='https://shop/gpu', raw_path=html, page=1, items=items)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['normalise', '--raw-dir', str(root / 'raw'), '--out', str(root / 'out')]), 0)
            result = json.loads((root / 'out/components.json').read_text())
            self.assertEqual(result['component_count'], 2)
            report = json.loads((root / 'out/identity_matches.json').read_text())
            self.assertEqual(report['mode'], 'verified_grouping')
            self.assertEqual(len(report['listings']), 2)
            self.assertTrue(all(item['identity']['gtin'] == identity.gtin for item in report['listings']))
            self.assertTrue(all(component['listings'][0]['identity_observations'] for component in result['components']))


if __name__ == '__main__':
    unittest.main()
