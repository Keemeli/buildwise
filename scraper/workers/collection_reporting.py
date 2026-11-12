"""Collection outcome policy and reporting; no retry execution."""
from dataclasses import asdict, dataclass
import requests

from scraper.common.fetching import RobotsDisallowedError, RobotsUnavailableError
from scraper.retailers.contracts import UnsupportedOperationError


@dataclass
class CollectionCounters:
    category_pages_planned: int = 0
    category_pages_attempted: int = 0
    category_pages_processed: int = 0
    product_followups_attempted: int = 0
    source_responses: int = 0
    cache_hits: int = 0
    network_responses: int = 0
    source_failures: int = 0
    unique_products_identified: int = 0
    observations_saved: int = 0
    priced_observations: int = 0
    null_price_observations: int = 0
    duplicates_skipped: int = 0
    recovered_issues: int = 0
    unresolved_outcomes: int = 0
    excluded_products: int = 0


@dataclass(frozen=True)
class CollectionOutcome:
    run_id: str
    shop: str
    stage: str
    category: str
    url: str
    source_url: str
    reason: str
    retry_classification: str
    error: str
    external_id: str | None = None
    retailer_sku: str | None = None
    page: int | None = None


def classify_problem(error=None, *, reason='missing_price', stage='parse') -> tuple[str, str]:
    """Return (reason code, retry classification), without scheduling a retry."""
    if isinstance(error, RobotsDisallowedError):
        return 'robots_disallowed', 'blocked'
    if isinstance(error, RobotsUnavailableError):
        status = error.status_code
        if status == 429 or (status is not None and status >= 500) or isinstance(
                error.cause, (requests.Timeout, requests.ConnectionError)):
            return 'robots_unavailable', 'retryable'
        return 'robots_unavailable', 'inspect'
    if isinstance(error, UnsupportedOperationError):
        return 'unsupported_operation', 'blocked'
    if isinstance(error, FileNotFoundError) and stage == 'fetch':
        return 'offline_cache_missing', 'retryable'
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return 'connection_failure', 'retryable'
    if isinstance(error, requests.HTTPError) and error.response is not None:
        status = error.response.status_code
        if status in (404, 410):
            return f'http_{status}', 'unavailable'
        return f'http_{status}', 'retryable' if status == 429 or status >= 500 else 'inspect'
    if error is not None:
        return ('write_error' if stage == 'write' else 'parse_error' if stage == 'parse'
                else 'fetch_error'), 'inspect'
    return reason, 'retryable' if reason in {'missing_price', 'offline_cache_missing'} else 'inspect'


@dataclass(frozen=True)
class CollectionResult:
    run_id: str
    shop: str
    categories: tuple[str, ...]
    pages_fetched: int
    products_fetched: int
    items_found: int
    duplicates_skipped: int
    started_at: str
    finished_at: str
    failures: tuple[CollectionOutcome, ...]
    issues: tuple
    recovered: tuple[CollectionOutcome, ...]
    counters: CollectionCounters
    coverage: tuple[dict, ...]
    exclusions: tuple[dict, ...] = ()

    @property
    def status(self) -> str:
        return ('partial' if self.items_found else 'failed') if self.failures else 'ok'

    @property
    def exit_code(self) -> int:
        return 1 if self.failures else 0

    def to_dict(self) -> dict:
        return {'report_version': 2, **asdict(self), 'status': self.status, 'exit_code': self.exit_code}
