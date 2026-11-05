"""Regression checks for object workers and preserved function/CLI interfaces."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / 'scraper'
sys.path.insert(0, str(ROOT))
from scraper.retailers.jimms import JimmsParser, parse_product
from scraper.retailers.datatronic import DatatronicParser
from scraper.workers.jimms import JimmsPriceScraper
from scraper.workers.jimms import JimmsCategoryDiscovery
from scraper.pipeline.export import CatalogueExporter
from scraper.pipeline.refresh import RefreshPipeline
from scraper.workers.datatronic import DatatronicScraper
from scraper.workers import specifications as specs

PRODUCT_HTML = '<h1>MSI RTX 5070</h1><meta property="product:price:amount" content="299.99">'
LISTING_HTML = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
                '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
                '<span class="price">299,99 €</span></article></div><p>Yhteensä 1 tuotetta</p>')
CATEGORY_HTML = ('<div id="initproductlist"><product-box>'
                 '<a href="/fi/Product/Show/123/gpu">GPU</a></product-box></div>')


def options(**updates):
    values = dict(skip_scrape=False, skip_specs=False, cold=False, pages=1, delay=1.0,
                  jimms_input=None, jimms_category_url=None)
    values.update(updates)
    return argparse.Namespace(**values)


class ObjectWorkerTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

    def test_parser_configuration_is_instance_local(self):
        custom = DatatronicParser('https://example.com')
        default = DatatronicParser()
        self.assertEqual(custom.parse_listing(LISTING_HTML)[0][0]['url'], 'https://example.com/gpu')
        self.assertEqual(default.parse_listing(LISTING_HTML)[0][0]['url'], 'https://datatronic.fi/gpu')
        self.assertEqual(JimmsParser().parse_product(PRODUCT_HTML), parse_product(PRODUCT_HTML))
        parser = JimmsParser({'example.com'})
        self.assertEqual(parser.parse_category(CATEGORY_HTML, 'https://example.com/list'),
                         ['https://example.com/fi/Product/Show/123/gpu'])

    def test_jimms_price_run_preserves_partial_success_and_closes_fetcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached = root / 'data/raw/html/product.html'
            cached.parent.mkdir(parents=True)
            cached.write_text(PRODUCT_HTML)
            fetcher = Mock()
            fetcher.fetch.side_effect = [(PRODUCT_HTML, cached, 'cache'), ValueError('missing price')]
            manifest = [{'category': 'gpu', 'url': f'https://www.jimms.fi/product/{i}'} for i in range(2)]
            self.assertEqual(JimmsPriceScraper(manifest, root, fetcher).run(), 1)
            fetcher.close.assert_called_once()
            payload = json.loads(next((root / 'raw').glob('jimms_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            log = json.loads((root / 'raw/scrape_runs.jsonl').read_text())
            self.assertEqual(log['status'], 'partial')
            self.assertEqual(len(log['failures']), 1)

    def test_category_worker_writes_existing_manifest_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'manifest.json'
            fetcher = Mock()
            fetcher.fetch.return_value = (CATEGORY_HTML, Path(directory) / 'cache.html', 'cache')
            opts = options(url='https://www.jimms.fi/fi/Product/List/gpu', category='gpu', output=output)
            self.assertEqual(JimmsCategoryDiscovery(opts, fetcher).run(), 0)
            self.assertEqual(json.loads(output.read_text()), [
                {'category': 'gpu', 'url': 'https://www.jimms.fi/fi/Product/Show/123/gpu'}])
            fetcher.close.assert_called_once()

    def test_datatronic_worker_outputs_same_payload_and_closes_fetcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached = root / 'data/raw/html/product.html'
            cached.parent.mkdir(parents=True)
            cached.write_text(LISTING_HTML)
            fetcher = Mock()
            fetcher.fetch.return_value = (LISTING_HTML, cached, 'cache')
            worker = DatatronicScraper(['gpu'], project_root=root, fetcher=fetcher)
            self.assertEqual(worker.run(), 0)
            fetcher.close.assert_called_once()
            payload = json.loads(next((root / 'data/raw').glob('datatronic_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            self.assertEqual(payload['raw_html'], 'raw/html/product.html')

    def test_datatronic_failure_is_logged_and_fetcher_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher = Mock()
            fetcher.fetch.side_effect = ValueError('robots.txt disallows URL')
            worker = DatatronicScraper(['gpu'], project_root=Path(directory), fetcher=fetcher)
            self.assertEqual(worker.run(), 1)
            fetcher.close.assert_called_once()
            self.assertEqual(json.loads(worker.run_log.read_text())['status'], 'failed')

    def test_specification_reparse_is_offline_and_keeps_output_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            url = 'https://datatronic.fi/gpu'
            (raw / 'gpu.json').write_text(json.dumps({'shop': 'Datatronic', 'category': 'gpu',
                'items': [{'url': url, 'name': 'GPU', 'external_id': '42'}]}))
            opts = argparse.Namespace(raw_dir=raw, out=root / 'out', category=None, limit=None,
                delay=1, force=False, reparse=True, status=False, checkpoint_every=1)
            session = Mock()
            with patch.object(specs, 'CACHE_DIR', root / 'cache'):
                cached = specs.cache_path(url, '42', specs.date.today().isoformat())
                cached.parent.mkdir(parents=True)
                cached.write_text('<script>{"features": [{"name": "Tehonkulutus (maks.)", "value": "180 W"}]}</script>')
                self.assertEqual(specs.DatatronicSpecExtractor(opts, session=session).run(), 0)
            session.get.assert_not_called()
            session.close.assert_called_once()
            entry = json.loads((opts.out / 'specs.json').read_text())['items'][url]
            self.assertEqual(entry['status'], 'ok')
            self.assertEqual(entry['specs']['power_w'], 180)
            self.assertTrue((opts.out / 'specs_report.md').exists())

    def test_pipeline_cold_and_jimms_stage_planning(self):
        pipeline = RefreshPipeline(options(cold=True, jimms_category_url='https://www.jimms.fi/fi/Product/List/gpu'),
                                   ['gpu'], ['datatronic', 'jimms'])
        stages = pipeline.build_stages()
        self.assertEqual([name for name, _ in stages], [
            'datatronic-gpu', 'jimms-collect', 'datatronic-specs', 'normalise', 'export'])
        self.assertIn('--force', dict(stages)['datatronic-specs'])

    def test_pipeline_stops_before_export_on_worker_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = Mock(return_value={'ok': False, 'last_lines': ['failed']})
            pipeline = RefreshPipeline(options(skip_specs=True), ['gpu'], ['datatronic'],
                stage_runner=runner, project_root=root, log_path=root / 'refresh.jsonl')
            self.assertEqual(pipeline.run(), 1)
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(json.loads((root / 'refresh.jsonl').read_text())['status'], 'failed at datatronic-gpu')

    def test_export_detects_price_change_with_unchanged_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source.json', root / 'target.json'
            payload = {'generated_at': 'today', 'component_count': 1, 'components': [{'price_cents': 100}]}
            source.write_text(json.dumps(payload))
            payload['components'][0]['price_cents'] = 200
            target.write_text(json.dumps(payload))
            exporter = CatalogueExporter(source, target, root)
            self.assertEqual(exporter.run(check=True), 1)
            self.assertEqual(exporter.run(), 0)
            self.assertEqual(exporter.run(check=True), 0)



if __name__ == '__main__':
    unittest.main()
