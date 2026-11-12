"""Persist unresolved collection work and explicit retry attempt history."""
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import tempfile


class PendingWorkStore:
    """Keep one entry per retailer work URL and retain each run's evidence.

    Category work includes its category in the identity; product work does not.
    Sightings are collection reports, separate from explicit retry attempts.
    Resolved entries remain available as history.
    """

    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / 'pending' / 'collection.json'

    @staticmethod
    def work_id(shop, kind, category, url):
        identity = [shop, kind, category if kind == 'category' else None, url]
        return hashlib.sha256(json.dumps(identity).encode('utf-8')).hexdigest()

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self):
        if not self.path.exists():
            return {'schema_version': 1, 'entries': {}}
        document = json.loads(self.path.read_text(encoding='utf-8'))
        if (not isinstance(document, dict) or document.get('schema_version') != 1
                or not isinstance(document.get('entries'), dict)):
            raise ValueError(f'invalid pending-work store: {self.path}')
        return document

    def record(self, result, outcomes, source_contexts=None):
        """Atomically merge keyed outcomes; repeated recording of a run is safe."""
        if not outcomes:
            return
        source_contexts = source_contexts or {}
        with self._locked():
            document = self._read()
            for (kind, category, url), outcome in outcomes.items():
                key = self.work_id(result.shop, kind, category, url)
                entry = document['entries'].setdefault(key, {
                    'work_id': key, 'shop': result.shop, 'kind': kind, 'url': url,
                    'status': 'pending', 'first_seen_at': result.finished_at,
                    'first_run_id': result.run_id, 'sightings': [],
                })
                evidence = {'outcome': asdict(outcome),
                            'observed_at': result.finished_at,
                            'source_context': source_contexts.get(url)}
                entry['sightings'] = [s for s in entry['sightings']
                                      if s['outcome']['run_id'] != result.run_id]
                entry['sightings'].append(evidence)
                entry.pop('resolved_at', None)
                entry.pop('resolved_run_id', None)
                entry.update(status='pending', latest_outcome=asdict(outcome), last_seen_at=result.finished_at,
                             last_run_id=result.run_id,
                             retry_eligible=outcome.retry_classification == 'retryable')
            self._write(document)

    def _write(self, document):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                    dir=self.path.parent, prefix='.collection-', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def eligible(self, shop):
        if not self.path.exists():
            return []
        with self._locked():
            return [entry for entry in self._read()['entries'].values()
                    if entry['shop'] == shop and entry['status'] == 'pending'
                    and entry['retry_eligible']]

    def start_attempt(self, work_id, attempt_id, started_at):
        with self._locked():
            document = self._read()
            entry = document['entries'][work_id]
            for previous in entry.get('attempts', []):
                if previous['status'] == 'running':
                    previous.update(status='interrupted', finished_at=started_at)
            entry.setdefault('attempts', []).append({
                'attempt_id': attempt_id, 'started_at': started_at, 'status': 'running'})
            self._write(document)

    def finish_attempt(self, work_id, attempt_id, finished_at, *, result=None,
                       resolved=False, error=None, expected_run_id=None):
        with self._locked():
            document = self._read()
            entry = document['entries'][work_id]
            if resolved and expected_run_id is not None and entry['last_run_id'] != expected_run_id:
                resolved = False
            attempt = next(a for a in entry['attempts'] if a['attempt_id'] == attempt_id)
            attempt.update(finished_at=finished_at,
                           status='resolved' if resolved else 'unresolved')
            if result is not None:
                attempt.update(run_id=result.run_id, collection_status=result.status,
                               unresolved_outcomes=result.counters.unresolved_outcomes)
            if error is not None:
                attempt['error'] = str(error)
            if resolved:
                entry.update(status='resolved', retry_eligible=False,
                             resolved_at=finished_at, resolved_run_id=result.run_id)
            self._write(document)
            return resolved
