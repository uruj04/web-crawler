"""robots.txt rules, with one ruleset cached per site."""

from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urlparse

logger = logging.getLogger("webcrawler")


class RobotsChecker:
    """Answers 'can I fetch this URL?' using each site's robots.txt.

    A fetch function is injected so this class never does its own networking,
    which keeps it fully testable without a real HTTP client.
    """

    def __init__(self, user_agent: str, fetch_text) -> None:
        self.user_agent = user_agent
        self._fetch_text = fetch_text
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _parser_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._parsers:
            return self._parsers[origin]

        parser = urllib.robotparser.RobotFileParser()
        robots_url = f"{origin}/robots.txt"
        try:
            text = self._fetch_text(robots_url)
        except Exception as exc:
            logger.info("No robots.txt at %s (%s); allowing all.", robots_url, exc)
            self._parsers[origin] = None
            return None

        if text is None:
            self._parsers[origin] = None
            return None

        try:
            parser.parse(text.splitlines())
        except Exception as exc:
            logger.warning("Could not parse robots.txt at %s (%s); allowing all.", robots_url, exc)
            self._parsers[origin] = None
            return None

        self._parsers[origin] = parser
        return parser

    def load_rules(self, origin_url: str, text: str | None) -> None:
        """Pre-populate the cache for one origin from already-fetched text.

        Lets an async caller fetch robots.txt itself (with a real async HTTP
        client) and hand the result in, instead of this class doing its own
        synchronous fetch.
        """
        parsed = urlparse(origin_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if text is None:
            self._parsers[origin] = None
            return
        parser = urllib.robotparser.RobotFileParser()
        try:
            parser.parse(text.splitlines())
        except Exception as exc:
            logger.warning("Could not parse robots.txt for %s (%s); allowing all.", origin, exc)
            self._parsers[origin] = None
            return
        self._parsers[origin] = parser

    def is_allowed(self, url: str) -> bool:
        parser = self._parser_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)
