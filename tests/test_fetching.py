"""Shared fetching, robots rules, throttling and HTML cache."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.common.fetching import PageFetcher



class SharedFetchingTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
