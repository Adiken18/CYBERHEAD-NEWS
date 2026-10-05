import argparse
import logging
import sqlite3
import time

from datetime import (
    datetime,
    timezone,
)

from app.collector import collect_all

from app.extractor import (
    extract_batch,
)

from app.cve_extractor import (
    extract_cves,
)

from app.cve_enricher import (
    enrich_cves,
)

from app.cisa_enricher import (
    enrich_cisa_kev,
)

from app.category_classifier import (
    classify_articles,
)

from app.tag_extractor import (
    process_articles as process_tags,
)

from app.severity_engine import (
    process_articles as process_severity,
)

from app.summarizer import (
    process_articles as process_summaries,
)

from app.daily_briefing import (
    generate_daily_briefing,
)

from app.database import (
    initialise_database,
    DATABASE_PATH,
)


logger = logging.getLogger(
    __name__
)


# =========================================================
# DISPLAY HELPERS
# =========================================================

def print_stage(
    number,
    title
):
    print()

    print(
        "=" * 70
    )

    print(
        f"STAGE {number}: {title}"
    )

    print(
        "=" * 70
    )


# =========================================================
# DATABASE SUMMARY
# =========================================================

def print_pipeline_summary():
    """
    Display the current processing state of
    the CYBERHEAD database.
    """

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:

        # =================================================
        # ARTICLE COUNTS
        # =================================================

        total_articles = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                """
            ).fetchone()[0]
        )

        extracted = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE extraction_status = 'success'
                """
            ).fetchone()[0]
        )

        classified = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles

                WHERE category IS NOT NULL

                  AND trim(category) <> ''
                """
            ).fetchone()[0]
        )

        tagged = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE tagging_status = 'success'
                """
            ).fetchone()[0]
        )

        # =================================================
        # SEVERITY COUNTS
        # =================================================

        severity_success = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE severity_status = 'success'
                """
            ).fetchone()[0]
        )

        severity_scored = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles

                WHERE severity_status = 'success'

                  AND severity IS NOT NULL
                """
            ).fetchone()[0]
        )

        severity_excluded = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles

                WHERE severity_status = 'success'

                  AND severity IS NULL
                """
            ).fetchone()[0]
        )

        severity_failed = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE severity_status = 'failed'
                """
            ).fetchone()[0]
        )

        # =================================================
        # SUMMARY COUNTS
        # =================================================

        summary_success = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE summary_status = 'success'
                """
            ).fetchone()[0]
        )

        summary_excluded = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE summary_status = 'excluded'
                """
            ).fetchone()[0]
        )

        summary_failed = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE summary_status = 'failed'
                """
            ).fetchone()[0]
        )

        summary_pending = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM articles
                WHERE summary_status = 'pending'
                """
            ).fetchone()[0]
        )

        # =================================================
        # DISPLAY DATABASE SUMMARY
        # =================================================

        print()

        print(
            "=" * 70
        )

        print(
            "CYBERHEAD PIPELINE DATABASE SUMMARY"
        )

        print(
            "=" * 70
        )

        print(
            f"Total articles:        "
            f"{total_articles}"
        )

        print(
            f"Extraction successful: "
            f"{extracted}"
        )

        print(
            f"Category classified:   "
            f"{classified}"
        )

        print(
            f"Tagging processed:     "
            f"{tagged}"
        )

        print(
            f"Severity processed:    "
            f"{severity_success}"
        )

        print(
            f"Severity scored:       "
            f"{severity_scored}"
        )

        print(
            f"Severity excluded:     "
            f"{severity_excluded}"
        )

        print(
            f"Severity failed:       "
            f"{severity_failed}"
        )

        print(
            f"Summary successful:    "
            f"{summary_success}"
        )

        print(
            f"Summary excluded:      "
            f"{summary_excluded}"
        )

        print(
            f"Summary failed:        "
            f"{summary_failed}"
        )

        print(
            f"Summary pending:       "
            f"{summary_pending}"
        )

        # =================================================
        # SEVERITY DISTRIBUTION
        # =================================================

        print()

        print(
            "Severity distribution:"
        )

        rows = (
            connection.execute(
                """
                SELECT

                    severity,

                    COUNT(*) AS total

                FROM articles

                WHERE severity IS NOT NULL

                GROUP BY severity

                ORDER BY

                    CASE severity

                        WHEN 'Critical'
                        THEN 1

                        WHEN 'High'
                        THEN 2

                        WHEN 'Medium'
                        THEN 3

                        WHEN 'Low'
                        THEN 4

                        ELSE 5

                    END
                """
            ).fetchall()
        )

        if not rows:

            print(
                "  No severity results yet."
            )

        for row in rows:

            print(
                f"  {row['severity']:8s}: "
                f"{row['total']}"
            )

    finally:

        connection.close()


# =========================================================
# PIPELINE
# =========================================================

def run_pipeline(
    article_limit=500,
    nvd_limit=100,
    skip_collect=False,
):
    """
    Run the complete CYBERHEAD processing pipeline.

    Order:

    1. Collect articles

    2. Extract full article text

    3. Extract CVE identifiers

    4. Classify article category using ML

    5. Enrich CVEs using NVD

    6. Check CISA Known Exploited Vulnerabilities

    7. Extract threat tags

    8. Calculate threat severity

    9. Generate NLP article summaries

    10. Refresh the rolling 24-hour Daily Briefing
    """

    start_time = time.time()

    started_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    print()

    print(
        "=" * 70
    )

    print(
        "CYBERHEAD NEWS AUTOMATIC PIPELINE"
    )

    print(
        "=" * 70
    )

    print(
        f"Started: {started_at}"
    )

    initialise_database()

    warnings = []


    # =====================================================
    # STAGE 1 - ARTICLE COLLECTION
    # =====================================================

    if skip_collect:

        print_stage(
            1,
            "ARTICLE COLLECTION - SKIPPED"
        )

        print(
            "Collection was skipped "
            "for this test run."
        )

    else:

        print_stage(
            1,
            "ARTICLE COLLECTION"
        )

        try:

            source_failures = (
                collect_all()
            )

            if source_failures:

                warning = (
                    f"{source_failures} source(s) "
                    f"failed during collection."
                )

                warnings.append(
                    warning
                )

                logger.warning(
                    warning
                )

        except Exception as error:

            warning = (
                "Article collection encountered "
                f"an error: {error}"
            )

            warnings.append(
                warning
            )

            logger.exception(
                "Collection stage failed."
            )

            # Do not stop here.
            #
            # Articles successfully collected from
            # other sources can still continue
            # through the pipeline.


    # =====================================================
    # STAGE 2 - FULL-TEXT EXTRACTION
    # =====================================================

    print_stage(
        2,
        "FULL-TEXT EXTRACTION"
    )

    try:

        extraction_failures = (
            extract_batch(

                limit=article_limit,

                retry_failed=True,
            )
        )

        if extraction_failures:

            warnings.append(
                f"{extraction_failures} article(s) "
                f"failed text extraction."
            )

    except Exception as error:

        warnings.append(
            f"Extraction stage error: "
            f"{error}"
        )

        logger.exception(
            "Extraction stage failed."
        )


    # =====================================================
    # STAGE 3 - CVE EXTRACTION
    # =====================================================

    print_stage(
        3,
        "CVE EXTRACTION"
    )

    try:

        extract_cves()

    except Exception:

        logger.exception(
            "CVE extraction failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "CVE extraction must work before "
            "security enrichment can continue."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 4 - ML CATEGORY CLASSIFICATION
    # =====================================================

    print_stage(
        4,
        "ML CATEGORY CLASSIFICATION"
    )

    try:

        classify_articles(
            limit=article_limit
        )

    except Exception:

        logger.exception(
            "Category classification failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "Category classification must "
            "be available before threat tagging "
            "and severity analysis."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 5 - NVD CVE ENRICHMENT
    # =====================================================

    print_stage(
        5,
        "NVD CVE ENRICHMENT"
    )

    try:

        nvd_errors = (
            enrich_cves(
                limit=nvd_limit
            )
        )

    except Exception:

        logger.exception(
            "NVD enrichment failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "Threat analysis has NOT continued "
            "because NVD enrichment failed."
        )

        print_pipeline_summary()

        return 1


    if nvd_errors:

        print()

        print(
            "NVD enrichment reported "
            "one or more errors."
        )

        print(
            "The pipeline will stop before "
            "threat tags and severity so "
            "incomplete vulnerability data "
            "does not produce misleading scores."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 6 - CISA KEV
    # =====================================================

    print_stage(
        6,
        "CISA KNOWN EXPLOITED VULNERABILITIES"
    )

    try:

        enrich_cisa_kev()

    except Exception:

        logger.exception(
            "CISA enrichment failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "Threat analysis has NOT continued "
            "because CISA KEV data could not "
            "be checked."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 7 - THREAT TAG EXTRACTION
    # =====================================================

    print_stage(
        7,
        "THREAT TAG EXTRACTION"
    )

    try:

        process_tags(

            limit=article_limit,

            retry_failed=True,
        )

    except Exception:

        logger.exception(
            "Threat-tag extraction failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "Severity analysis has NOT been run "
            "because threat tagging failed."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 8 - SEVERITY ANALYSIS
    # =====================================================

    print_stage(
        8,
        "SEVERITY ANALYSIS"
    )

    try:

        process_severity(

            limit=article_limit,

            retry_failed=True,
        )

    except Exception:

        logger.exception(
            "Severity analysis failed."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 9 - ARTICLE SUMMARIZATION
    # =====================================================

    print_stage(
        9,
        "NLP ARTICLE SUMMARIZATION"
    )

    try:

        process_summaries(

            limit=article_limit,

            retry_failed=True,
        )

    except Exception:

        logger.exception(
            "Article summarization failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "Article summaries could "
            "not be generated."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # STAGE 10 - DAILY BRIEFING
    # =====================================================

    print_stage(
        10,
        "ROLLING 24-HOUR DAILY BRIEFING"
    )

    try:

        briefing = (
            generate_daily_briefing(

                hours=24,

                minimum_articles=5,
            )
        )

        selected_articles = (
            briefing.get(
                "articles",
                []
            )
            if briefing
            else []
        )

        print(
            "Daily Briefing refreshed successfully."
        )

        print(
            f"Articles considered "
            f"in last 24 hours: "
            f"{briefing['total_considered']}"
        )

        print(
            f"Critical threats "
            f"in last 24 hours: "
            f"{briefing['critical_count']}"
        )

        print(
            f"High threats "
            f"in last 24 hours: "
            f"{briefing['high_count']}"
        )

        print(
            f"Medium threats "
            f"in last 24 hours: "
            f"{briefing['medium_count']}"
        )

        print(
            f"Low threats "
            f"in last 24 hours: "
            f"{briefing['low_count']}"
        )

        print(
            f"Articles included "
            f"in Daily Briefing: "
            f"{len(selected_articles)}"
        )

        # -------------------------------------------------
        # DISPLAY SELECTED THREAT TITLES
        # -------------------------------------------------

        if selected_articles:

            print()

            print(
                "Current Daily Briefing:"
            )

            for article in (
                selected_articles
            ):

                print(
                    f"  #{article['rank']} "
                    f"[{article['severity']} "
                    f"{article['severity_score']}/100] "
                    f"{article['title']}"
                )

        else:

            print(
                "No qualifying articles "
                "were selected."
            )

    except Exception:

        logger.exception(
            "Daily Briefing refresh failed."
        )

        print()

        print(
            "PIPELINE STOPPED."
        )

        print(
            "The article-processing stages "
            "completed, but the Daily Briefing "
            "could not be refreshed."
        )

        print_pipeline_summary()

        return 1


    # =====================================================
    # PIPELINE COMPLETE
    # =====================================================

    duration = (
        time.time()
        - start_time
    )

    print_pipeline_summary()

    print()

    print(
        "=" * 70
    )

    print(
        "PIPELINE COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"Duration: "
        f"{duration:.1f} seconds"
    )

    if warnings:

        print()

        print(
            "Completed with warnings:"
        )

        for warning in warnings:

            print(
                f"  - {warning}"
            )

    else:

        print(
            "No pipeline warnings."
        )

    return 0


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

    parser = argparse.ArgumentParser(
        description=(
            "Run the complete CYBERHEAD "
            "news-processing pipeline."
        )
    )

    parser.add_argument(

        "--limit",

        type=int,

        default=500,

        help=(
            "Maximum number of articles "
            "processed by each article stage."
        ),
    )

    parser.add_argument(

        "--nvd-limit",

        type=int,

        default=100,

        help=(
            "Maximum number of CVEs "
            "looked up from NVD "
            "during this run."
        ),
    )

    parser.add_argument(

        "--skip-collect",

        action="store_true",

        help=(
            "Do not collect new RSS articles. "
            "Useful when testing the pipeline."
        ),
    )

    args = parser.parse_args()


    if args.limit < 1:

        parser.error(
            "--limit must be at least 1."
        )


    if args.nvd_limit < 1:

        parser.error(
            "--nvd-limit must be at least 1."
        )


    exit_code = run_pipeline(

        article_limit=
            args.limit,

        nvd_limit=
            args.nvd_limit,

        skip_collect=
            args.skip_collect,
    )


    raise SystemExit(
        exit_code
    )