import argparse
import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
import trafilatura

from app.database import (
    initialise_database,
    get_articles_for_extraction,
    save_extraction_result,
)


logger = logging.getLogger(__name__)

BOT_NAME = "CyberheadNews"
USER_AGENT = "CyberheadNews/0.1 (academic news collector)"

ALLOWED_HOSTS = {
    "www.bleepingcomputer.com",
    "bleepingcomputer.com",
    "thehackernews.com",
    "www.thehackernews.com",
}

MAX_PAGE_BYTES = 5 * 1024 * 1024
MIN_WORDS = 80
DEFAULT_DELAY = 3

robots_cache = {}


class SkipArticle(Exception):
    """The page should not be downloaded or processed."""


def download(session, url):
    """Download one URL with a size limit and no automatic redirects."""

    with session.get(
        url,
        timeout=(10, 30),
        allow_redirects=False,
        stream=True
    ) as response:

        if 300 <= response.status_code < 400:
            raise SkipArticle(
                "Redirect received; review the destination before extracting."
            )

        response.raise_for_status()

        chunks = []
        total_bytes = 0

        for chunk in response.iter_content(chunk_size=65536):
            total_bytes += len(chunk)

            if total_bytes > MAX_PAGE_BYTES:
                raise ValueError("Response exceeds the 5 MB size limit.")

            chunks.append(chunk)

        return (
            b"".join(chunks),
            response.headers.get("Content-Type", "").lower()
        )


def check_robots(session, url):
    """Check robots.txt and return the delay between requests."""

    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"

    if origin not in robots_cache:
        robots_url = origin + "/robots.txt"

        try:
            body, content_type = download(session, robots_url)

        except requests.HTTPError as error:
            if error.response.status_code == 404:
                # No robots.txt was published at this address.
                robots_cache[origin] = None
            else:
                raise

        else:
            if "text/html" in content_type:
                raise ValueError(
                    "Received HTML instead of a readable robots.txt."
                )

            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(body.decode("utf-8", errors="replace").splitlines())
            robots_cache[origin] = parser

    parser = robots_cache[origin]

    if parser is None:
        return DEFAULT_DELAY

    if not parser.can_fetch(BOT_NAME, url):
        raise SkipArticle("robots.txt disallows this article URL.")

    delay = parser.crawl_delay(BOT_NAME) or DEFAULT_DELAY
    rate = parser.request_rate(BOT_NAME)

    if rate and rate.requests > 0:
        delay = max(delay, rate.seconds / rate.requests)

    return max(DEFAULT_DELAY, delay)


def extract_article(session, url):
    parts = urlsplit(url)

    if (
        parts.scheme != "https"
        or parts.hostname not in ALLOWED_HOSTS
        or parts.username
        or parts.password
        or parts.port not in (None, 443)
    ):
        raise SkipArticle("URL is outside the configured HTTPS news sources.")

    delay = check_robots(session, url)
    time.sleep(delay)

    html, content_type = download(session, url)

    if not any(
        value in content_type
        for value in ("text/html", "application/xhtml+xml")
    ):
        raise SkipArticle("The URL did not return an HTML webpage.")

    text = trafilatura.extract(
        html,
        url=url,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        favor_precision=True
    )

    if not text or len(text.split()) < MIN_WORDS:
        raise ValueError(
            "Too little article text was extracted; RSS text has been retained."
        )

    return text.strip()


def extract_batch(limit=5, retry_failed=False):
    initialise_database()

    articles = get_articles_for_extraction(
        limit=limit,
        retry_failed=retry_failed
    )

    if not articles:
        logger.info("No matching articles are waiting for extraction.")
        return 0

    counts = {"success": 0, "failed": 0, "skipped": 0}

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html, application/xhtml+xml, text/plain"
        })

        for article in articles:
            logger.info(
                "Processing article %s: %s",
                article["id"],
                article["title"]
            )

            text = None
            error_message = None

            try:
                text = extract_article(session, article["url"])
                status = "success"

            except SkipArticle as error:
                status = "skipped"
                error_message = str(error)

            except (requests.RequestException, ValueError) as error:
                status = "failed"
                error_message = str(error)

            save_extraction_result(
                article_id=article["id"],
                status=status,
                text=text,
                error=error_message
            )

            counts[status] += 1

            if status == "success":
                logger.info(
                    "SUCCESS: article %s; %s words extracted.",
                    article["id"],
                    len(text.split())
                )
            else:
                logger.warning(
                    "%s: article %s; %s",
                    status.upper(),
                    article["id"],
                    error_message
                )

            time.sleep(DEFAULT_DELAY)

    logger.info(
        "Finished: %s successful, %s failed, %s skipped.",
        counts["success"],
        counts["failed"],
        counts["skipped"]
    )

    return counts["failed"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Extract article text from stored news URLs."
    )

    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1.")

    failures = extract_batch(
        limit=args.limit,
        retry_failed=args.retry_failed
    )

    raise SystemExit(1 if failures else 0)