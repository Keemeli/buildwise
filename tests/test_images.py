"""Product images recovered from the cached listing and product pages."""
import tempfile
import unittest
from pathlib import Path

from scraper.pipeline.images import extract_product_pages, image_for, images_from_page, load

CARD_PLAIN = ('<article data-id-product="111"><a href="x">'
              '<img src = "https://datatronic.fi/100-home_default/geforce-rtx-5070.jpg" alt="a">'
              '</a></article>')
CARD_LAZY = ('<article data-id-product="222"><a href="y">'
             '<img data-src="https://datatronic.fi/200-home_default/ryzen-7-9800x3d.jpg">'
             '</a></article>')
CARD_SRCSET = ('<article data-id-product="333">'
               '<img data-srcset="https://datatronic.fi/300-home_default/ssd-990-pro.jpg 1x, '
               'https://datatronic.fi/300-large_default/ssd-990-pro.jpg 2x"></article>')
PLACEHOLDER = ('<article data-id-product="444">'
               '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw="></article>')
SITE_ASSET = ('<article data-id-product="555">'
              '<img src="https://datatronic.fi/img/cms/logo.png"></article>')


class ImageExtractionTests(unittest.TestCase):
    def test_each_card_keeps_its_own_image(self):
        found = images_from_page(CARD_PLAIN + CARD_LAZY + CARD_SRCSET)
        self.assertEqual(found, {
            '111': 'https://datatronic.fi/100-home_default/geforce-rtx-5070.jpg',
            '222': 'https://datatronic.fi/200-home_default/ryzen-7-9800x3d.jpg',
            '333': 'https://datatronic.fi/300-home_default/ssd-990-pro.jpg',
        })

    def test_placeholders_and_site_assets_are_not_product_images(self):
        self.assertEqual(images_from_page(PLACEHOLDER + SITE_ASSET), {})

    def test_spaces_around_the_attribute_sign_are_tolerated(self):
        # The shop writes `src = "..."`; a scraper that expects `src="` finds nothing.
        self.assertIn('111', images_from_page(CARD_PLAIN))

    def test_image_for_prefers_a_listing_that_has_one(self):
        component = {'listings': [{'external_id': '999'}, {'external_id': '222'}]}
        self.assertEqual(image_for(component, {'222': 'https://x/222.jpg'}), 'https://x/222.jpg')
        self.assertIsNone(image_for(component, {}))
        self.assertIsNone(image_for({'listings': []}, {'222': 'https://x/222.jpg'}))

    def test_a_missing_file_means_no_images_not_a_crash(self):
        self.assertEqual(load(Path('/nonexistent/images.json')), {})


PAGE_WITH_IMAGE = (
    '<html><head>'
    '<link rel="canonical" href="https://datatronic.fi/komponentit/kotelot/fractal-pop-xl">'
    '<meta property="og:image" content="https://datatronic.fi/629824-large_default/fractal-pop-xl.jpg">'
    '</head><body></body></html>')
# 313 of the 314 rows the listing pages left without a picture turned out to be exactly this:
# the shop's own page publishes an empty og:image, so there is no picture to borrow.
PAGE_EMPTY_IMAGE = (
    '<html><head>'
    '<link rel="canonical" href="https://datatronic.fi/komponentit/muistit/kingston-fury">'
    '<meta property="og:image" content="">'
    '</head><body>'
    '<img src="https://datatronic.fi/451032-home_default/corsair-rm850x.jpg">'  # a related product
    '</body></html>')


class ProductPageImageTests(unittest.TestCase):
    def test_a_product_page_gives_its_picture_in_the_list_size(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '2026-11-27').mkdir()
            (root / '2026-11-27' / 'a.html').write_text(PAGE_WITH_IMAGE)
            (root / '2026-11-27' / 'b.html').write_text(PAGE_EMPTY_IMAGE)
            payload = extract_product_pages(root, root / 'out.json', pattern='**/*.html')
        self.assertEqual(
            payload['images'],
            {'https://datatronic.fi/komponentit/kotelot/fractal-pop-xl':
             'https://datatronic.fi/629824-home_default/fractal-pop-xl.jpg'})

    def test_an_empty_picture_and_a_related_product_are_not_taken(self):
        """The page above shows another product's photo; nothing from it may be used."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.html').write_text(PAGE_EMPTY_IMAGE)
            payload = extract_product_pages(root, root / 'out.json')
        self.assertEqual(payload['images'], {})

    def test_image_for_falls_back_to_the_product_page_map(self):
        component = {'listings': [{'external_id': '999', 'url': 'https://datatronic.fi/x/y/'}]}
        page_map = {'https://datatronic.fi/x/y': 'https://datatronic.fi/1-home_default/y.jpg'}
        self.assertIsNone(image_for(component, {'111': 'https://x/111.jpg'}))
        self.assertEqual(image_for(component, {}, page_map), 'https://datatronic.fi/1-home_default/y.jpg')
        self.assertEqual(
            image_for(component, {'999': 'https://x/999.jpg'}, page_map), 'https://x/999.jpg')


if __name__ == '__main__':
    unittest.main()
