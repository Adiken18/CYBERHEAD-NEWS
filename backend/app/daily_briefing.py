import argparse
import sqlite3

from collections import Counter

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.database import (
    DATABASE_PATH,
    initialise_database,
)

from app.briefing_database import (
    initialise_briefing_database,
    replace_current_briefing,
    get_current_briefing,
)


DEFAULT_HOURS = 24

DEFAULT_MINIMUM_ARTICLES = 5


# =========================================================
# DATE HELPERS
# =========================================================

def parse_datetime(value):
    """
    Convert stored article dates into UTC datetimes.

    Returns None if the value cannot be parsed.
    """

    if not value:

        return None

    value = value.strip()

    # Convert Z format into Python-compatible UTC offset.
    if value.endswith("Z"):

        value = (
            value[:-1]
            + "+00:00"
        )

    try:

        result = datetime.fromisoformat(
            value
        )

    except ValueError:

        return None

    # If the date had no timezone, assume UTC.
    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )

    return result.astimezone(
        timezone.utc
    )


def get_article_time(article):
    """
    Prefer the real publication time.

    If publication time is unavailable or invalid,
    fall back to the time CYBERHEAD collected it.
    """

    published = parse_datetime(
        article.get(
            "published_at"
        )
    )

    if published is not None:

        return published

    collected = parse_datetime(
        article.get(
            "collected_at"
        )
    )

    return collected


# =========================================================
# GET ARTICLES FROM THE LAST 24 HOURS
# =========================================================

def get_briefing_candidates(
    period_start,
    period_end,
):
    """
    Get fully analysed articles inside the rolling
    briefing period.

    Time filtering happens BEFORE threat ranking.
    """

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:

        rows = connection.execute(
            """
            SELECT

                id,

                title,

                url,

                source,

                published_at,

                collected_at,

                category,

                severity,

                severity_score,

                summary,

                why_it_matters,

                recommendations

            FROM articles

            WHERE summary_status = 'success'

              AND severity_status = 'success'

              AND severity IS NOT NULL

              AND severity_score IS NOT NULL

            ORDER BY id DESC
            """
        ).fetchall()

    finally:

        connection.close()

    candidates = []

    for row in rows:

        article = dict(
            row
        )

        article_time = (
            get_article_time(
                article
            )
        )

        if article_time is None:

            continue

        # IMPORTANT:
        #
        # Only articles from this time window
        # become ranking candidates.
        if (
            period_start
            <= article_time
            <= period_end
        ):

            article[
                "_briefing_time"
            ] = article_time

            candidates.append(
                article
            )

    return candidates


# =========================================================
# GENERAL THREAT SORTING
# =========================================================

def sort_articles(
    articles
):
    """
    Sort articles by:

    1. severity score
    2. publication / collection time
    3. article ID

    Highest values first.
    """

    return sorted(
        articles,
        key=lambda article: (

            article.get(
                "severity_score"
            )
            or 0,

            article[
                "_briefing_time"
            ].timestamp(),

            article[
                "id"
            ],
        ),
        reverse=True,
    )


# =========================================================
# DAILY BRIEFING SELECTION
# =========================================================

def select_briefing_articles(
    articles,
    minimum_articles=5,
):
    """
    CYBERHEAD Daily Briefing selection rule:

    1. Include ALL Critical articles.

    2. If fewer than the minimum number of
       articles were selected, fill remaining
       places using the highest-ranked
       non-Critical articles.

    Example:

        8 Critical articles
        -> all 8 included

        3 Critical articles
        -> 3 Critical + best 2 non-Critical

        0 Critical articles
        -> best 5 non-Critical articles
    """

    critical_articles = [
        article
        for article in articles
        if article.get(
            "severity"
        ) == "Critical"
    ]

    non_critical_articles = [
        article
        for article in articles
        if article.get(
            "severity"
        ) != "Critical"
    ]

    critical_articles = (
        sort_articles(
            critical_articles
        )
    )

    non_critical_articles = (
        sort_articles(
            non_critical_articles
        )
    )

    # ALL critical articles are always included.
    selected = list(
        critical_articles
    )

    # If there are fewer than the minimum,
    # add the best remaining threats.
    remaining_slots = max(
        minimum_articles
        - len(selected),
        0
    )

    if remaining_slots > 0:

        selected.extend(
            non_critical_articles[
                :remaining_slots
            ]
        )

    return selected


# =========================================================
# STATISTICS
# =========================================================

def calculate_severity_counts(
    articles
):
    """
    Count all qualifying articles by severity.
    """

    counts = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
    }

    for article in articles:

        severity = (
            article.get(
                "severity"
            )
        )

        if severity in counts:

            counts[
                severity
            ] += 1

    return counts


def calculate_category_counts(
    articles
):
    """
    Count qualifying articles by category.
    """

    counter = Counter()

    for article in articles:

        category = (
            article.get(
                "category"
            )
            or "Uncategorised"
        )

        counter[
            category
        ] += 1

    return dict(
        counter.most_common()
    )


# =========================================================
# GENERATE DAILY BRIEFING
# =========================================================

def generate_daily_briefing(
    hours=DEFAULT_HOURS,
    minimum_articles=DEFAULT_MINIMUM_ARTICLES,
):
    """
    Generate the current rolling CYBERHEAD
    Daily Briefing.
    """

    initialise_database()

    initialise_briefing_database()

    # Current UTC time.
    period_end = datetime.now(
        timezone.utc
    )

    # Rolling look-back window.
    period_start = (
        period_end
        - timedelta(
            hours=hours
        )
    )

    # Only last-24-hour articles enter here.
    candidates = (
        get_briefing_candidates(
            period_start,
            period_end,
        )
    )

    severity_counts = (
        calculate_severity_counts(
            candidates
        )
    )

    category_counts = (
        calculate_category_counts(
            candidates
        )
    )

    # Apply:
    # ALL Critical
    # + enough remaining threats to reach minimum.
    selected_articles = (
        select_briefing_articles(
            candidates,
            minimum_articles=
                minimum_articles,
        )
    )

    items = []

    for rank, article in enumerate(
        selected_articles,
        start=1,
    ):

        items.append({

            "rank":
                rank,

            "article_id":
                article[
                    "id"
                ],

            "ranking_score":
                article[
                    "severity_score"
                ],

            "is_critical":
                1
                if article[
                    "severity"
                ] == "Critical"
                else 0,
        })

    # Use the computer's local timezone
    # for the displayed briefing date.
    local_now = (
        datetime.now()
        .astimezone()
    )

    replace_current_briefing(

        briefing_date=(
            local_now
            .date()
            .isoformat()
        ),

        period_start=(
            period_start
            .isoformat()
        ),

        period_end=(
            period_end
            .isoformat()
        ),

        generated_at=(
            period_end
            .isoformat()
        ),

        total_considered=len(
            candidates
        ),

        severity_counts=(
            severity_counts
        ),

        category_counts=(
            category_counts
        ),

        items=items,
    )

    return get_current_briefing()


# =========================================================
# DISPLAY HELPERS
# =========================================================

def display_article(
    article
):
    """
    Print one article from the Daily Briefing.
    """

    print()

    print(
        "#"
        + str(
            article[
                "rank"
            ]
        )
        + " "
        + article[
            "title"
        ]
    )

    print(
        f"Severity: "
        f"{article['severity']} "
        f"({article['severity_score']}/100)"
    )

    print(
        f"Category: "
        f"{article['category']}"
    )

    print(
        f"Source: "
        f"{article['source']}"
    )

    print()

    print(
        "Summary:"
    )

    print(
        article[
            "summary"
        ]
        or "Not available."
    )

    print()

    print(
        "Why it matters:"
    )

    print(
        article[
            "why_it_matters"
        ]
        or "Not available."
    )

    print()

    print(
        "Recommendations:"
    )

    print(
        article[
            "recommendations"
        ]
        or "No recommendations available."
    )

    print()

    print(
        "-" * 70
    )


# =========================================================
# DISPLAY BRIEFING
# =========================================================

def display_briefing(
    briefing
):
    """
    Display the current Daily Briefing.
    """

    if briefing is None:

        print(
            "No Daily Briefing exists."
        )

        return

    print()

    print(
        "=" * 70
    )

    print(
        "CYBERHEAD DAILY BRIEFING"
    )

    print(
        "ROLLING LAST 24 HOURS"
    )

    print(
        "=" * 70
    )

    print(
        f"Briefing date: "
        f"{briefing['briefing_date']}"
    )

    print(
        f"Last updated: "
        f"{briefing['generated_at']}"
    )

    print(
        f"Articles considered: "
        f"{briefing['total_considered']}"
    )

    print()

    # =====================================================
    # THREAT OVERVIEW
    # =====================================================

    print(
        "THREAT OVERVIEW"
    )

    print(
        "-" * 70
    )

    print(
        f"Critical: "
        f"{briefing['critical_count']}"
    )

    print(
        f"High:     "
        f"{briefing['high_count']}"
    )

    print(
        f"Medium:   "
        f"{briefing['medium_count']}"
    )

    print(
        f"Low:      "
        f"{briefing['low_count']}"
    )

    # =====================================================
    # CATEGORY OVERVIEW
    # =====================================================

    print()

    print(
        "CATEGORY OVERVIEW"
    )

    print(
        "-" * 70
    )

    category_counts = (
        briefing.get(
            "category_counts",
            {}
        )
    )

    if not category_counts:

        print(
            "No qualifying articles."
        )

    else:

        for category, total in (
            category_counts.items()
        ):

            print(
                f"{category}: "
                f"{total}"
            )

    # =====================================================
    # SELECTED THREATS
    # =====================================================

    articles = briefing.get(
        "articles",
        []
    )

    print()

    print(
        "DAILY BRIEFING THREATS"
    )

    print(
        "-" * 70
    )

    print(
        "Rule: all Critical threats are shown."
    )

    print(
        "If fewer than 5 Critical threats exist, "
        "the highest-ranked remaining threats "
        "are added."
    )

    if not articles:

        print()

        print(
            "No qualifying threats were "
            "found during this period."
        )

        return

    # =====================================================
    # CRITICAL SECTION
    # =====================================================

    critical_articles = [
        article
        for article in articles
        if article[
            "severity"
        ] == "Critical"
    ]

    other_articles = [
        article
        for article in articles
        if article[
            "severity"
        ] != "Critical"
    ]

    if critical_articles:

        print()
        print(
            "=" * 70
        )

        print(
            "CRITICAL THREATS"
        )

        print(
            "=" * 70
        )

        for article in (
            critical_articles
        ):

            display_article(
                article
            )

    # =====================================================
    # OTHER PRIORITY THREATS
    # =====================================================

    if other_articles:

        print()
        print(
            "=" * 70
        )

        print(
            "OTHER PRIORITY THREATS"
        )

        print(
            "=" * 70
        )

        for article in (
            other_articles
        ):

            display_article(
                article
            )

    print()

    print(
        "=" * 70
    )

    print(
        f"Briefing contains "
        f"{len(articles)} article(s)."
    )

    print(
        "=" * 70
    )


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Generate the rolling "
            "CYBERHEAD Daily Briefing."
        )
    )

    parser.add_argument(
        "--hours",
        type=int,
        default=DEFAULT_HOURS,
        help=(
            "Number of previous hours "
            "included in the briefing."
        ),
    )

    parser.add_argument(
        "--minimum",
        type=int,
        default=DEFAULT_MINIMUM_ARTICLES,
        help=(
            "Minimum number of articles "
            "included when enough qualifying "
            "articles exist. All Critical "
            "articles are always included."
        ),
    )

    args = parser.parse_args()

    if args.hours < 1:

        parser.error(
            "--hours must be at least 1."
        )

    if args.minimum < 1:

        parser.error(
            "--minimum must be at least 1."
        )

    briefing = (
        generate_daily_briefing(

            hours=args.hours,

            minimum_articles=
                args.minimum,
        )
    )

    display_briefing(
        briefing
    )