import math
import re
import sqlite3

from collections import Counter

from app.database import (
    DATABASE_PATH,
)


# =========================================================
# CURRENT SEVERITY BANDS
# =========================================================

def score_to_severity(score):

    if score >= 70:
        return "Critical"

    if score >= 40:
        return "High"

    if score >= 20:
        return "Medium"

    return "Low"


# =========================================================
# RECONSTRUCT ORIGINAL RAW SCORE
# =========================================================

POINT_PATTERN = re.compile(
    r"\+(\d+)\s*$"
)


def reconstruct_raw_score(
    reason_text,
    stored_score,
):
    """
    Reconstruct the score before the old 100-point cap.

    Example reasons:

        Critical CVSS score 9.8: +35
        CISA KEV: +40
        Remote Code Execution detected: +20

    Raw total:
        95
    """

    if not reason_text:

        return stored_score

    points = []

    for line in reason_text.splitlines():

        match = POINT_PATTERN.search(
            line.strip()
        )

        if match:

            points.append(
                int(
                    match.group(1)
                )
            )

    if not points:

        return stored_score

    return sum(
        points
    )


# =========================================================
# PROPOSED SOFT COMPRESSION
# =========================================================

def proposed_score(
    raw_score
):
    """
    Keep the current score unchanged up to 70.

    Above 70, increasingly compress very large totals.

    This prevents many severe articles from all
    becoming exactly 100/100 while preserving
    the current Critical threshold.
    """

    if raw_score <= 70:

        return raw_score

    compressed = (
        70
        +
        30
        *
        (
            1
            -
            math.exp(
                -(raw_score - 70)
                / 50
            )
        )
    )

    return min(
        round(
            compressed
        ),
        100
    )


# =========================================================
# SCORE RANGE HELPER
# =========================================================

def critical_score_band(
    score
):

    if score < 70:

        return None

    if score <= 79:

        return "70-79"

    if score <= 89:

        return "80-89"

    if score <= 99:

        return "90-99"

    return "100"


# =========================================================
# AUDIT
# =========================================================

def run_audit():

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
                severity,
                severity_score,
                severity_reason,
                severity_rules_version

            FROM articles

            WHERE
                severity_status = 'success'

            AND
                severity_score IS NOT NULL

            ORDER BY id
            """
        ).fetchall()

    finally:

        connection.close()


    if not rows:

        print(
            "No scored articles found."
        )

        return


    results = []


    for row in rows:

        raw_score = (
            reconstruct_raw_score(
                row[
                    "severity_reason"
                ],
                row[
                    "severity_score"
                ],
            )
        )


        new_score = (
            proposed_score(
                raw_score
            )
        )


        new_severity = (
            score_to_severity(
                new_score
            )
        )


        results.append({

            "id":
                row["id"],

            "title":
                row["title"],

            "old_score":
                row[
                    "severity_score"
                ],

            "old_severity":
                row[
                    "severity"
                ],

            "raw_score":
                raw_score,

            "new_score":
                new_score,

            "new_severity":
                new_severity,

            "rules_version":
                row[
                    "severity_rules_version"
                ],
        })


    # =====================================================
    # GENERAL COUNTS
    # =====================================================

    total = len(
        results
    )


    old_distribution = Counter(

        item[
            "old_severity"
        ]

        for item in results
    )


    new_distribution = Counter(

        item[
            "new_severity"
        ]

        for item in results
    )


    stored_100 = [

        item
        for item in results
        if item[
            "old_score"
        ] == 100
    ]


    critical_100 = [

        item
        for item in stored_100
        if item[
            "old_severity"
        ] == "Critical"
    ]


    raw_over_100 = [

        item
        for item in results
        if item[
            "raw_score"
        ] > 100
    ]


    changed_level = [

        item
        for item in results

        if item[
            "old_severity"
        ]
        != item[
            "new_severity"
        ]
    ]


    # =====================================================
    # CURRENT CRITICAL SCORE BANDS
    # =====================================================

    old_critical_bands = Counter()

    new_critical_bands = Counter()


    for item in results:

        old_band = (
            critical_score_band(
                item[
                    "old_score"
                ]
            )
        )

        if old_band:

            old_critical_bands[
                old_band
            ] += 1


        new_band = (
            critical_score_band(
                item[
                    "new_score"
                ]
            )
        )

        if new_band:

            new_critical_bands[
                new_band
            ] += 1


    # =====================================================
    # OUTPUT
    # =====================================================

    print()
    print(
        "=" * 72
    )

    print(
        "CYBERHEAD SEVERITY CALIBRATION AUDIT"
    )

    print(
        "=" * 72
    )


    print()
    print(
        "CURRENT SYSTEM"
    )

    print(
        "-" * 72
    )

    print(
        f"Total scored articles: "
        f"{total}"
    )

    print(
        f"Articles stored as 100/100: "
        f"{len(stored_100)}"
    )

    print(
        f"Critical articles stored as 100/100: "
        f"{len(critical_100)}"
    )

    print(
        f"Articles whose reconstructed raw "
        f"score exceeded 100: "
        f"{len(raw_over_100)}"
    )

    print(
        f"Highest reconstructed raw score: "
        f"{max(item['raw_score'] for item in results)}"
    )


    print()
    print(
        "CURRENT SEVERITY DISTRIBUTION"
    )

    print(
        "-" * 72
    )

    for severity in [
        "Critical",
        "High",
        "Medium",
        "Low",
    ]:

        print(
            f"{severity:8s}: "
            f"{old_distribution[severity]}"
        )


    print()
    print(
        "CURRENT CRITICAL SCORE DISTRIBUTION"
    )

    print(
        "-" * 72
    )

    for band in [
        "70-79",
        "80-89",
        "90-99",
        "100",
    ]:

        print(
            f"{band:6s}: "
            f"{old_critical_bands[band]}"
        )


    # =====================================================
    # PROPOSED SYSTEM
    # =====================================================

    print()
    print(
        "=" * 72
    )

    print(
        "SIMULATED CALIBRATED SYSTEM"
    )

    print(
        "=" * 72
    )


    print()
    print(
        "PROPOSED SEVERITY DISTRIBUTION"
    )

    print(
        "-" * 72
    )

    for severity in [
        "Critical",
        "High",
        "Medium",
        "Low",
    ]:

        print(
            f"{severity:8s}: "
            f"{new_distribution[severity]}"
        )


    print()
    print(
        "PROPOSED CRITICAL SCORE DISTRIBUTION"
    )

    print(
        "-" * 72
    )

    for band in [
        "70-79",
        "80-89",
        "90-99",
        "100",
    ]:

        print(
            f"{band:6s}: "
            f"{new_critical_bands[band]}"
        )


    print()
    print(
        f"Articles changing severity level: "
        f"{len(changed_level)}"
    )


    # =====================================================
    # TOP RAW SCORES
    # =====================================================

    print()
    print(
        "=" * 72
    )

    print(
        "TOP 20 HIGHEST RAW SCORES"
    )

    print(
        "=" * 72
    )


    ranked = sorted(

        results,

        key=lambda item:
            item[
                "raw_score"
            ],

        reverse=True,
    )


    for item in ranked[:20]:

        print()

        print(
            f"Article {item['id']}"
        )

        print(
            item[
                "title"
            ]
        )

        print(
            f"Stored: "
            f"{item['old_score']}/100 "
            f"({item['old_severity']})"
        )

        print(
            f"Raw total: "
            f"{item['raw_score']}"
        )

        print(
            f"Proposed: "
            f"{item['new_score']}/100 "
            f"({item['new_severity']})"
        )


    # =====================================================
    # LEVEL CHANGES
    # =====================================================

    if changed_level:

        print()
        print(
            "=" * 72
        )

        print(
            "ARTICLES THAT WOULD CHANGE LEVEL"
        )

        print(
            "=" * 72
        )


        for item in changed_level[:30]:

            print()

            print(
                f"Article {item['id']}: "
                f"{item['old_severity']} "
                f"{item['old_score']}"
                f" -> "
                f"{item['new_severity']} "
                f"{item['new_score']}"
            )

            print(
                item[
                    "title"
                ]
            )


    print()
    print(
        "=" * 72
    )

    print(
        "AUDIT COMPLETE - DATABASE WAS NOT MODIFIED"
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":

    run_audit()