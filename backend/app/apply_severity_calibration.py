import re

from contextlib import closing

from datetime import (
    datetime,
    timezone,
)

from app.database import (
    get_connection,
)

from app.severity_engine import (
    RULES_VERSION,
    calibrate_score,
    score_to_severity,
)


# =========================================================
# POINT EXTRACTION
# =========================================================

POINT_PATTERN = re.compile(
    r"\+(\d+)\s*$"
)


# =========================================================
# RECONSTRUCT RAW SCORE
# =========================================================

def reconstruct_raw_score(
    reason_text,
    stored_score,
):
    """
    Reconstruct the original evidence total
    from the stored severity reasons.

    Example:

        Critical CVSS score 9.8: +35
        CISA KEV: +40
        RCE detected: +20

    Raw score:
        95
    """

    if not reason_text:

        return stored_score


    points = []


    for line in (
        reason_text.splitlines()
    ):

        match = (
            POINT_PATTERN.search(
                line.strip()
            )
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
# APPLY CALIBRATION
# =========================================================

def apply_calibration():
    """
    Apply the new calibrated severity score
    to articles that were already scored.

    This does NOT rerun the entire severity engine.

    This is important because rerunning the engine
    could change recency points simply because time
    has passed.
    """

    with closing(
        get_connection()
    ) as connection:

        rows = (
            connection.execute(
                """
                SELECT

                    id,

                    title,

                    severity,

                    severity_score,

                    severity_reason,

                    summary_status

                FROM articles

                WHERE
                    severity_status = 'success'

                AND
                    severity_score IS NOT NULL

                ORDER BY
                    id
                """
            ).fetchall()
        )


        if not rows:

            print(
                "No scored articles found."
            )

            return


        updates = []

        level_changes = []


        # =================================================
        # CALCULATE RESULTS FIRST
        # =================================================
        #
        # Nothing has been modified yet.
        # =================================================

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
                calibrate_score(
                    raw_score
                )
            )


            new_severity = (
                score_to_severity(
                    new_score
                )
            )


            if (
                new_severity
                != row[
                    "severity"
                ]
            ):

                level_changes.append({

                    "id":
                        row[
                            "id"
                        ],

                    "title":
                        row[
                            "title"
                        ],

                    "old_severity":
                        row[
                            "severity"
                        ],

                    "new_severity":
                        new_severity,

                    "old_score":
                        row[
                            "severity_score"
                        ],

                    "new_score":
                        new_score,
                })


            updates.append({

                "id":
                    row[
                        "id"
                    ],

                "old_score":
                    row[
                        "severity_score"
                    ],

                "new_score":
                    new_score,

                "new_severity":
                    new_severity,

                "summary_status":
                    row[
                        "summary_status"
                    ],
            })


        # =================================================
        # SAFETY CHECK
        # =================================================
        #
        # Our audit showed zero severity-level changes.
        #
        # If anything unexpectedly changes level now,
        # the database will NOT be modified.
        # =================================================

        if level_changes:

            print()

            print(
                "=" * 72
            )

            print(
                "CALIBRATION ABORTED"
            )

            print(
                "=" * 72
            )

            print()

            print(
                "One or more articles would "
                "change severity level."
            )

            print()

            for item in (
                level_changes
            ):

                print(
                    f"Article "
                    f"{item['id']}: "
                    f"{item['old_severity']} "
                    f"{item['old_score']} "
                    f"-> "
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
                "DATABASE WAS NOT MODIFIED."
            )

            return


        # =================================================
        # APPLY DATABASE UPDATE
        # =================================================

        now = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )


        changed_scores = 0

        unchanged_scores = 0

        summaries_reset = 0


        try:

            connection.execute(
                "BEGIN"
            )


            for item in updates:

                if (
                    item[
                        "new_score"
                    ]
                    != item[
                        "old_score"
                    ]
                ):

                    changed_scores += 1

                else:

                    unchanged_scores += 1


                # -----------------------------------------
                # Update severity score
                # -----------------------------------------

                connection.execute(
                    """
                    UPDATE articles

                    SET
                        severity = ?,

                        severity_score = ?,

                        severity_rules_version = ?,

                        severity_processed_at = ?,

                        severity_error = NULL

                    WHERE
                        id = ?
                    """,
                    (
                        item[
                            "new_severity"
                        ],

                        item[
                            "new_score"
                        ],

                        RULES_VERSION,

                        now,

                        item[
                            "id"
                        ],
                    )
                )


                # -----------------------------------------
                # Reset successful summaries
                # -----------------------------------------
                #
                # Why it matters contains the numeric
                # severity score.
                #
                # Example:
                #
                # "CYBERHEAD rates this development
                # as Critical severity (100/100)."
                #
                # That text must be regenerated.
                # -----------------------------------------

                if (
                    item[
                        "summary_status"
                    ]
                    == "success"
                ):

                    connection.execute(
                        """
                        UPDATE articles

                        SET
                            summary_status = 'pending',

                            summary_processed_at = NULL,

                            summary_error = NULL

                        WHERE
                            id = ?
                        """,
                        (
                            item[
                                "id"
                            ],
                        )
                    )


                    summaries_reset += 1


            connection.commit()


        except Exception:

            connection.rollback()

            raise


    # =====================================================
    # RESULT
    # =====================================================

    print()

    print(
        "=" * 72
    )

    print(
        "CYBERHEAD SEVERITY CALIBRATION APPLIED"
    )

    print(
        "=" * 72
    )

    print()

    print(
        f"Articles processed: "
        f"{len(updates)}"
    )

    print(
        f"Scores changed: "
        f"{changed_scores}"
    )

    print(
        f"Scores unchanged: "
        f"{unchanged_scores}"
    )

    print(
        "Severity levels changed: 0"
    )

    print(
        f"Summaries queued for refresh: "
        f"{summaries_reset}"
    )

    print(
        f"Rules version: "
        f"{RULES_VERSION}"
    )

    print()

    print(
        "Existing severity evidence "
        "was preserved."
    )

    print(
        "Calibration complete."
    )


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    apply_calibration()