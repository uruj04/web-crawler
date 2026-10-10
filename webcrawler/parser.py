"""Turns raw HTML into structured PageData, using BeautifulSoup."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from .models import PageData


def _clean(text: str) -> str:
    return " ".join(text.split())


def _resolve(base_url: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    absolute, _fragment = urldefrag(urljoin(base_url, href))
    if urlparse(absolute).scheme not in ("http", "https"):
        return None
    return absolute


def parse_page(url: str, html: str, status_code: int, depth: int) -> PageData:
    """Extract everything the crawler needs from one page's HTML."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = _clean(title_tag.get_text()) if title_tag else ""

    headings = [
        _clean(tag.get_text())
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        if _clean(tag.get_text())
    ]

    paragraphs = [_clean(tag.get_text()) for tag in soup.find_all("p") if _clean(tag.get_text())]

    links: list[str] = []
    seen_links = set()
    for tag in soup.find_all("a", href=True):
        resolved = _resolve(url, tag["href"])
        if resolved and resolved not in seen_links:
            seen_links.add(resolved)
            links.append(resolved)

    images: list[str] = []
    seen_images = set()
    for tag in soup.find_all("img", src=True):
        resolved = _resolve(url, tag["src"])
        if resolved and resolved not in seen_images:
            seen_images.add(resolved)
            images.append(resolved)

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_description = _clean(meta_tag["content"])

    return PageData(
        url=url,
        depth=depth,
        status_code=status_code,
        title=title,
        headings=headings,
        paragraphs=paragraphs,
        links=links,
        images=images,
        meta_description=meta_description,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
    )


def same_site(url_a: str, url_b: str) -> bool:
    """True when two URLs share the same scheme and host (ignoring port)."""
    a, b = urlparse(url_a), urlparse(url_b)
    return a.scheme == b.scheme and a.hostname == b.hostname
