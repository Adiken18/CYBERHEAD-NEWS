import json
import sqlite3
from contextlib import closing

from app.database import DATABASE_PATH


CURRENT_BRIEFING_ID = 1


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# =========================================================
# DATABASE INITIALISATION
# =========================================================

def initialise_briefing_database():
    """
    Create the tables required for the current
    CYBERHEAD Daily Briefing.

    Only one current briefing is stored.
    Every refresh replaces the previous briefing.
    """

    with closing(
        get_connection()
    ) as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_briefing (

                id INTEGER PRIMARY KEY
                    CHECK (id = 1),

                briefing_date TEXT NOT NULL,

                period_start TEXT NOT NULL,

                period_end TEXT NOT NULL,

                generated_at TEXT NOT NULL,

                total_considered INTEGER
                    NOT NULL DEFAULT 0,

                critical_count INTEGER
                    NOT NULL DEFAULT 0,

                high_count INTEGER
                    NOT NULL DEFAULT 0,

                medium_count INTEGER
                    NOT NULL DEFAULT 0,

                low_count INTEGER
                    NOT NULL DEFAULT 0,

                category_counts_json TEXT
                    NOT NULL DEFAULT '{}',

                status TEXT NOT NULL
                    CHECK (
                        status IN (
                            'success',
                            'failed'
                        )
                    ),

                error TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_briefing_items (

                briefing_id INTEGER NOT NULL

                    REFERENCES daily_briefing(id)
                    ON DELETE CASCADE,

                rank INTEGER NOT NULL,

                article_id INTEGER NOT NULL

                    REFERENCES articles(id)
                    ON DELETE RESTRICT,

                ranking_score INTEGER NOT NULL,

                is_critical INTEGER
                    NOT NULL DEFAULT 0
                    CHECK (
                        is_critical IN (0, 1)
                    ),

                PRIMARY KEY (
                    briefing_id,
                    rank
                ),

                UNIQUE (
                    briefing_id,
                    article_id
                )
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_daily_briefing_items_article

            ON daily_briefing_items(
                article_id
            )
            """
        )

        connection.commit()


# =========================================================
# SAVE CURRENT BRIEFING
# =========================================================

def replace_current_briefing(
    briefing_date,
    period_start,
    period_end,
    generated_at,
    total_considered,
    severity_counts,
    category_counts,
    items,
):
    """
    Replace the current briefing.

    CYBERHEAD currently keeps only one current
    rolling Daily Briefing instead of an archive.
    """

    initialise_briefing_database()

    with closing(
        get_connection()
    ) as connection:

        try:

            connection.execute(
                "BEGIN"
            )

            # Remove the old ranked items.
            connection.execute(
                """
                DELETE FROM daily_briefing_items
                WHERE briefing_id = ?
                """,
                (
                    CURRENT_BRIEFING_ID,
                )
            )

            # Create or update the briefing record.
            connection.execute(
                """
                INSERT INTO daily_briefing (

                    id,

                    briefing_date,

                    period_start,

                    period_end,

                    generated_at,

                    total_considered,

                    critical_count,

                    high_count,

                    medium_count,

                    low_count,

                    category_counts_json,

                    status,

                    error

                )

                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    'success',
                    NULL
                )

                ON CONFLICT(id) DO UPDATE SET

                    briefing_date =
                        excluded.briefing_date,

                    period_start =
                        excluded.period_start,

                    period_end =
                        excluded.period_end,

                    generated_at =
                        excluded.generated_at,

                    total_considered =
                        excluded.total_considered,

                    critical_count =
                        excluded.critical_count,

                    high_count =
                        excluded.high_count,

                    medium_count =
                        excluded.medium_count,

                    low_count =
                        excluded.low_count,

                    category_counts_json =
                        excluded.category_counts_json,

                    status = 'success',

                    error = NULL
                """,
                (
                    CURRENT_BRIEFING_ID,

                    briefing_date,

                    period_start,

                    period_end,

                    generated_at,

                    total_considered,

                    severity_counts.get(
                        "Critical",
                        0
                    ),

                    severity_counts.get(
                        "High",
                        0
                    ),

                    severity_counts.get(
                        "Medium",
                        0
                    ),

                    severity_counts.get(
                        "Low",
                        0
                    ),

                    json.dumps(
                        category_counts
                    ),
                )
            )

            # Save ranked briefing articles.
            for item in items:

                connection.execute(
                    """
                    INSERT INTO daily_briefing_items (

                        briefing_id,

                        rank,

                        article_id,

                        ranking_score,

                        is_critical

                    )

                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        CURRENT_BRIEFING_ID,

                        item[
                            "rank"
                        ],

                        item[
                            "article_id"
                        ],

                        item[
                            "ranking_score"
                        ],

                        item[
                            "is_critical"
                        ],
                    )
                )

            connection.commit()

        except Exception:

            connection.rollback()

            raise


# =========================================================
# READ CURRENT BRIEFING
# =========================================================

def get_current_briefing():
    """
    Return the current briefing together with
    all selected articles.
    """

    initialise_briefing_database()

    with closing(
        get_connection()
    ) as connection:

        briefing_row = (
            connection.execute(
                """
                SELECT *
                FROM daily_briefing
                WHERE id = ?
                """,
                (
                    CURRENT_BRIEFING_ID,
                )
            ).fetchone()
        )

        if briefing_row is None:

            return None

        article_rows = (
            connection.execute(
                """
                SELECT

                    daily_briefing_items.rank,

                    daily_briefing_items.ranking_score,

                    daily_briefing_items.is_critical,

                    articles.id AS article_id,

                    articles.title,

                    articles.url,

                    articles.source,

                    articles.published_at,

                    articles.collected_at,

                    articles.category,

                    articles.severity,

                    articles.severity_score,

                    articles.summary,

                    articles.why_it_matters,

                    articles.recommendations

                FROM daily_briefing_items

                JOIN articles

                    ON articles.id =
                       daily_briefing_items.article_id

                WHERE daily_briefing_items.briefing_id = ?

                ORDER BY
                    daily_briefing_items.rank
                """,
                (
                    CURRENT_BRIEFING_ID,
                )
            ).fetchall()
        )

        briefing = dict(
            briefing_row
        )

        try:

            briefing[
                "category_counts"
            ] = json.loads(
                briefing[
                    "category_counts_json"
                ]
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            briefing[
                "category_counts"
            ] = {}

        briefing[
            "articles"
        ] = [
            dict(row)
            for row in article_rows
        ]

        return briefing