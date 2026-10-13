"""Safe browser-based live demo for the Web Crawler project."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from webcrawler.cli import _run_crawl
from webcrawler.config import Settings
from webcrawler.exceptions import CrawlerError
from webcrawler.exporter import export_csv, export_json
from webcrawler.search import keyword_frequency, search_pages


DEMO_HOST = "books.toscrape.com"

st.set_page_config(page_title="Web Crawler Demo", page_icon="🕸️", layout="wide")


def is_safe_demo_url(value: str) -> bool:
    """Keep the public demo limited to the scraping-practice site."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.netloc == DEMO_HOST


st.title("Web Crawler & Data Extraction Engine")
st.caption("A live, safe demonstration of the project's asynchronous crawler.")
st.info(
    "This public demo is intentionally limited to books.toscrape.com, a site created for "
    "scraping practice. The CLI project can crawl permitted public sites and respects robots.txt."
)

with st.form("crawler-settings"):
    seed_url = st.text_input("Seed URL", value="https://books.toscrape.com/")
    col1, col2 = st.columns(2)
    with col1:
        max_depth = st.slider("Maximum depth", min_value=0, max_value=2, value=1)
    with col2:
        max_pages = st.slider("Maximum pages", min_value=1, max_value=25, value=10)
    submitted = st.form_submit_button("Start crawl", type="primary")

if not submitted:
    st.stop()

if not is_safe_demo_url(seed_url.strip()):
    st.error("For safety, this live demo only crawls https://books.toscrape.com/. ")
    st.stop()

with tempfile.TemporaryDirectory() as directory:
    output_dir = Path(directory)
    settings = Settings(
        seed_urls=(seed_url.strip(),),
        max_depth=max_depth,
        max_pages=max_pages,
        concurrency=5,
        delay_s=0.2,
        timeout_s=15.0,
        max_retries=2,
        retry_delay_s=1.0,
        respect_robots=True,
        output_dir=output_dir,
        log_file=output_dir / "crawler.log",
    )
    try:
        with st.spinner("Fetching pages, checking robots.txt, and extracting content..."):
            result = asyncio.run(_run_crawl(settings, [seed_url.strip()]))
    except CrawlerError as exc:
        st.error(str(exc))
        st.stop()
    except Exception:
        st.error("The crawl could not complete. Please try again shortly.")
        st.stop()

    json_path = output_dir / "crawl_result.json"
    csv_path = output_dir / "crawl_result.csv"
    export_json(result, json_path)
    export_csv(result, csv_path)
    json_bytes = json_path.read_bytes()
    csv_bytes = csv_path.read_bytes()

stats = result.stats
st.success(f"Crawl completed: {stats.pages_visited} page(s) extracted.")
metrics = st.columns(4)
metrics[0].metric("Pages visited", stats.pages_visited)
metrics[1].metric("Failures", stats.pages_failed)
metrics[2].metric("Robots skipped", stats.pages_skipped_robots)
metrics[3].metric("Time", f"{stats.execution_seconds:.2f} s")

downloads = st.columns(2)
downloads[0].download_button(
    "Download JSON export", json_bytes, "crawl_result.json", "application/json"
)
downloads[1].download_button("Download CSV export", csv_bytes, "crawl_result.csv", "text/csv")

st.subheader("Extracted pages")
rows = [
    {
        "Title": page.title or "(untitled)",
        "Depth": page.depth,
        "Words": page.word_count,
        "Links": len(page.links),
        "URL": page.url,
    }
    for page in result.pages
]
st.dataframe(rows, use_container_width=True, hide_index=True)

query = st.text_input("Search collected content", placeholder="Example: travel")
if query.strip():
    matches = search_pages(result.pages, query)
    st.write(f"**{len(matches)} page(s)** mention `{query.strip()}`.")
    for page in matches:
        st.markdown(f"- [{page.title or '(untitled)'}]({page.url})")

st.subheader("Top keywords")
keywords = keyword_frequency(result.pages, top_n=12)
if keywords:
    st.bar_chart({"Occurrences": {word: count for word, count in keywords}})
