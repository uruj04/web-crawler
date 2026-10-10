"""Custom exceptions used across the application."""


class CrawlerError(Exception):
    """Base class for all application errors."""


class ConfigError(CrawlerError):
    """Raised when settings are invalid."""


class FetchError(CrawlerError):
    """Raised when a page cannot be downloaded after all retries."""


class RobotsDisallowedError(CrawlerError):
    """Raised when robots.txt forbids fetching a URL."""
