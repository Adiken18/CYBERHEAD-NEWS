import csv
import json
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone

from app.database import (
    DATABASE_PATH,
    get_connection,
    initialise_database,
)


def get_cvss_assessments(record):
    assessments = []

    for metric_name, values in record.get("metrics", {}).items():
        if not metric_name.startswith("cvssMetric"):
            continue

        for value in values:
            cvss = value.get("cvssData", {})

            assessments.append({
                "version": cvss.get("version"),
                "source": value.get("source"),
                "base_score": cvss.get("baseScore"),
                "base_severity": (
                    cvss.get("baseSeverity")
                    or value.get("baseSeverity")
                )
            })

    return assessments


def export_training_data():
    initialise_database()

    with closing(get_connection()) as connection:
        articles = connection.execute("""
            SELECT
                id,
                title,
                url,
                source,
                published_at,
                content,
                full_content,
                extraction_status
            FROM articles
            ORDER BY id
        """).fetchall()

        cve_rows = connection.execute("""
            SELECT
                article_cves.article_id,
                article_cves.cve_id,
                cve_details.lookup_status,
                cve_details.record_json,
                cve_details.data_fetched_at
            FROM article_cves
            LEFT JOIN cve_details
                ON article_cves.cve_id = cve_details.cve_id
            ORDER BY article_cves.article_id, article_cves.cve_id
        """).fetchall()

    if not articles:
        print("No articles found. Run the collector first.")
        return

    cves_by_article = {}

    for row in cve_rows:
        record = (
            json.loads(row["record_json"])
            if row["record_json"]
            else {}
        )

        evidence = {
            "cve_id": row["cve_id"],
            "lookup_status": row["lookup_status"],
            "vulnerability_status": record.get("vulnStatus"),
            "data_fetched_at": row["data_fetched_at"],
            "cvss_assessments": get_cvss_assessments(record)
        }

        cves_by_article.setdefault(
            row["article_id"], []
        ).append(evidence)

    export_folder = DATABASE_PATH.parent / "data" / "exports"
    export_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_path = (
        export_folder / f"training_articles_{timestamp}.csv"
    )

    fieldnames = [
        "article_id",
        "title",
        "text",
        "text_source",
        "word_count",
        "source",
        "url",
        "published_at",
        "extraction_status",
        "cve_ids",
        "cve_evidence",
        "primary_category_label",
        "severity_label",
        "severity_reason",
        "incident_group",
        "tags",
        "active_exploitation",
        "impact_notes",
        "review_status",
        "review_notes"
    ]

    text_sources = Counter()
    short_articles = 0

    # A new filename avoids overwriting earlier labelling work.
    with output_path.open(
        "x",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for article in articles:
            full_text = (article["full_content"] or "").strip()
            rss_text = (article["content"] or "").strip()

            if full_text:
                text = full_text
                text_source = "webpage"
            elif rss_text:
                text = rss_text
                text_source = "rss"
            else:
                text = ""
                text_source = "missing"

            word_count = len(text.split())
            text_sources[text_source] += 1

            if word_count < 80:
                short_articles += 1

            evidence = cves_by_article.get(article["id"], [])

            writer.writerow({
                "article_id": article["id"],
                "title": article["title"],
                "text": text,
                "text_source": text_source,
                "word_count": word_count,
                "source": article["source"],
                "url": article["url"],
                "published_at": article["published_at"],
                "extraction_status": article["extraction_status"],
                "cve_ids": "; ".join(
                    item["cve_id"] for item in evidence
                ),
                "cve_evidence": json.dumps(
                    evidence,
                    ensure_ascii=False
                ),
                "primary_category_label": "",
                "severity_label": "",
                "severity_reason": "",
                "incident_group": "",
                "tags": "",
                "active_exploitation": "unknown",
                "impact_notes": "",
                "review_status": "pending",
                "review_notes": ""
            })

    print(f"Exported {len(articles)} articles.")
    print(f"Webpage text: {text_sources['webpage']}")
    print(f"RSS fallback: {text_sources['rss']}")
    print(f"Missing text: {text_sources['missing']}")
    print(f"Articles with fewer than 80 words: {short_articles}")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    export_training_data()