"""Offline checks for the Jimms price proof; no retailer traffic required."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.common.fetching import PageFetcher
from scraper.common.prices import parse_price_cents
from scraper.retailers.jimms import parse_product


class JimmsTests(unittest.TestCase):
    def test_metadata_and_fallback(self):
        for markup in ('<meta property="product:price:amount" content="1234.56">',
                       '<span itemprop="price" content="1 234,56"></span>'):
            result = parse_product('<h1>Example GPU</h1>' + markup)
            self.assertEqual((result['name'], result['price_cents']), ('Example GPU', 123456))

    def test_invalid_pages(self):
        for html in ('<h1>GPU</h1>', '<meta itemprop="price" content="10">',
                     '<h1>GPU</h1><meta itemprop="price" content="free">',
                     '<h1>GPU</h1><meta itemprop="price" content="10"><meta itemprop="price" content="20">',
                     '<h1>GPU</h1><meta itemprop="price" content="10"><meta itemprop="priceCurrency" content="USD">'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_product(html)

    def test_exact_cents(self):
        self.assertEqual(parse_price_cents('0,29 €'), 29)
        for value in ('-1', 'NaN', '0', '1.234', '1,234.56'):
            self.assertIsNone(parse_price_cents(value))

    def test_cache_and_throttle_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher = PageFetcher(Path(directory), 'jimms', {'www.jimms.fi'})
            response = Mock(status_code=200, is_redirect=False, is_permanent_redirect=False,
                            apparent_encoding='utf-8', text='<h1>GPU</h1>')
            import requests
            with patch.object(fetcher.session, 'get', side_effect=[Mock(status_code=404), requests.Timeout('timeout'), response]) as get:
                with patch('scraper.common.fetching.time.sleep') as sleep:
                    with self.assertRaises(requests.Timeout):
                        fetcher.fetch('https://www.jimms.fi/product')
                    fetcher.fetch('https://www.jimms.fi/product')
                    self.assertTrue(sleep.called)
                    self.assertEqual(fetcher.fetch('https://www.jimms.fi/product')[2], 'cache')
                    self.assertEqual(get.call_count, 3)
            fetcher.close()

    def test_robots_disallow_and_delay(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher = PageFetcher(Path(directory), 'jimms', {'www.jimms.fi'})
            robots = Mock(status_code=200, text='User-agent: *\nDisallow: /private\nCrawl-delay: 3\n')
            with patch.object(fetcher.session, 'get', return_value=robots) as get:
                with self.assertRaisesRegex(ValueError, 'disallows'):
                    fetcher.fetch('https://www.jimms.fi/private/product')
                self.assertEqual(fetcher._check_robots('https://www.jimms.fi/public'), 3)
                self.assertEqual(get.call_count, 1)
            fetcher.close()

    def test_robots_unavailable_blocks_host(self):
        import requests
        for response in (Mock(status_code=503), Mock(status_code=403),
                         Mock(status_code=302), requests.Timeout('timeout')):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory:
                fetcher = PageFetcher(Path(directory), 'jimms', {'www.jimms.fi'})
                options = {'side_effect': response} if isinstance(response, Exception) else {'return_value': response}
                with patch.object(fetcher.session, 'get', **options) as get:
                    for _ in range(2):
                        with self.assertRaisesRegex(ValueError, 'robots check unavailable'):
                            fetcher.fetch('https://www.jimms.fi/product')
                    self.assertEqual(get.call_count, 1)
                fetcher.close()

    def test_offline_cli_output_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            url = 'https://www.jimms.fi/product'
            fetcher = PageFetcher(root / 'raw' / 'html', 'jimms', {'www.jimms.fi'})
            import hashlib
            fetcher.cache_dir.mkdir(parents=True)
            (fetcher.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_text(
                '<h1>Example GPU</h1><meta property="product:price:amount" content="299.99">')
            fetcher.close()
            manifest = root / 'urls.json'
            manifest.write_text(json.dumps([{'category': 'gpu', 'url': url}]))
            result = subprocess.run([sys.executable, '-B', '-m', 'scraper', 'collect', '--shop', 'jimms',
                                     '--input', str(manifest), '--data-dir', str(root), '--offline'],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(next((root / 'raw').glob('jimms_*.json')).read_text())
            self.assertEqual(payload['shop'], 'Jimms')
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            self.assertEqual(payload['origin'], 'cache')


if __name__ == '__main__':
    unittest.main()
