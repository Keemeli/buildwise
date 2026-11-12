"""Shared exact price conversion."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.common.prices import parse_price_cents



class PriceParsingTests(unittest.TestCase):
    def test_exact_cents(self):
        self.assertEqual(parse_price_cents('0,29 €'), 29)
        for value in ('-1', 'NaN', '0', '1.234', '1,234.56'):
            self.assertIsNone(parse_price_cents(value))


if __name__ == '__main__':
    unittest.main()
