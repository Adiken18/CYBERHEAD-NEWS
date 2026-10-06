import ipaddress
import socket
import sqlite3

from datetime import (
    datetime,
    timezone,
)

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    urldefrag,
    urlsplit,
)

from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

import feedparser

from app.database import (
    get_connection,
)

from app.sources import (
    RSS_SOURCES,
)


# =========================================================
# SETTINGS
# =========================================================

TIMEOUT_SECONDS = 30

MAX_FEED_BYTES = (
    5
    * 1024
    * 1024
)


# =========================================================
# CUSTOM ERRORS
# =========================================================

class SourceValidationError(
    ValueError
):
    pass


class DuplicateSourceError(
    ValueError
):
    pass


class SourceNotFoundError(
    ValueError
):
    pass


# =========================================================
# DATABASE INITIALISATION
# =========================================================

def initialise_source_database():
    """
    Create the sources table once during application startup.

    The original six CYBERHEAD feeds are inserted as
    default sources if they are not already present.
    """

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


    with get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (

                id INTEGER
                    PRIMARY KEY
                    AUTOINCREMENT,

                name TEXT
                    NOT NULL
                    COLLATE NOCASE
                    UNIQUE,

                url TEXT
                    NOT NULL
                    UNIQUE,

                enabled INTEGER
                    NOT NULL
                    DEFAULT 1
                    CHECK (
                        enabled IN (0, 1)
                    ),

                created_at TEXT
                    NOT NULL,

                last_checked_at TEXT,

                last_check_status TEXT
                    CHECK (
                        last_check_status
                        IN (
                            'success',
                            'failed'
                        )
                    ),

                last_check_error TEXT
            )
            """
        )


        for source in RSS_SOURCES:

            connection.execute(
                """
                INSERT OR IGNORE
                INTO sources (

                    name,

                    url,

                    enabled,

                    created_at
                )

                VALUES (?, ?, 1, ?)
                """,
                (
                    source[
                        "name"
                    ],

                    source[
                        "url"
                    ],

                    now,
                ),
            )


        connection.commit()


# =========================================================
# URL VALIDATION
# =========================================================

def validate_public_feed_url(
    url
):
    """
    Only allow public HTTP/HTTPS feed addresses.
    """

    if not isinstance(
        url,
        str
    ):

        raise SourceValidationError(
            "Feed URL must be text."
        )


    url = (
        url.strip()
    )


    if not url:

        raise SourceValidationError(
            "Feed URL cannot be empty."
        )


    url, _ = (
        urldefrag(
            url
        )
    )


    try:

        parts = (
            urlsplit(
                url
            )
        )

    except ValueError as error:

        raise SourceValidationError(
            "Invalid feed URL."
        ) from error


    if parts.scheme not in (
        "http",
        "https",
    ):

        raise SourceValidationError(
            "Feed URL must use HTTP or HTTPS."
        )


    if not parts.hostname:

        raise SourceValidationError(
            "Feed URL must contain a hostname."
        )


    if (
        parts.username
        or
        parts.password
    ):

        raise SourceValidationError(
            "Feed URLs containing credentials "
            "are not allowed."
        )


    try:

        port = (
            parts.port
            or (
                443
                if parts.scheme
                == "https"
                else 80
            )
        )

    except ValueError as error:

        raise SourceValidationError(
            "Invalid URL port."
        ) from error


    try:

        addresses = (
            socket.getaddrinfo(
                parts.hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        )

    except socket.gaierror as error:

        raise SourceValidationError(
            "The feed hostname could "
            "not be resolved."
        ) from error


    if not addresses:

        raise SourceValidationError(
            "The feed hostname could "
            "not be resolved."
        )


    for address in addresses:

        raw_ip = (
            address[4][0]
        )


        raw_ip = (
            raw_ip.split(
                "%"
            )[0]
        )


        try:

            ip = (
                ipaddress.ip_address(
                    raw_ip
                )
            )

        except ValueError as error:

            raise SourceValidationError(
                "The feed resolved to "
                "an invalid IP address."
            ) from error


        if not ip.is_global:

            raise SourceValidationError(
                "Private, local or reserved "
                "feed addresses are not allowed."
            )


    return url


# =========================================================
# SAFE REDIRECTS
# =========================================================

class SafeRedirectHandler(
    HTTPRedirectHandler
):

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):

        validate_public_feed_url(
            newurl
        )


        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )


# =========================================================
# DOWNLOAD FEED
# =========================================================

def download_feed(
    url
):

    url = (
        validate_public_feed_url(
            url
        )
    )


    request = Request(

        url,

        headers={
            "User-Agent":
                (
                    "CYBERHEAD-News/0.2 "
                    "(RSS collector)"
                ),

            "Accept":
                (
                    "application/rss+xml, "
                    "application/atom+xml, "
                    "application/xml, "
                    "text/xml"
                ),
        },
    )


    opener = (
        build_opener(
            SafeRedirectHandler()
        )
    )


    try:

        with opener.open(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:

            final_url = (
                response.geturl()
            )


            validate_public_feed_url(
                final_url
            )


            data = (
                response.read(
                    MAX_FEED_BYTES
                    + 1
                )
            )


    except (
        HTTPError,
        URLError,
        OSError,
    ) as error:

        raise SourceValidationError(
            f"Feed could not be downloaded: "
            f"{error}"
        ) from error


    if (
        len(data)
        > MAX_FEED_BYTES
    ):

        raise SourceValidationError(
            "Feed exceeds the 5 MB size limit."
        )


    return (
        data,
        final_url,
    )


# =========================================================
# TEST RSS / ATOM FEED
# =========================================================

def test_feed_url(
    url
):

    (
        feed_bytes,
        final_url,
    ) = download_feed(
        url
    )


    feed = (
        feedparser.parse(
            feed_bytes
        )
    )


    if not feed.get(
        "version"
    ):

        raise SourceValidationError(
            "The supplied URL is not a "
            "recognised RSS or Atom feed."
        )


    feed_title = (
        str(
            feed.feed.get(
                "title",
                ""
            )
            or ""
        ).strip()
    )


    warning = None


    if feed.bozo:

        warning = (
            str(
                feed.bozo_exception
            )
        )


    return {

        "valid":
            True,

        "feed_title":
            (
                feed_title
                or None
            ),

        "feed_type":
            feed.get(
                "version"
            ),

        "entry_count":
            len(
                feed.entries
            ),

        "final_url":
            final_url,

        "parsing_warning":
            warning,
    }


# =========================================================
# READ ALL SOURCES
# =========================================================

def get_sources():
    """
    Read sources only.

    IMPORTANT:
    This function does NOT initialise or write to
    the database. GET /api/sources therefore stays
    a read-only request.
    """

    with get_connection() as connection:

        rows = (
            connection.execute(
                """
                SELECT

                    s.id,

                    s.name,

                    s.url,

                    s.enabled,

                    s.created_at,

                    s.last_checked_at,

                    s.last_check_status,

                    s.last_check_error,

                    COUNT(
                        a.id
                    ) AS article_count,

                    MAX(
                        COALESCE(
                            a.published_at,
                            a.collected_at
                        )
                    ) AS latest_article_at

                FROM sources s

                LEFT JOIN articles a

                    ON a.source = s.name

                GROUP BY
                    s.id,
                    s.name,
                    s.url,
                    s.enabled,
                    s.created_at,
                    s.last_checked_at,
                    s.last_check_status,
                    s.last_check_error

                ORDER BY
                    s.id
                """
            ).fetchall()
        )


    results = []


    for row in rows:

        source = (
            dict(row)
        )


        source[
            "enabled"
        ] = bool(
            source[
                "enabled"
            ]
        )


        results.append(
            source
        )


    return results


# =========================================================
# READ ONE SOURCE
# =========================================================

def get_source(
    source_id
):

    with get_connection() as connection:

        row = (
            connection.execute(
                """
                SELECT

                    s.id,

                    s.name,

                    s.url,

                    s.enabled,

                    s.created_at,

                    s.last_checked_at,

                    s.last_check_status,

                    s.last_check_error,

                    COUNT(
                        a.id
                    ) AS article_count,

                    MAX(
                        COALESCE(
                            a.published_at,
                            a.collected_at
                        )
                    ) AS latest_article_at

                FROM sources s

                LEFT JOIN articles a

                    ON a.source = s.name

                WHERE
                    s.id = ?

                GROUP BY
                    s.id,
                    s.name,
                    s.url,
                    s.enabled,
                    s.created_at,
                    s.last_checked_at,
                    s.last_check_status,
                    s.last_check_error
                """,
                (
                    source_id,
                ),
            ).fetchone()
        )


    if row is None:

        return None


    result = (
        dict(row)
    )


    result[
        "enabled"
    ] = bool(
        result[
            "enabled"
        ]
    )


    return result


# =========================================================
# ENABLED SOURCES
# =========================================================

def get_enabled_sources():

    with get_connection() as connection:

        rows = (
            connection.execute(
                """
                SELECT

                    id,

                    name,

                    url

                FROM sources

                WHERE enabled = 1

                ORDER BY id
                """
            ).fetchall()
        )


    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# ADD SOURCE
# =========================================================

def add_source(
    name,
    url
):

    name = (
        str(
            name
            or ""
        ).strip()
    )


    if not name:

        raise SourceValidationError(
            "Source name cannot be empty."
        )


    if len(name) > 100:

        raise SourceValidationError(
            "Source name must be "
            "100 characters or fewer."
        )


    url = (
        validate_public_feed_url(
            url
        )
    )


    with get_connection() as connection:

        duplicate = (
            connection.execute(
                """
                SELECT
                    id,
                    name,
                    url

                FROM sources

                WHERE
                    lower(name)
                    = lower(?)

                OR
                    url = ?

                LIMIT 1
                """,
                (
                    name,
                    url,
                ),
            ).fetchone()
        )


    if duplicate:

        raise DuplicateSourceError(
            "A source with this name "
            "or feed URL already exists."
        )


    test_result = (
        test_feed_url(
            url
        )
    )


    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


    try:

        with get_connection() as connection:

            cursor = (
                connection.execute(
                    """
                    INSERT INTO sources (

                        name,

                        url,

                        enabled,

                        created_at,

                        last_checked_at,

                        last_check_status,

                        last_check_error
                    )

                    VALUES (
                        ?,
                        ?,
                        1,
                        ?,
                        ?,
                        'success',
                        NULL
                    )
                    """,
                    (
                        name,
                        url,
                        now,
                        now,
                    ),
                )
            )


            source_id = (
                cursor.lastrowid
            )


            connection.commit()


    except sqlite3.IntegrityError as error:

        raise DuplicateSourceError(
            "A source with this name "
            "or feed URL already exists."
        ) from error


    return {

        "source":
            get_source(
                source_id
            ),

        "feed_test":
            test_result,
    }


# =========================================================
# ENABLE / DISABLE SOURCE
# =========================================================

def set_source_enabled(
    source_id,
    enabled
):

    enabled_value = (
        1
        if enabled
        else 0
    )


    with get_connection() as connection:

        cursor = (
            connection.execute(
                """
                UPDATE sources

                SET enabled = ?

                WHERE id = ?
                """,
                (
                    enabled_value,
                    source_id,
                ),
            )
        )


        connection.commit()


    if cursor.rowcount == 0:

        raise SourceNotFoundError(
            "Source not found."
        )


    return get_source(
        source_id
    )


# =========================================================
# SAVE COLLECTION STATUS
# =========================================================

def mark_source_check(
    source_id,
    success,
    error=None,
):

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


    status = (
        "success"
        if success
        else "failed"
    )


    with get_connection() as connection:

        connection.execute(
            """
            UPDATE sources

            SET
                last_checked_at = ?,

                last_check_status = ?,

                last_check_error = ?

            WHERE id = ?
            """,
            (
                now,

                status,

                (
                    None
                    if success
                    else str(
                        error
                    )
                ),

                source_id,
            ),
        )


        connection.commit()