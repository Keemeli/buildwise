"""Conservative identity decisions and verified grouping plans; no I/O."""
from collections import defaultdict
from itertools import combinations
import json
import re

from scraper.common.product_identity import ProductIdentity


class ProductIdentityMatcher:
    """Compare retailer listings, keeping conflicting historical evidence visible.

    Decisions are pairs, never transitive groups: A matching B and B matching C
    is not sufficient evidence to merge A with C.
    """

    VARIANT_FIELDS = ('chipset', 'vram_gb', 'memory_type', 'capacity_gb',
                      'socket', 'packaging', 'color', 'modules')
    SPECIAL_OFFER = re.compile(r'\b(bundle|bundled|demo|refurbished|used|b-stock|tray|bulk|käytetty|kunnostettu)\b', re.I)

    @staticmethod
    def reconcile(observations):
        values = {field: set() for field in ('gtin', 'manufacturer_part_number', 'brand')}
        issues = set()
        for observation in observations:
            try:
                identity = ProductIdentity.from_dict(observation.get('identity'))
            except (TypeError, ValueError, AttributeError):
                issues.add('invalid_identity_observation')
                continue
            if identity is None:
                continue
            issues.update(identity.issues)
            for field in values:
                value = getattr(identity, field)
                if value is not None:
                    # Only brand spelling/case is normalised for comparison.
                    values[field].add(value.casefold() if field == 'brand' else value)
        result = {}
        for field, observed in values.items():
            result[field] = next(iter(observed)) if len(observed) == 1 else None
            if len(observed) > 1:
                issues.add(f'{field}:conflicting_observations')
        return {**result, 'issues': sorted(issues)}

    def compare(self, left, right):
        a, b = left['identity'], right['identity']
        reasons = []
        if left['category'] != right['category']:
            reasons.append('category_conflict')
        for field in ('gtin', 'manufacturer_part_number', 'brand'):
            if a[field] and b[field] and a[field] != b[field]:
                reasons.append(f'{field}_conflict')
        for field in self.VARIANT_FIELDS:
            first, second = left['specs'].get(field), right['specs'].get(field)
            if first is not None and second is not None and first != second:
                reasons.append(f'specification_conflict:{field}')
        if reasons:
            return 'conflict', reasons
        if a['issues'] or b['issues']:
            return 'review', ['identity_evidence_issues']
        if any(self.SPECIAL_OFFER.search(item['raw_name']) or item.get('category_confidence') == 'suspect'
               for item in (left, right)):
            return 'review', ['offer_or_category_needs_review']
        if a['gtin'] and a['gtin'] == b['gtin']:
            return 'match', ['exact_gtin']
        if (a['brand'] and a['brand'] == b['brand'] and a['manufacturer_part_number']
                and a['manufacturer_part_number'] == b['manufacturer_part_number']):
            return 'match', ['exact_brand_and_manufacturer_part_number']
        return 'unresolved', ['insufficient_identifiers']

    def build_report(self, components):
        # Reconcile repeated raw snapshots per retailer URL before comparing shops.
        groups = defaultdict(list)
        for component in components:
            for listing in component['listings']:
                key = (listing['shop'].casefold(), listing['url'])
                groups[key].append((component, listing))
        listings = []
        for key, entries in sorted(groups.items()):
            observations = [source for _, listing in entries for source in listing.get('identity_observations', [])]
            component, listing = min(entries, key=lambda pair: json.dumps(pair, sort_keys=True))
            identity = self.reconcile(observations)
            if any(self.SPECIAL_OFFER.search(item['raw_name']) or item.get('category_confidence') == 'suspect'
                   for item, _ in entries):
                identity['issues'].append('offer_or_category_needs_review')
            categories = {item['category'] for item, _ in entries}
            if len(categories) > 1:
                identity['issues'].append('listing_category_conflict')
            specs = {}
            for field in self.VARIANT_FIELDS:
                values = {json.dumps(item['specs'].get(field), sort_keys=True) for item, _ in entries
                          if item['specs'].get(field) is not None}
                if len(values) == 1:
                    specs[field] = json.loads(next(iter(values)))
                elif len(values) > 1:
                    identity['issues'].append(f'listing_specification_conflict:{field}')
            listings.append({'shop': key[0], 'url': key[1], 'external_id': listing.get('external_id'),
                             'category': component['category'], 'raw_name': component['raw_name'],
                             'category_confidence': component.get('category_confidence'),
                             'specs': specs, 'identity': identity,
                             'identity_observations': sorted(observations, key=lambda value: json.dumps(value, sort_keys=True))})
        # Index strong identifiers instead of comparing every title with every other.
        index = defaultdict(set)
        for position, listing in enumerate(listings):
            identity = listing['identity']
            if identity['gtin']:
                index[('gtin', identity['gtin'])].add(position)
            if identity['brand'] and identity['manufacturer_part_number']:
                index[('mpn', identity['brand'], identity['manufacturer_part_number'])].add(position)
        pairs = set()
        for positions in index.values():
            pairs.update(combinations(sorted(positions), 2))
        decisions = []
        for first, second in sorted(pairs):
            left, right = listings[first], listings[second]
            if left['shop'] == right['shop']:
                continue
            status, reasons = self.compare(left, right)
            decisions.append({'left': first, 'right': second, 'status': status, 'reasons': reasons})
        counts = {status: sum(item['status'] == status for item in decisions)
                  for status in ('match', 'conflict', 'review', 'unresolved')}
        involved = {position for item in decisions for position in (item['left'], item['right'])}
        return {'policy_version': 1, 'mode': 'review_only', 'listings': listings,
                'decisions': decisions, 'counts': {**counts, 'without_candidates': len(listings) - len(involved)}}


class VerifiedProductGrouper:
    """Apply only complete, unambiguous cross-shop match groups.

    Incomplete connected groups are withheld as a whole, rather than choosing
    an input-order-dependent subset or merging through a weak bridge.
    """

    def plan(self, report):
        from copy import deepcopy
        report = deepcopy(report)
        listings = report['listings']
        neighbours = {index: set() for index in range(len(listings))}
        decisions = {}
        for decision in report['decisions']:
            pair = (decision['left'], decision['right'])
            decisions[pair] = decision
            if decision['status'] == 'match':
                first, second = pair
                neighbours[first].add(second)
                neighbours[second].add(first)
        remaining = set(neighbours)
        groups = []
        ambiguous = 0
        while remaining:
            first = min(remaining)
            connected, pending = set(), [first]
            while pending:
                index = pending.pop()
                if index not in connected:
                    connected.add(index)
                    pending.extend(neighbours[index] - connected)
            remaining.difference_update(connected)
            members = sorted(connected)
            complete = len(members) > 1 and all(
                decisions.get((a, b), {}).get('status') == 'match'
                for a, b in combinations(members, 2))
            if complete:
                groups.append({'listings': members, 'status': 'verified',
                               'reasons': sorted({reason for a, b in combinations(members, 2)
                                                  for reason in decisions[(a, b)]['reasons']})})
                continue
            if len(members) > 1:
                ambiguous += 1
            for index in members:
                related = [decision for pair, decision in decisions.items() if index in pair]
                statuses = {decision['status'] for decision in related}
                status = ('review' if len(members) > 1 else 'conflict' if 'conflict' in statuses
                          else 'review' if 'review' in statuses or listings[index]['identity']['issues']
                          else 'unresolved')
                reasons = (['ambiguous_match_chain'] if len(members) > 1 else
                           sorted({reason for decision in related for reason in decision['reasons']
                                   if decision['status'] != 'match'}))
                if not reasons:
                    reasons = listings[index]['identity']['issues'] or ['insufficient_identifiers']
                groups.append({'listings': [index], 'status': status, 'reasons': reasons})
        report['groups'] = sorted(groups, key=lambda group: group['listings'])
        report['mode'] = 'verified_grouping'
        report['policy_version'] = 2
        report['counts'].update(verified_groups=sum(group['status'] == 'verified' for group in groups),
                                separate_listings=sum(len(group['listings']) == 1 for group in groups),
                                ambiguous_groups=ambiguous)
        return report
