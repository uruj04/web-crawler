"""Keyword search and frequency analysis over collected pages."""

from __future__ import annotations

import re
from collections import Counter

from .models import PageData

_WORD = re.compile(r"[a-zA-Z']+")


def search_pages(pages: list[PageData], keyword: str) -> list[PageData]:
    """Return pages whose title, headings, or paragraphs mention `keyword`."""
    keyword = keyword.strip().lower()
    if not keyword:
        return []

    matches = []
    for page in pages:
        haystack = " ".join([page.title, *page.headings, *page.paragraphs]).lower()
        if keyword in haystack:
            matches.append(page)
    return matches


def keyword_frequency(pages: list[PageData], top_n: int = 20, min_length: int = 3) -> list[tuple[str, int]]:
    """Return the most common words across every page's text, longest-first on ties."""
    stop_words = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
        "was", "were", "with", "this", "that", "from", "your", "have", "will",
        "about", "their", "which", "there",
    }
    counts: Counter[str] = Counter()
    for page in pages:
        text = " ".join([page.title, *page.headings, *page.paragraphs]).lower()
        for word in _WORD.findall(text):
            if len(word) >= min_length and word not in stop_words:
                counts[word] += 1
    return counts.most_common(top_n)
