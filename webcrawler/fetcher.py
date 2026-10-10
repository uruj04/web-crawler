"""Async HTTP fetching, using aiohttp for the real network calls.

The crawler depends only on an object with a matching `fetch(url)` method
(see the Fetcher protocol below), not on aiohttp itself, so it can be driven
by a fake fetcher in tests without aiohttp installed at all.
"""

from __future__ import annotations

from typing import Protocol

from .models import FetchResult


class Fetcher(Protocol):
    async def fetch(self, url: str) -> FetchResult: ...
    async def fetch_text_or_none(self, url: str) -> str | None: ...
    async def close(self) -> None: ...


class AiohttpFetcher:
    """Fetches pages with a real aiohttp session, one per crawl run.

    aiohttp is imported here, inside __init__, rather than at module level,
    so this module (and anything that imports it, like the CLI) can still be
    imported and unit tested in environments without aiohttp installed; only
    actually creating a fetcher for a real crawl requires it.
    """

    def __init__(self, user_agent: str, timeout_s: float) -> None:
        import aiohttp

        self._aiohttp = aiohttp
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": user_agent},
            timeout=aiohttp.ClientTimeout(total=timeout_s),
        )

    async def fetch(self, url: str) -> FetchResult:
        async with self._session.get(url) as response:
            text = await response.text(errors="replace")
            return FetchResult(url=url, status_code=response.status, text=text)

    async def fetch_text_or_none(self, url: str) -> str | None:
        try:
            async with self._session.get(url) as response:
                if response.status >= 400:
                    return None
                return await response.text(errors="replace")
        except self._aiohttp.ClientError:
            return None

    async def close(self) -> None:
        await self._session.close()
