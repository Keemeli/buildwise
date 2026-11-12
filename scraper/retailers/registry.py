"""Resolve retailer keys to adapter instances; workers need no concrete imports."""
from collections.abc import Callable, Mapping

from scraper.retailers.contracts import RetailerAdapter


class RetailerRegistry:
    def __init__(self, factories: Mapping[str, Callable[[], RetailerAdapter]]):
        self._factories = dict(factories)

    def get(self, key: str) -> RetailerAdapter:
        try:
            factory = self._factories[key.strip().lower()]
        except KeyError:
            raise ValueError(f'unknown retailer: {key}') from None
        return factory()

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._factories)


def default_registry() -> RetailerRegistry:
    """Keep command help and export usable without HTML parsing dependencies."""
    def datatronic():
        from scraper.retailers.datatronic import DatatronicAdapter
        return DatatronicAdapter()

    def jimms():
        from scraper.retailers.jimms import JimmsAdapter
        return JimmsAdapter()

    def proshop():
        from scraper.retailers.proshop import ProshopAdapter
        return ProshopAdapter()

    return RetailerRegistry({'datatronic': datatronic, 'jimms': jimms, 'proshop': proshop})
