"""BuildWise — sequential, throttled requests and retailer-scoped HTML caching."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from protego import Protego

import requests

USER_AGENT = "BuildWise-course-project/0.1 (eekarjal24@students.oamk.fi)"


class RobotsDisallowedError(ValueError):
    """Published robots rules prohibit the requested URL."""


class RobotsUnavailableError(ValueError):
    def __init__(self, message, *, status_code=None, cause=None):
        super().__init__(message)
        self.status_code = status_code
        self.cause = cause


class PageFetcher:
    """One identified session; failed requests also count toward the delay.

    Cache keys include the complete URL and retailer. Cached reads do not make
    network requests. Offline mode never falls back to the network.
    """

    def __init__(self, cache_root: Path, retailer: str, hosts: set[str],
                 delay: float = 1.0, offline: bool = False, force: bool = False,
                 session: requests.Session | None = None):
        if delay < 1.0:
            raise ValueError("delay must be at least 1.0 seconds")
        if offline and force:
            raise ValueError("offline and force cannot be combined")
        self.cache_dir = cache_root / retailer / date.today().isoformat()
        self.hosts = hosts
        self.delay, self.offline, self.force = delay, offline, force
        self.last_attempt: float | None = None
        self.robots: dict[str, tuple[Protego, float] | RobotsUnavailableError] = {}
        self.session = requests.Session() if session is None else session
        self.session.headers.update({"User-Agent": USER_AGENT,
                                     "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8"})

    def validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in self.hosts
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError(f"expected an HTTPS product URL on {sorted(self.hosts)}")

    def _request(self, url: str, delay: float):
        """Space all attempts, including robots requests and failures."""
        if self.last_attempt is not None:
            time.sleep(max(0, delay - (time.monotonic() - self.last_attempt)))
        self.last_attempt = time.monotonic()
        return self.session.get(url, timeout=30, allow_redirects=False)

    def _check_robots(self, url: str) -> float:
        """Load rules once per host/run; unavailable rules block that host.

        A 404 means no published rules. Redirects and other unsuccessful
        responses fail closed rather than silently granting access. Cached
        product HTML can still be parsed offline without requesting robots.
        """
        host = urlsplit(url).netloc
        if host not in self.robots:
            robots_url = f"https://{host}/robots.txt"
            status_code = None
            try:
                response = self._request(robots_url, self.delay)
                status_code = response.status_code
                if response.status_code == 404:
                    text = "User-agent: *\nAllow: /\n"
                elif response.status_code == 200:
                    text = response.text
                    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
                        raise ValueError("robots.txt returned HTML")
                else:
                    raise ValueError(f"robots.txt returned HTTP {response.status_code}")
                rules = Protego.parse(text)
                wait = max(self.delay, float(rules.crawl_delay(USER_AGENT) or 0))
                rate = rules.request_rate(USER_AGENT)
                if rate and rate.requests > 0:
                    wait = max(wait, rate.seconds / rate.requests)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                (self.cache_dir / f"robots_{host.replace(':', '_')}.json").write_text(
                    json.dumps({"url": robots_url, "status": response.status_code,
                                "rules": text}, indent=2), encoding="utf-8")
                self.robots[host] = (rules, wait)
            except (requests.RequestException, OSError, ValueError) as exc:
                self.robots[host] = RobotsUnavailableError(f"robots check unavailable for {host}: {exc}",
                                                          status_code=status_code, cause=exc)
        entry = self.robots[host]
        if isinstance(entry, RobotsUnavailableError):
            raise entry
        rules, wait = entry
        if not rules.can_fetch(url, USER_AGENT):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")
        return wait

    def fetch(self, url: str) -> tuple[str, Path, str]:
        """Return (HTML, cache path, origin), preserving successful responses."""
        self.validate_url(url)
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        path = self.cache_dir / f"{key}.html"
        if path.exists() and not self.force:
            return path.read_text(encoding="utf-8"), path, "cache"
        if self.offline:
            raise FileNotFoundError(f"no cached HTML for {url}")
        current = url
        for _ in range(6):
            self.validate_url(current)
            wait = self._check_robots(current)
            response = self._request(current, wait)
            if response.is_redirect or response.is_permanent_redirect:
                from urllib.parse import urljoin
                current = urljoin(current, response.headers["Location"])
                continue
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError(f"unexpected HTTP status {response.status_code}")
            response.encoding = response.apparent_encoding or "utf-8"
            html = response.text
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
            return html, path, "network"
        raise ValueError("too many redirects")

    def close(self) -> None:
        self.session.close()
