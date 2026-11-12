"""Shared synthetic HTML and HTTP responses; no test cases or live requests.

Datatronic/Jimms card builders serve shared-policy tests. Real retailer markup
belongs in fixtures/. Keep assertion logic in test modules.
"""
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]


def product_url(adapter, number=123):
    return (f'https://datatronic.fi/gpu-{number}' if adapter.config.key == 'datatronic'
            else f'https://www.jimms.fi/fi/Product/Show/{number}/gpu')


def card(adapter, price='299,99 €', number=123):
    url = product_url(adapter, number)
    if adapter.config.key == 'datatronic':
        amount = f'<span class="price">{price}</span>' if price is not None else ''
        return (f'<article class="product-miniature" data-id-product="{number}">'
                f'<h3 class="product-title"><a href="{url}">MSI RTX 5070 12GB GDDR7</a></h3>{amount}</article>')
    amount = f'<span class="price__amount">{price}</span>' if price is not None else ''
    return (f'<product-box><h5 class="product-box-name"><a href="{url}">MSI RTX 5070 12GB GDDR7</a></h5>'
            f'<div class="product-box-sku">SKU-{number}</div>{amount}</product-box>')


def listing(adapter, price='299,99 €', number=123, extra='', total=100):
    identity = 'js-product-list' if adapter.config.key == 'datatronic' else 'initproductlist'
    return f'<div id="{identity}">{card(adapter, price, number)}{extra}</div><p>Yhteensä {total} tuotetta</p>'


def product_page(price='299.99'):
    metadata = f'<meta property="product:price:amount" content="{price}">' if price is not None else ''
    return '<h1>MSI RTX 5070 12GB GDDR7</h1>' + metadata


def response(text, url='', status=200):
    item = requests.Response()
    item.status_code, item.url, item.encoding = status, url, 'utf-8'
    item._content = text.encode('utf-8')
    return item
