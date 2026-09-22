import logging
import re
from contextlib import closing

from app.database import get_connection, initialise_database


logger = logging.getLogger(__name__)

CVE_PATTERN = re.compile(
    r"\bCVE-[0-9]{4}-[0-9]{4,19}\b",
    flags=re.IGNORECASE
)


def find_cves(text):
    """Return unique CVE-shaped identifiers in a consistent format."""

    return sorted({
        match.upper()
        for match in CVE_PATTERN.findall(text or "")
    })


def extract_cves():
    initialise_database()

    articles_with_cves = 0
    new_links = 0

    with closing(get_connection()) as connection:
        articles = connection.execute("""
            SELECT id, title, content, full_content
            FROM articles
            ORDER BY id
        """).fetchall()

        # Commit the batch together; roll back if an error occurs.
        with connection:
            for article in articles:
                text = "\n".join(
                    article[field] or ""
                    for field in ("title", "content", "full_content")
                )

                cve_ids = find_cves(text)

                if not cve_ids:
                    continue

                articles_with_cves += 1

                for cve_id in cve_ids:
                    cursor = connection.execute(
                        """
                        INSERT INTO article_cves (article_id, cve_id)
                        VALUES (?, ?)
                        ON CONFLICT(article_id, cve_id) DO NOTHING
                        """,
                        (article["id"], cve_id)
                    )

                    new_links += cursor.rowcount

                logger.info(
                    "Article %s: %s",
                    article["id"],
                    ", ".join(cve_ids)
                )

        distinct_cves = connection.execute("""
            SELECT COUNT(DISTINCT cve_id)
            FROM article_cves
        """).fetchone()[0]

    logger.info(
        "Finished: %s articles scanned; "
        "%s articles contain CVE IDs; "
        "%s new links saved; "
        "%s distinct CVE IDs stored.",
        len(articles),
        articles_with_cves,
        new_links,
        distinct_cves
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    extract_cves()
    