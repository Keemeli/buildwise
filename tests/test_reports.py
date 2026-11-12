"""Specification coverage report configuration."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.pipeline.reports import SpecificationReportWriter



class SpecificationReportTests(unittest.TestCase):
    def test_specification_report_uses_supplied_retailer_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SpecificationReportWriter({'gpu': {'custom_field': ['Custom label']}})
            store = {'items': {'url': {'category': 'gpu', 'status': 'ok',
                                      'specs': {'custom_field': 42}}}}
            report = writer.write(Path(directory), store).read_text()
            self.assertIn('custom_field', report)
            self.assertNotIn('recommended_psu_w', report)


if __name__ == '__main__':
    unittest.main()
