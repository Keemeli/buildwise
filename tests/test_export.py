"""Catalogue export and complete-content drift detection."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.pipeline.export import CatalogueExporter



class CatalogueExportTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

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
