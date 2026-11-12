"""Shared product specification collection, checkpoints and retailer-scoped parsing."""
from __future__ import annotations
import hashlib
import fcntl
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
import requests
from scraper.config import PROJECT_ROOT, CATEGORIES
from scraper.common.fetching import PageFetcher
from scraper.common.specifications import SPECIFICATION_FIELDS
from scraper.pipeline.reports import SpecificationReportWriter
from scraper.retailers.contracts import UnsupportedOperationError

# Retained only for the Datatronic compatibility entry point and old HTML caches.
CACHE_DIR = PROJECT_ROOT / 'data/raw/html/specs'


def iter_listings(raw_dir, categories, shop='Datatronic'):
    """Read one retailer's unique product URLs from all supported raw formats."""
    seen, observed = {}, {}
    for path in sorted(Path(raw_dir).glob('*.json')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
            continue
        category, source = payload.get('category'), payload.get('shop', '?')
        if not isinstance(source, str) or source.casefold() != shop.casefold():
            continue
        if category not in CATEGORIES or (categories and category not in categories):
            continue
        try:
            timestamp = datetime.fromisoformat(payload.get('fetched_at') or '0001-01-01')
            timestamp = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
        except (TypeError, ValueError):
            timestamp = datetime.min.replace(tzinfo=timezone.utc)
        for item in payload['items']:
            if not isinstance(item, dict) or not item.get('url'):
                continue
            url = item['url']
            listing = {'url': url, 'category': category, 'name': item.get('name', ''),
                'external_id': str(item.get('external_id') or ''),
                'retailer_sku': item.get('retailer_sku'), 'shop': source}
            if url not in seen or timestamp >= observed[url]:
                previous = seen.get(url, {})
                for field in ('external_id', 'retailer_sku'):
                    listing[field] = listing[field] or previous.get(field)
                seen[url], observed[url] = listing, timestamp
    return list(seen.values())


def cache_path(url, external_id, run_date, retailer='datatronic'):
    return CACHE_DIR / retailer / run_date / (hashlib.sha256(url.encode()).hexdigest() + '.html')


def fetch_page(fetcher, url):
    html, _, origin = fetcher.fetch(url)
    return html, origin


def load_store(path):
    if not path.exists():
        return {'generated_at': date.today().isoformat(), 'source': 'Retailer product pages (data sheet)', 'items': {}}
    store = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(store, dict) or not isinstance(store.get('items'), dict):
        raise ValueError(f'invalid specification store: {path}')
    return store


def write_store(path, store):
    path.parent.mkdir(parents=True, exist_ok=True)
    store['generated_at'] = date.today().isoformat()
    store['source'] = 'Retailer product pages (data sheet)'
    store['item_count'] = len(store['items'])
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                prefix='.specs-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(store, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SpecificationWorker:
    """One retailer per pass, one shared store, one fetcher for the entire pass."""
    def __init__(self, options, adapter, session=None, spec_parser=None,
                 report_writer=None, fetcher=None, cache_root=None):
        if not adapter.config.capabilities.specifications:
            raise UnsupportedOperationError(f'{adapter.config.name} does not support specifications')
        if fetcher is not None and session is not None:
            raise ValueError('supply a fetcher or a session, not both')
        self.options, self.adapter = options, adapter
        self.spec_parser = spec_parser if spec_parser is not None else adapter.specification_parser()
        for category in options.category or ():
            adapter.category_url(category)
            if category not in self.spec_parser.field_map:
                raise UnsupportedOperationError(f'{adapter.config.name} has no specification mapping for {category}')
        report_fields = {category: dict.fromkeys(fields) for category, fields in SPECIFICATION_FIELDS.items()}
        for category, fields in self.spec_parser.field_map.items():
            report_fields.setdefault(category, {}).update(dict.fromkeys(fields))
        self.report_writer = report_writer if report_writer is not None else SpecificationReportWriter(report_fields)
        self.fetcher = fetcher if fetcher is not None else PageFetcher(
            Path(options.raw_dir) / 'html' if cache_root is None else cache_root,
            adapter.config.key, set(adapter.config.allowed_hosts), delay=options.delay,
            offline=options.reparse, force=options.force, session=session)
        self.session = self.fetcher.session

    def run(self):
        try:
            self.options.out.mkdir(parents=True, exist_ok=True)
            with (self.options.out / 'specs.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('another specification command is already running') from None
                return self._run()
        finally:
            self.fetcher.close()

    def _fetch(self, url):
        # Read today's old specification cache if collection has not cached it.
        self.fetcher.validate_url(url)
        digest = hashlib.sha256(url.encode()).hexdigest() + '.html'
        current = self.fetcher.cache_dir / digest
        legacy = Path(self.options.raw_dir) / 'html/specs' / self.adapter.config.key / date.today().isoformat() / digest
        if not self.options.force and not current.exists() and legacy.is_file():
            return legacy.read_text(encoding='utf-8'), legacy, 'cache'
        return self.fetcher.fetch(url)

    def _status(self, store):
        items = {url: entry for url, entry in store['items'].items()
                 if str(entry.get('shop', 'Datatronic')).casefold() == self.adapter.config.name.casefold()
                 and (not self.options.category or entry.get('category') in self.options.category)}
        if not items:
            print(f'No saved specifications for {self.adapter.config.name}', file=sys.stderr)
            return 1
        print(f"{self.adapter.config.name}: {len(items)} products, "
              f"{sum(entry.get('status') == 'ok' for entry in items.values())} parsed ok")
        self.report_writer.write(self.options.out, {**store, 'items': items})
        return 0

    def _parse(self, html, category):
        try:
            features, method = self.spec_parser.extract_features(html)
            values, unmapped = self.spec_parser.parse_specs(category, features)
            return features, method, values, unmapped
        except Exception as exc:
            raise ValueError(f'{type(exc).__name__}: {exc}') from exc

    def _save_entry(self, store, url, entry):
        previous = store['items'].get(url)
        if entry['status'] != 'ok' and previous and previous.get('status') == 'ok' and previous.get('specs'):
            # A failed refresh is evidence about the attempt, not a replacement
            # for an earlier successfully parsed data sheet.
            previous['last_attempt'] = entry
        else:
            store['items'][url] = entry

    def _run(self):
        options = self.options
        store_path = options.out / 'specs.json'
        store = load_store(store_path)
        if options.status:
            return self._status(store)
        listings = iter_listings(options.raw_dir, options.category, self.adapter.config.name)
        if not listings:
            print(f'No listings found — collect {self.adapter.config.key} prices first', file=sys.stderr)
            return 1
        if options.limit:
            listings = listings[:options.limit]
        processed = parsed_ok = skipped = failed = no_cache = 0
        print(f'{self.adapter.config.name}: {len(listings)} products (cache: {self.fetcher.cache_dir})')
        for listing in listings:
            url = listing['url']
            existing = store['items'].get(url)
            if (not options.reparse and not options.force and existing and existing.get('status') == 'ok'
                    and existing.get('specs') and str(existing.get('fetched_at', '')).startswith(date.today().isoformat())):
                skipped += 1
                continue
            entry = {**{key: value for key, value in listing.items() if key != 'url'},
                     'source': 'product_page', 'processed_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
            try:
                html, raw_path, origin = self._fetch(url)
                entry.update(fetched_at=datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat(timespec='seconds'),
                             origin=origin, raw_html=str(raw_path.resolve().relative_to(options.raw_dir.parent.resolve()))
                             if raw_path.resolve().is_relative_to(options.raw_dir.parent.resolve()) else str(raw_path.resolve()))
                features, method, values, unmapped = self._parse(html, listing['category'])
                specs = dict.fromkeys(self.spec_parser.field_map.get(listing['category'], {}))
                specs.update(values)
                entry.update(specs=specs, spec_count=len(values), feature_count=len(features),
                             extraction=method, unmapped=unmapped, status='ok' if values else 'empty')
                if values:
                    parsed_ok += 1
                else:
                    failed += 1
                    entry['error'] = 'no supported specification fields parsed'
            except (requests.RequestException, OSError, ValueError) as exc:
                if isinstance(exc, FileNotFoundError) and options.reparse:
                    no_cache += 1
                    print(f'  NO CACHE {url} — {exc}', file=sys.stderr)
                    continue
                failed += 1
                entry.update(specs={}, status='failed', error=f'{type(exc).__name__}: {exc}'[:240])
                print(f'  FAILED {url} — {exc}', file=sys.stderr)
            self._save_entry(store, url, entry)
            processed += 1
            if processed % options.checkpoint_every == 0:
                write_store(store_path, store)
            print(f"  [{listing['category']}] {entry['status']}: {listing['name'][:60]}")
        write_store(store_path, store)
        self.report_writer.write(options.out, store)
        print(f'{processed} processed, {parsed_ok} parsed, {skipped} skipped, {failed} failed, {no_cache} offline misses')
        return 1 if failed or no_cache else 0


class DatatronicSpecExtractor(SpecificationWorker):
    """Compatibility entry point; all orchestration is implemented by the worker."""
    def __init__(self, options, session=None, spec_parser=None, report_writer=None, fetcher=None):
        from scraper.retailers.datatronic import DatatronicAdapter
        super().__init__(options, DatatronicAdapter(), session, spec_parser, report_writer, fetcher, CACHE_DIR)


def write_report(out_dir, store):
    from scraper.retailers.datatronic_specs import FIELD_MAP
    return SpecificationReportWriter(FIELD_MAP).write(out_dir, store)
