import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from app.categories import PRIMARY_CATEGORIES
import json


DATABASE_PATH = Path(__file__).resolve().parent.parent / "cyberhead.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def add_extraction_columns(connection):
    """Add extraction fields without deleting existing articles."""

    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(articles)")
    }

    new_columns = {
        "full_content": "TEXT",

        "extraction_status": """
            TEXT NOT NULL DEFAULT 'pending'
            CHECK (
                extraction_status IN (
                    'pending',
                    'success',
                    'failed',
                    'skipped'
                )
            )
        """,

        "extraction_attempted_at": "TEXT",
        "extracted_at": "TEXT",
        "extraction_error": "TEXT",
    }

    for name, definition in new_columns.items():
        if name not in existing_columns:
            connection.execute(
                f"ALTER TABLE articles ADD COLUMN {name} {definition}"
            )

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

        add_extraction_columns(connection)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS article_cves (
                article_id INTEGER NOT NULL
                    REFERENCES articles(id) ON DELETE CASCADE,
                cve_id TEXT NOT NULL,
                detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (article_id, cve_id)
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_cves_cve
            ON article_cves(cve_id)
        """)

        connection.commit()

        connection.execute("""
            CREATE TABLE IF NOT EXISTS cve_details (
                cve_id TEXT PRIMARY KEY NOT NULL,
                lookup_status TEXT NOT NULL CHECK (
                    lookup_status IN ('found', 'not_found', 'error')
                ),
                record_json TEXT,
                last_checked_at TEXT NOT NULL,
                data_fetched_at TEXT,
                lookup_error TEXT
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS cisa_kev (
                cve_id TEXT PRIMARY KEY NOT NULL,
                vendor_project TEXT,
                product TEXT,
                vulnerability_name TEXT,
                date_added TEXT,
                short_description TEXT,
                required_action TEXT,
                due_date TEXT,
                known_ransomware_campaign_use TEXT,
                notes TEXT,
                last_checked_at TEXT NOT NULL
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

def get_articles_for_extraction(limit=5, retry_failed=False):
    """Return articles waiting for extraction."""

    statuses = ("pending", "failed") if retry_failed else ("pending",)
    placeholders = ", ".join("?" for _ in statuses)

    with closing(get_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT id, title, url
            FROM articles
            WHERE extraction_status IN ({placeholders})
            ORDER BY id DESC
            LIMIT ?
            """,
            (*statuses, limit)
        ).fetchall()

        return [dict(row) for row in rows]


def save_extraction_result(article_id, status, text=None, error=None):
    """Save extraction results without modifying the original RSS text."""

    if status not in ("success", "failed", "skipped"):
        raise ValueError("Invalid extraction result status.")

    if status == "success" and not (text and text.strip()):
        raise ValueError("Successful extraction requires article text.")

    now = datetime.now(timezone.utc).isoformat()
    successful = status == "success"

    with closing(get_connection()) as connection:
        connection.execute(
            """
            UPDATE articles
            SET extraction_status = ?,
                extraction_attempted_at = ?,
                full_content = CASE
                    WHEN ? THEN ? ELSE full_content
                END,
                extracted_at = CASE
                    WHEN ? THEN ? ELSE extracted_at
                END,
                extraction_error = ?
            WHERE id = ?
            """,
            (
                status,
                now,
                successful,
                text,
                successful,
                now,
                None if successful else error,
                article_id
            )
        )

        connection.commit()

def get_article_cves():
    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT
                article_cves.article_id,
                article_cves.cve_id,
                articles.title,
                articles.source,
                articles.url
            FROM article_cves
            JOIN articles
                ON articles.id = article_cves.article_id
            ORDER BY article_cves.article_id DESC,
                     article_cves.cve_id
        """).fetchall()

        return [dict(row) for row in rows]

def get_cves_for_lookup(limit=5):
    """Select new CVEs or cached lookups older than 24 hours."""

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT article_cves.cve_id
            FROM article_cves
            LEFT JOIN cve_details
                ON article_cves.cve_id = cve_details.cve_id
            WHERE cve_details.cve_id IS NULL
               OR datetime(cve_details.last_checked_at)
                    < datetime('now', '-24 hours')
            ORDER BY
                cve_details.last_checked_at ASC,
                article_cves.cve_id ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [row["cve_id"] for row in rows]


def save_cve_lookup(cve_id, status, record=None, error=None):
    """Store a lookup and preserve cached data if a request fails."""

    if status not in ("found", "not_found", "error"):
        raise ValueError("Invalid CVE lookup status.")

    if status == "found" and (
        not isinstance(record, dict) or record.get("id") != cve_id
    ):
        raise ValueError("The returned record does not match the CVE ID.")

    now = datetime.now(timezone.utc).isoformat()
    record_json = json.dumps(record) if record is not None else None
    fetched_at = now if status == "found" else None

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO cve_details (
                cve_id,
                lookup_status,
                record_json,
                last_checked_at,
                data_fetched_at,
                lookup_error
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(cve_id) DO UPDATE SET
                lookup_status = excluded.lookup_status,
                last_checked_at = excluded.last_checked_at,
                lookup_error = excluded.lookup_error,
                record_json = CASE
                    WHEN excluded.lookup_status = 'error'
                    THEN cve_details.record_json
                    ELSE excluded.record_json
                END,
                data_fetched_at = CASE
                    WHEN excluded.lookup_status = 'error'
                    THEN cve_details.data_fetched_at
                    ELSE excluded.data_fetched_at
                END
            """,
            (
                cve_id,
                status,
                record_json,
                now,
                fetched_at,
                error
            )
        )

        connection.commit()


def get_cve_details():
    """Return readable details with all supplied CVSS assessments."""

    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT *
            FROM cve_details
            ORDER BY cve_id
        """).fetchall()

    results = []

    for row in rows:
        record = json.loads(row["record_json"]) if row["record_json"] else {}

        description = next(
            (
                item["value"]
                for item in record.get("descriptions", [])
                if item.get("lang") == "en"
            ),
            None
        )

        scores = []

        for metric_name, assessments in record.get("metrics", {}).items():
            if not metric_name.startswith("cvssMetric"):
                continue

            for assessment in assessments:
                cvss = assessment.get("cvssData", {})

                scores.append({
                    "version": cvss.get("version"),
                    "source": assessment.get("source"),
                    "type": assessment.get("type"),
                    "base_score": cvss.get("baseScore"),
                    "base_severity": (
                        cvss.get("baseSeverity")
                        or assessment.get("baseSeverity")
                    ),
                    "vector": cvss.get("vectorString")
                })

        results.append({
            "cve_id": row["cve_id"],
            "lookup_status": row["lookup_status"],
            "vulnerability_status": record.get("vulnStatus"),
            "description": description,
            "published_at": record.get("published"),
            "modified_at": record.get("lastModified"),
            "cvss_assessments": scores,
            "references": record.get("references", []),
            "last_checked_at": row["last_checked_at"],
            "data_fetched_at": row["data_fetched_at"],
            "lookup_error": row["lookup_error"],
            "nvd_url": (
                "https://nvd.nist.gov/vuln/detail/" + row["cve_id"]
            )
        })

    return results
def get_detected_cve_ids():
    """Return all distinct CVE IDs detected in collected articles."""

    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT DISTINCT cve_id
            FROM article_cves
            ORDER BY cve_id
        """).fetchall()

        return [row["cve_id"] for row in rows]


def save_cisa_kev_record(record):
    """Save or update one CISA Known Exploited Vulnerability record."""

    cve_id = record.get("cveID")

    if not cve_id:
        raise ValueError("CISA KEV record does not contain a CVE ID.")

    now = datetime.now(timezone.utc).isoformat()

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO cisa_kev (
                cve_id,
                vendor_project,
                product,
                vulnerability_name,
                date_added,
                short_description,
                required_action,
                due_date,
                known_ransomware_campaign_use,
                notes,
                last_checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(cve_id) DO UPDATE SET
                vendor_project = excluded.vendor_project,
                product = excluded.product,
                vulnerability_name = excluded.vulnerability_name,
                date_added = excluded.date_added,
                short_description = excluded.short_description,
                required_action = excluded.required_action,
                due_date = excluded.due_date,
                known_ransomware_campaign_use =
                    excluded.known_ransomware_campaign_use,
                notes = excluded.notes,
                last_checked_at = excluded.last_checked_at
            """,
            (
                cve_id,
                record.get("vendorProject"),
                record.get("product"),
                record.get("vulnerabilityName"),
                record.get("dateAdded"),
                record.get("shortDescription"),
                record.get("requiredAction"),
                record.get("dueDate"),
                record.get("knownRansomwareCampaignUse"),
                record.get("notes"),
                now,
            )
        )

        connection.commit()


def get_cisa_kev_details():
    """Return CISA KEV records stored for detected CVEs."""

    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT *
            FROM cisa_kev
            ORDER BY date_added DESC, cve_id
        """).fetchall()

        return [dict(row) for row in rows]

    
def get_articles_for_category_classification(limit=20):
    """Return extracted articles that do not have a category yet."""

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                title,
                full_content,
                content
            FROM articles
            WHERE extraction_status = 'success'
              AND (
                    category IS NULL
                    OR trim(category) = ''
                  )
            ORDER BY id
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [dict(row) for row in rows]


def save_article_category(article_id, category):
    """Save the ML-predicted category for an article."""

    if category not in PRIMARY_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category}"
        )

    with closing(get_connection()) as connection:
        connection.execute(
            """
            UPDATE articles
            SET category = ?
            WHERE id = ?
            """,
            (category, article_id)
        )

        connection.commit()    