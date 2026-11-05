"""BuildWise — Jimms product-page metadata parser (issue #7).

    Primary price: meta[property="product:price:amount"]
    Fallback price: [itemprop="price"]

Missing data is reported, never invented. This parser does not fetch pages or
extract hardware specifications. Selectors must be checked against live samples.
"""

from bs4 import BeautifulSoup
from scraper.common.prices import parse_price_cents

SHOP = "Jimms"
HOSTS = {"jimms.fi", "www.jimms.fi"}


# Category URLs observed in Jimms public navigation. Other categories can use
# an explicit --url until their paths have been verified.
CATEGORY_URLS = {
    "gpu": "https://www.jimms.fi/fi/Product/List/000-00P/komponentit--naytonohjaimet",
    "cpu": "https://www.jimms.fi/fi/Product/List/000-00R/komponentit--prosessorit",
}


class JimmsParser:
    """Own Jimms selectors and allowed hosts; performs no network access."""

    def __init__(self, hosts: set[str] | None = None):
        self.hosts = set(HOSTS if hosts is None else hosts)

    def parse_product(self, html: str) -> dict:
        """Return name + price, rejecting missing, invalid or conflicting metadata."""
        soup = BeautifulSoup(html, "html.parser")
        name = None
        for selector in ('h1[itemprop="name"]', 'h1', 'meta[property="og:title"]'):
            element = soup.select_one(selector)
            if element:
                name = " ".join((element.get("content") or element.get_text(" ", strip=True)).split())
                if name:
                    break
        if not name:
            raise ValueError("missing product name")

        currencies = {str(el.get("content") or el.get_text(strip=True)).strip().upper()
                      for el in soup.select('meta[property="product:price:currency"], [itemprop="priceCurrency"]')}
        if currencies and currencies != {"EUR"}:
            raise ValueError(f"unsupported or conflicting currency: {sorted(currencies)}")

        prices = []
        methods = []
        for selector in ('meta[property="product:price:amount"]', '[itemprop="price"]'):
            for element in soup.select(selector):
                raw = element.get("content") or element.get("value") or element.get_text(" ", strip=True)
                price = parse_price_cents(raw)
                if price is None:
                    raise ValueError(f"invalid price metadata: {raw!r}")
                prices.append(price)
                methods.append(selector)
        if not prices:
            raise ValueError("missing price metadata")
        if len(set(prices)) != 1:
            raise ValueError("conflicting price metadata")
        return {"name": name, "price_cents": prices[0], "extraction": methods[0]}

    def parse_category(self, html: str, source_url: str) -> list[str]:
        """Read only the actual listing, excluding menus and recommended products.

        Jimms currently renders product-box links inside #initproductlist in the
        initial HTML, even though its pagination controls use JavaScript.
        """
        from urllib.parse import urljoin, urlsplit, urlunsplit
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one('#initproductlist')
        if container is None:
            raise ValueError("missing Jimms category listing #initproductlist")
        urls = []
        for anchor in container.select('product-box a[href]'):
            parsed = urlsplit(urljoin(source_url, anchor['href']))
            if (parsed.scheme != 'https' or parsed.hostname not in self.hosts
                    or not parsed.path.startswith('/fi/Product/Show/')):
                continue
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
            if url not in urls:
                urls.append(url)
        if not urls:
            raise ValueError("no product links found; inspect cached category HTML")
        return urls


def parse_product(html: str) -> dict:
    """Compatibility function; delegate to JimmsParser."""
    return JimmsParser().parse_product(html)


def parse_category(html: str, source_url: str) -> list[str]:
    """Compatibility function; delegate to JimmsParser."""
    return JimmsParser().parse_category(html, source_url)
