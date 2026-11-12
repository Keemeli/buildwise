"""Explicit, bounded retries using the existing collection pipeline."""
from datetime import datetime, timezone
import fcntl
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from scraper.common.fetching import PageFetcher
from scraper.retailers.contracts import ProductRequest
from scraper.workers.collection_worker import CollectionWorker
from scraper.workers.pending_work import PendingWorkStore


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class RetryService:
    def __init__(self, options, adapter):
        self.options, self.adapter = options, adapter
        self.store = PendingWorkStore(options.data_dir)

    def _worker(self, entry):
        outcome = entry['latest_outcome']
        category = outcome['category']
        self.adapter.category_url(category)
        kwargs = {}
        if entry['kind'] == 'product' and self.adapter.config.capabilities.product_prices:
            self.adapter.config.validate_url(entry['url'])
            kwargs['product_requests'] = (ProductRequest(category, entry['url'],
                outcome.get('external_id'), reason='pending_retry',
                retailer_sku=outcome.get('retailer_sku')),)
        else:
            # Category-only retailers must revisit the listing containing the item.
            url = entry['url'] if entry['kind'] == 'category' else outcome['source_url']
            self.adapter.config.validate_url(url)
            page = outcome.get('page')
            if page is None:
                for sighting in reversed(entry.get('sightings', [])):
                    context = sighting.get('source_context') or {}
                    if context.get('source_url') == url and context.get('page'):
                        page = context['page']
                        break
            if page is None:
                # Legacy reports lack page metadata. This fallback labels the
                # observation only; the exact work URL is never reconstructed.
                page = int(parse_qs(urlsplit(url).query).get('page', ['1'])[0])
            if type(page) is not int or page < 1:
                raise ValueError('pending category page must be positive')
            kwargs.update(categories=(category,), category_request_urls={category: url},
                          start_page=page)
        return CollectionWorker(self.adapter, self.options.data_dir, self.fetcher,
                                pages=1, close_fetcher=False, **kwargs)

    def run(self):
        if not self.store.path.exists():
            print('No eligible pending work')
            return 0
        # Prevent two retry commands from executing the same snapshot concurrently.
        with (self.store.path.parent / 'retry.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('another retry command is already running') from None
            return self._run_selected()

    def _run_selected(self):
        entries = self.store.eligible(self.adapter.config.name)[:self.options.limit]
        if not entries:
            print('No eligible pending work')
            return 0
        args = self.options
        # One session owns robots rules and the request clock for the whole batch.
        self.fetcher = PageFetcher(args.data_dir / 'raw/html', self.adapter.config.key,
            set(self.adapter.config.allowed_hosts), args.delay, args.offline, args.force)
        try:
            return self._retry_entries(entries)
        finally:
            self.fetcher.close()

    def _retry_entries(self, entries):
        unresolved = resolved_count = 0
        for entry in entries:
            attempt_id = uuid4().hex
            self.store.start_attempt(entry['work_id'], attempt_id, now())
            try:
                worker = self._worker(entry)
                result = worker.run()
                if entry['kind'] == 'product':
                    resolved = entry['url'] in worker.priced
                else:
                    resolved = (result.counters.category_pages_processed > 0
                                and not any(key[0] == 'category' for key in worker.outcomes))
            except (OSError, ValueError) as exc:
                self.store.finish_attempt(entry['work_id'], attempt_id, now(), error=exc)
                unresolved += 1
                print(f"Retry failed: {entry['url']} — {exc}")
                continue
            resolved = self.store.finish_attempt(entry['work_id'], attempt_id, now(),
                result=result, resolved=resolved, expected_run_id=entry['last_run_id'])
            resolved_count += int(resolved)
            # Newly discovered unresolved work still makes this command partial.
            unresolved += int(not resolved or bool(result.failures))
        print(f'Retry: {len(entries)} attempted, {resolved_count} resolved, '
              f'{unresolved} attempts with unresolved work')
        return 1 if unresolved else 0
