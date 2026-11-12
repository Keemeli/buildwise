"""Check package boundaries and independently configurable collaborators."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.config import PROJECT_ROOT, RAW_DIR, NORMALISED_DIR
from scraper.pipeline.components import ComponentNameParser
from scraper.pipeline.normalisation import ComponentNormaliser
from scraper.pipeline.reports import SpecificationReportWriter


class PackageStructureTests(unittest.TestCase):
    def test_paths_resolve_to_project_not_worker_directory(self):
        self.assertEqual(PROJECT_ROOT, ROOT)
        self.assertEqual(RAW_DIR, ROOT / 'data/raw')
        self.assertEqual(NORMALISED_DIR, ROOT / 'data/normalised')

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

    def test_specification_report_uses_supplied_retailer_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SpecificationReportWriter({'gpu': {'custom_field': ['Custom label']}})
            store = {'items': {'url': {'category': 'gpu', 'status': 'ok',
                                      'specs': {'custom_field': 42}}}}
            report = writer.write(Path(directory), store).read_text()
            self.assertIn('custom_field', report)
            self.assertNotIn('recommended_psu_w', report)

    def test_unified_commands_accept_help(self):
        for name in ('collect', 'specs', 'normalise', 'export', 'refresh'):
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, '-B', '-m', 'scraper', name, '--help'],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
