import sqlite3
from contextlib import closing
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "cyberhead.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
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