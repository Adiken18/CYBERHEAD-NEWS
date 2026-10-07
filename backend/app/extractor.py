import argparse
import logging
import time

from urllib.parse import (
    urlsplit,
)

from urllib.robotparser import (
    RobotFileParser,
)

import requests
import trafilatura

from app.database import (
    initialise_database,
    get_articles_for_extraction,
    save_extraction_result,
)

from app.source_manager import (
    get_sources,
    initialise_source_database,
    validate_public_feed_url,
    SourceValidationError,
)


logger = logging.getLogger(
    __name__
)


# =========================================================
# COLLECTOR IDENTITY
# =========================================================

BOT_NAME = (
    "CyberheadNews"
)

USER_AGENT = (
    "CyberheadNews/0.2 "
    "(academic cybersecurity news collector)"
)


# =========================================================
# ORIGINAL CYBERHEAD ARTICLE DOMAINS
# =========================================================
#
# These are retained for backwards compatibility.
#
# This is especially important for sources such as
# The Hacker News, whose RSS feed may be hosted by a
# different feed provider.
# =========================================================

LEGACY_ALLOWED_HOSTS = {

    # BleepingComputer
    "www.bleepingcomputer.com",
    "bleepingcomputer.com",

    # The Hacker News
    "thehackernews.com",
    "www.thehackernews.com",

    # SecurityWeek
    "securityweek.com",
    "www.securityweek.com",

    # Krebs on Security
    "krebsonsecurity.com",
    "www.krebsonsecurity.com",

    # Dark Reading
    "darkreading.com",
    "www.darkreading.com",

    # Ars Technica
    "arstechnica.com",
    "www.arstechnica.com",
}


# =========================================================
# EXTRACTION SETTINGS
# =========================================================

MAX_PAGE_BYTES = (
    5
    *
    1024
    *
    1024
)

MIN_WORDS = 80

DEFAULT_DELAY = 3


robots_cache = {}


# =========================================================
# CUSTOM ERROR
# =========================================================

class SkipArticle(Exception):
    """
    The article should not be downloaded
    or processed.
    """

    pass


# =========================================================
# HOST HELPERS
# =========================================================

def host_variants(
    hostname
):
    """
    Return normal and www versions
    of a hostname.

    Example:

        securityaffairs.com

    becomes:

        securityaffairs.com
        www.securityaffairs.com
    """

    if not hostname:

        return set()


    hostname = (
        hostname
        .strip()
        .lower()
        .rstrip(".")
    )


    if not hostname:

        return set()


    hosts = {
        hostname
    }


    if hostname.startswith(
        "www."
    ):

        hosts.add(
            hostname[4:]
        )

    else:

        hosts.add(
            f"www.{hostname}"
        )


    return hosts


def get_allowed_article_hosts():
    """
    Build the article-domain allowlist.

    The allowlist contains:

    1. Original CYBERHEAD source domains.
    2. Domains belonging to sources configured
       through the Sources database.

    Disabled sources are also included here so
    articles already collected from a source can
    still complete processing after the source
    has been disabled.
    """

    allowed_hosts = set(
        LEGACY_ALLOWED_HOSTS
    )


    sources = (
        get_sources()
    )


    for source in sources:

        feed_url = (
            source.get(
                "url"
            )
            or ""
        )


        try:

            parts = (
                urlsplit(
                    feed_url
                )
            )

        except ValueError:

            continue


        hostname = (
            parts.hostname
        )


        allowed_hosts.update(
            host_variants(
                hostname
            )
        )


    return allowed_hosts


# =========================================================
# DOWNLOAD
# =========================================================

def download(
    session,
    url
):
    """
    Download one URL.

    Responses are size-limited and redirects
    are not automatically followed.
    """

    with session.get(

        url,

        timeout=(
            10,
            30,
        ),

        allow_redirects=False,

        stream=True,

    ) as response:


        if (
            300
            <=
            response.status_code
            <
            400
        ):

            raise SkipArticle(
                "Redirect received; review the "
                "destination before extracting."
            )


        response.raise_for_status()


        chunks = []

        total_bytes = 0


        for chunk in (
            response.iter_content(
                chunk_size=65536
            )
        ):

            total_bytes += (
                len(chunk)
            )


            if (
                total_bytes
                >
                MAX_PAGE_BYTES
            ):

                raise ValueError(
                    "Response exceeds the "
                    "5 MB size limit."
                )


            chunks.append(
                chunk
            )


        return (

            b"".join(
                chunks
            ),

            response.headers.get(
                "Content-Type",
                ""
            ).lower(),
        )


# =========================================================
# ROBOTS.TXT
# =========================================================

def check_robots(
    session,
    url
):
    """
    Check robots.txt and return the delay
    between requests.
    """

    parts = (
        urlsplit(
            url
        )
    )


    origin = (
        f"{parts.scheme}://"
        f"{parts.netloc}"
    )


    if (
        origin
        not in
        robots_cache
    ):

        robots_url = (
            origin
            +
            "/robots.txt"
        )


        try:

            (
                body,
                content_type,
            ) = download(
                session,
                robots_url
            )


        except requests.HTTPError as error:

            if (
                error.response.status_code
                ==
                404
            ):

                # No robots.txt was published.
                robots_cache[
                    origin
                ] = None

            else:

                raise


        else:

            if (
                "text/html"
                in
                content_type
            ):

                raise ValueError(
                    "Received HTML instead of "
                    "a readable robots.txt."
                )


            parser = (
                RobotFileParser()
            )


            parser.set_url(
                robots_url
            )


            parser.parse(

                body.decode(
                    "utf-8",
                    errors="replace"
                ).splitlines()

            )


            robots_cache[
                origin
            ] = parser


    parser = (
        robots_cache[
            origin
        ]
    )


    if (
        parser is None
    ):

        return DEFAULT_DELAY


    if not parser.can_fetch(
        BOT_NAME,
        url
    ):

        raise SkipArticle(
            "robots.txt disallows "
            "this article URL."
        )


    delay = (
        parser.crawl_delay(
            BOT_NAME
        )
        or
        DEFAULT_DELAY
    )


    rate = (
        parser.request_rate(
            BOT_NAME
        )
    )


    if (
        rate
        and
        rate.requests > 0
    ):

        delay = max(

            delay,

            (
                rate.seconds
                /
                rate.requests
            ),
        )


    return max(
        DEFAULT_DELAY,
        delay
    )


# =========================================================
# ARTICLE EXTRACTION
# =========================================================

def extract_article(
    session,
    url,
    allowed_hosts
):
    """
    Download and extract a configured
    CYBERHEAD source article.
    """

    try:

        validated_url = (
            validate_public_feed_url(
                url
            )
        )


    except SourceValidationError as error:

        raise SkipArticle(
            f"Unsafe article URL: {error}"
        ) from error


    parts = (
        urlsplit(
            validated_url
        )
    )


    hostname = (
        (
            parts.hostname
            or
            ""
        )
        .lower()
        .rstrip(".")
    )


    # -----------------------------------------------------
    # REQUIRE CONFIGURED PUBLIC SOURCE DOMAIN
    # -----------------------------------------------------

    if (
        hostname
        not in
        allowed_hosts
    ):

        raise SkipArticle(
            "Article domain is not associated "
            "with a configured CYBERHEAD source."
        )


    # -----------------------------------------------------
    # HTTP / HTTPS ONLY
    # -----------------------------------------------------

    if (
        parts.scheme
        not in (
            "http",
            "https",
        )
    ):

        raise SkipArticle(
            "Article URL must use HTTP or HTTPS."
        )


    # -----------------------------------------------------
    # NO URL CREDENTIALS
    # -----------------------------------------------------

    if (
        parts.username
        or
        parts.password
    ):

        raise SkipArticle(
            "Article URL contains credentials."
        )


    # -----------------------------------------------------
    # STANDARD WEB PORTS ONLY
    # -----------------------------------------------------

    try:

        port = (
            parts.port
        )

    except ValueError as error:

        raise SkipArticle(
            "Article URL contains an invalid port."
        ) from error


    if (
        parts.scheme == "https"
        and
        port not in (
            None,
            443,
        )
    ):

        raise SkipArticle(
            "HTTPS article uses a "
            "non-standard port."
        )


    if (
        parts.scheme == "http"
        and
        port not in (
            None,
            80,
        )
    ):

        raise SkipArticle(
            "HTTP article uses a "
            "non-standard port."
        )


    # -----------------------------------------------------
    # ROBOTS.TXT
    # -----------------------------------------------------

    delay = (
        check_robots(
            session,
            validated_url
        )
    )


    time.sleep(
        delay
    )


    # -----------------------------------------------------
    # DOWNLOAD ARTICLE
    # -----------------------------------------------------

    (
        html,
        content_type,
    ) = download(
        session,
        validated_url
    )


    if not any(

        value
        in
        content_type

        for value in (
            "text/html",
            "application/xhtml+xml",
        )

    ):

        raise SkipArticle(
            "The URL did not return "
            "an HTML webpage."
        )


    # -----------------------------------------------------
    # MAIN TEXT EXTRACTION
    # -----------------------------------------------------

    text = (
        trafilatura.extract(

            html,

            url=validated_url,

            output_format="txt",

            include_comments=False,

            include_tables=True,

            favor_precision=True,

        )
    )


    if (
        not text
        or
        len(
            text.split()
        )
        <
        MIN_WORDS
    ):

        raise ValueError(
            "Too little article text was "
            "extracted; RSS text has been retained."
        )


    return (
        text.strip()
    )


# =========================================================
# EXTRACTION BATCH
# =========================================================

def extract_batch(
    limit=5,
    retry_failed=False
):
    """
    Extract pending CYBERHEAD articles.
    """

    # Main article database
    initialise_database()


    # Ensure the Sources table exists.
    initialise_source_database()


    allowed_hosts = (
        get_allowed_article_hosts()
    )


    logger.info(
        "Article extractor loaded %s "
        "allowed source host(s).",
        len(
            allowed_hosts
        )
    )


    articles = (
        get_articles_for_extraction(

            limit=limit,

            retry_failed=
                retry_failed,
        )
    )


    if not articles:

        logger.info(
            "No matching articles are "
            "waiting for extraction."
        )

        return 0


    counts = {

        "success":
            0,

        "failed":
            0,

        "skipped":
            0,
    }


    with requests.Session() as session:

        session.headers.update({

            "User-Agent":
                USER_AGENT,

            "Accept":
                (
                    "text/html, "
                    "application/xhtml+xml, "
                    "text/plain"
                ),
        })


        for article in articles:

            logger.info(

                "Processing article %s: %s",

                article[
                    "id"
                ],

                article[
                    "title"
                ],
            )


            text = None

            error_message = None


            try:

                text = (
                    extract_article(

                        session,

                        article[
                            "url"
                        ],

                        allowed_hosts,
                    )
                )


                status = (
                    "success"
                )


            except SkipArticle as error:

                status = (
                    "skipped"
                )

                error_message = (
                    str(error)
                )


            except (
                requests.RequestException,
                ValueError,
            ) as error:

                status = (
                    "failed"
                )

                error_message = (
                    str(error)
                )


            save_extraction_result(

                article_id=
                    article[
                        "id"
                    ],

                status=
                    status,

                text=
                    text,

                error=
                    error_message,
            )


            counts[
                status
            ] += 1


            if (
                status
                ==
                "success"
            ):

                logger.info(

                    "SUCCESS: article %s; "
                    "%s words extracted.",

                    article[
                        "id"
                    ],

                    len(
                        text.split()
                    ),
                )


            else:

                logger.warning(

                    "%s: article %s; %s",

                    status.upper(),

                    article[
                        "id"
                    ],

                    error_message,
                )


            time.sleep(
                DEFAULT_DELAY
            )


    logger.info(

        "Finished: %s successful, "
        "%s failed, %s skipped.",

        counts[
            "success"
        ],

        counts[
            "failed"
        ],

        counts[
            "skipped"
        ],
    )


    return (
        counts[
            "failed"
        ]
    )


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    logging.basicConfig(

        level=logging.INFO,

        format=(
            "%(levelname)s: "
            "%(message)s"
        ),
    )


    parser = (
        argparse.ArgumentParser(

            description=(
                "Extract article text from "
                "stored CYBERHEAD news URLs."
            )
        )
    )


    parser.add_argument(

        "--limit",

        type=int,

        default=5,
    )


    parser.add_argument(

        "--retry-failed",

        action="store_true",
    )


    args = (
        parser.parse_args()
    )


    if (
        args.limit < 1
    ):

        parser.error(
            "--limit must be at least 1."
        )


    failures = (
        extract_batch(

            limit=
                args.limit,

            retry_failed=
                args.retry_failed,
        )
    )


    raise SystemExit(
        1
        if failures
        else 0
    )