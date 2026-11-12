"""Select current and last-known prices without making stale prices current."""
from datetime import datetime, timezone
import json


class ListingPriceSelector:
    """Compare source observation times; processing order has no significance."""

    @staticmethod
    def observed_at(listing):
        value = listing.get('fetched_at') or listing.get('snapshot_date')
        if not value:
            return datetime.min.replace(tzinfo=timezone.utc)
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Legacy date-only/naive timestamps are interpreted as UTC.
        return timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)

    @staticmethod
    def valid_price(listing):
        price = listing.get('price_cents')
        return type(price) is int and price >= 0

    @staticmethod
    def evidence(listing):
        return {key: listing.get(key) for key in (
            'shop', 'url', 'price_cents', 'fetched_at', 'snapshot_date',
            'external_id', 'retailer_sku', 'provenance')}

    def select(self, observations):
        groups = {}
        for listing in observations:
            groups.setdefault(self.observed_at(listing), []).append(listing)
        newest = groups[max(groups)]
        valid = [listing for listing in newest if self.valid_price(listing)]
        prices = {listing['price_cents'] for listing in valid}
        # Prefer priced evidence at the same instant; stable metadata ties do not
        # decide between different prices, which always remain a conflict.
        representative = min(valid or newest, key=lambda item: json.dumps(item, sort_keys=True))
        selected = dict(representative)
        selected['price_cents'] = next(iter(prices)) if len(prices) == 1 else None
        selected['price_status'] = 'conflict' if len(prices) > 1 else 'available' if prices else 'unknown'
        selected['price_observations'] = [self.evidence(item) for item in
            sorted(newest, key=lambda item: json.dumps(item, sort_keys=True))]
        selected.update(last_known_price_cents=None, last_known_price_fetched_at=None,
                        last_known_price_source=None)
        for timestamp in sorted(groups, reverse=True):
            candidates = [item for item in groups[timestamp] if self.valid_price(item)]
            if len({item['price_cents'] for item in candidates}) != 1:
                continue
            known = min(candidates, key=lambda item: json.dumps(item, sort_keys=True))
            selected.update(last_known_price_cents=known['price_cents'],
                            last_known_price_fetched_at=known.get('fetched_at') or known.get('snapshot_date') or None,
                            last_known_price_source=self.evidence(known))
            break
        # Keep known retailer identifiers if the newest legacy observation omits
        # them. Their original evidence remains attached to the selected source.
        for field in ('external_id', 'retailer_sku'):
            if selected.get(field) is None:
                candidates = [item for item in observations if item.get(field) is not None]
                if candidates:
                    latest = max(self.observed_at(item) for item in candidates)
                    known = min((item for item in candidates if self.observed_at(item) == latest),
                                key=lambda item: json.dumps(item, sort_keys=True))
                    selected[field] = known[field]
                    selected.setdefault('identifier_sources', {})[field] = self.evidence(known)
        identity_observations = [source for item in observations
                                 for source in item.get('identity_observations', [])]
        if identity_observations:
            unique = {json.dumps(source, sort_keys=True): source for source in identity_observations}
            selected['identity_observations'] = [unique[key] for key in sorted(unique)]
        return selected
