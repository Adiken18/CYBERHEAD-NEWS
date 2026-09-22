import calendar
import logging
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import urldefrag, urlsplit
from urllib.request import Request, urlopen

import feedparser
from bs4 import BeautifulSoup

from app.database import initialise_database, save_article
from app.sources import RSS_SOURCES


logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
MAX_FEED_BYTES = 5 * 1024 * 1024


def clean_text(value):
    """Remove HTML and unnecessary whitespace."""

    soup = BeautifulSoup(value or "", "html.parser")

    for element in soup(["script", "style"]):
        element.decompose()

    return " ".join(soup.get_text(separator=" ", strip=True).split())


def get_publication_date(entry):
    """Return the supplied publication date in UTC, or None."""

    parsed_date = entry.get("published_parsed")

    if parsed_date is None:
        return None

    try:
        timestamp = calendar.timegm(parsed_date)

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        ).isoformat()

    except (ValueError, OverflowError, OSError):
        return None


def get_article_content(entry):
    """Use feed content when available; otherwise use its summary."""

    for item in entry.get("content", []):
        if item.get("type") in ("text/plain", "text/html", "application/xhtml+xml"):
            text = clean_text(item.get("value"))

            if text:
                return text

    return clean_text(entry.get("summary")) or None


def get_article_url(entry):
    """Accept HTTP(S) links and remove page fragments."""

    raw_url = entry.get("link", "").strip()

    try:
        url, _ = urldefrag(raw_url)
        parts = urlsplit(url)

        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None

        return url

    except ValueError:
        return None


def download_feed(url):
    """Download with a timeout and a maximum response size."""

    request = Request(
        url,
        headers={
            "User-Agent": "CYBERHEAD-News/0.1 (RSS collector)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml"
        }
    )

    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(MAX_FEED_BYTES + 1)

    if len(data) > MAX_FEED_BYTES:
        raise ValueError("Feed exceeds the 5 MB size limit.")

    return data


def collect_source(source):
    feed_bytes = download_feed(source["url"])
    feed = feedparser.parse(feed_bytes)

    if not feed.get("version"):
        raise ValueError("The response is not a recognised RSS or Atom feed.")

    if feed.bozo:
        logger.warning(
            "%s: feed has parsing issues; processing readable entries.",
            source["name"]
        )

    added = 0
    duplicates = 0
    invalid = 0

    for entry in feed.entries:
        title = clean_text(entry.get("title"))
        url = get_article_url(entry)

        if not title or not url:
            invalid += 1
            continue

        was_added = save_article(
            title=title,
            url=url,
            source=source["name"],
            published_at=get_publication_date(entry),
            content=get_article_content(entry)
        )

        if was_added:
            added += 1
        else:
            duplicates += 1

    logger.info(
        "%s: %s added, %s existing URLs skipped, %s invalid entries skipped.",
        source["name"],
        added,
        duplicates,
        invalid
    )

    return added


def collect_all():
    initialise_database()

    total_added = 0
    failed_sources = 0

    for source in RSS_SOURCES:
        logger.info("Collecting from %s...", source["name"])

        try:
            total_added += collect_source(source)

        except (URLError, OSError, ValueError) as error:
            failed_sources += 1

            logger.error(
                "%s could not be collected: %s",
                source["name"],
                error
            )

    logger.info(
        "Finished: %s new articles; %s source(s) failed.",
        total_added,
        failed_sources
    )

    return failed_sources


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    failures = collect_all()

    raise SystemExit(1 if failures else 0)