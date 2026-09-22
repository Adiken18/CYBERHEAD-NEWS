import sqlite3
from contextlib import closing
from pathlib import Path

from app.categories import PRIMARY_CATEGORIES


DATABASE_PATH = Path(__file__).resolve().parent.parent / "cyberhead.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise_database():
    with closing(get_connection()) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                published_at TEXT,
                collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                content TEXT,
                category TEXT,
                severity TEXT CHECK (
                    severity IN ('Low', 'Medium', 'High', 'Critical')
                )
            )
        """)
        # Additive upgrade: keep every existing article and its original ID.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                name TEXT PRIMARY KEY NOT NULL
            )
        """)
        connection.executemany(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            [(name,) for name in PRIMARY_CATEGORIES],
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                why_it_matters TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_articles (
                report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE RESTRICT,
                PRIMARY KEY (report_id, article_id)
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_report_articles_article
            ON report_articles(article_id)
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_analysis (
                report_id INTEGER PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
                primary_category TEXT REFERENCES categories(name),
                category_confidence REAL CHECK (
                    category_confidence IS NULL OR
                    category_confidence BETWEEN 0 AND 1
                ),
                predicted_severity TEXT CHECK (
                    predicted_severity IN ('Low', 'Medium', 'High', 'Critical')
                ),
                final_severity TEXT CHECK (
                    final_severity IN ('Low', 'Medium', 'High', 'Critical')
                ),
                severity_reason TEXT,
                recommendations TEXT,
                category_model_version TEXT,
                severity_model_version TEXT,
                rules_version TEXT,
                analysed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_tags (
                report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                tag TEXT NOT NULL CHECK (length(trim(tag)) > 0),
                PRIMARY KEY (report_id, tag)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_cves (
                report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                cve_id TEXT NOT NULL CHECK (length(trim(cve_id)) > 0),
                PRIMARY KEY (report_id, cve_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_affected_systems (
                report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                system_name TEXT NOT NULL CHECK (length(trim(system_name)) > 0),
                PRIMARY KEY (report_id, system_name)
            )
        """)
        connection.commit()


def get_articles():
    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT *
            FROM articles
            ORDER BY collected_at DESC, id DESC
            LIMIT 100
        """).fetchall()

        return [dict(row) for row in rows]

def save_article(title, url, source, published_at=None, content=None):
    """Save an article. Return True if new, False if its URL already exists."""

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO articles (
                title,
                url,
                source,
                published_at,
                content
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
            """,
            (title, url, source, published_at, content)
        )

        connection.commit()

        return cursor.rowcount == 1