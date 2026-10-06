import argparse
import json
import math
import re

from datetime import datetime, timezone

from app.database import (
    initialise_database,
    get_articles_for_severity,
    get_article_severity_context,
    save_severity_result,
    save_severity_failure,
    save_severity_exclusion,
)

from app.content_filter import (
    check_article_suitability,
)


# =========================================================
# RULE VERSION
# =========================================================

RULES_VERSION = "severity_rules_v3_calibrated"


# =========================================================
# SEVERITY BANDS
# =========================================================

def score_to_severity(score):
    """
    Convert CYBERHEAD's final 0-100 severity score
    into a severity level.
    """

    if score >= 70:
        return "Critical"

    if score >= 40:
        return "High"

    if score >= 20:
        return "Medium"

    return "Low"


# =========================================================
# SCORE CALIBRATION
# =========================================================

def calibrate_score(raw_score):
    """
    Convert the accumulated evidence score into
    CYBERHEAD's final 0-100 severity score.

    Scores up to 70 are left unchanged.

    Scores above 70 are progressively compressed.
    This prevents many serious threats from all
    becoming exactly 100/100.

    Examples approximately:

        raw 75  -> 73
        raw 100 -> 84
        raw 120 -> 89
        raw 150 -> 94
        raw 200 -> 98

    The Critical threshold remains 70.
    """

    raw_score = max(
        int(
            round(
                raw_score
            )
        ),
        0
    )

    # Do not change Low / Medium / High scoring.
    # Also preserve the start of the Critical range.
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
        int(
            round(
                compressed
            )
        ),
        100
    )


# =========================================================
# CVSS
# =========================================================

def get_max_cvss(cve_rows):
    """
    Find the highest CVSS score across
    every CVE linked to the article.
    """

    scores = []

    for row in cve_rows:

        record_json = row.get(
            "record_json"
        )

        if not record_json:
            continue

        try:

            record = json.loads(
                record_json
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        metrics = record.get(
            "metrics",
            {}
        )

        for (
            metric_name,
            assessments
        ) in metrics.items():

            if not metric_name.startswith(
                "cvssMetric"
            ):
                continue

            for assessment in assessments:

                cvss_data = (
                    assessment.get(
                        "cvssData",
                        {}
                    )
                )

                value = (
                    cvss_data.get(
                        "baseScore"
                    )
                )

                if value is None:
                    continue

                try:

                    scores.append(
                        float(
                            value
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

    if not scores:
        return None

    return max(
        scores
    )


# =========================================================
# CISA KEV
# =========================================================

def has_cisa_kev(cve_rows):
    """
    Return True when at least one article CVE
    appears in the CISA Known Exploited
    Vulnerabilities catalogue.
    """

    return any(
        row.get(
            "kev_cve_id"
        )
        for row in cve_rows
    )


def has_known_ransomware_use(
    cve_rows
):
    """
    Return True when CISA indicates that at least
    one linked CVE is known to be used in
    ransomware campaigns.
    """

    for row in cve_rows:

        value = (
            row.get(
                "known_ransomware_campaign_use"
            )
            or ""
        )

        value = (
            str(
                value
            )
            .strip()
            .lower()
        )

        if value == "known":
            return True

    return False


# =========================================================
# RECENCY
# =========================================================

def calculate_recency_points(
    published_at
):
    """
    Give a small score contribution to recent news.

    <= 1 day  -> +5
    <= 3 days -> +3
    <= 7 days -> +1
    older     -> +0
    """

    if not published_at:

        return 0, None

    try:

        published = (
            datetime.fromisoformat(
                str(
                    published_at
                ).replace(
                    "Z",
                    "+00:00"
                )
            )
        )

        if published.tzinfo is None:

            published = (
                published.replace(
                    tzinfo=timezone.utc
                )
            )

        now = datetime.now(
            timezone.utc
        )

        age_days = (
            (
                now
                - published
            )
            .total_seconds()
            / 86400
        )

        age_days = max(
            age_days,
            0
        )

    except (
        ValueError,
        TypeError,
    ):

        return 0, None

    if age_days <= 1:

        return 5, age_days

    if age_days <= 3:

        return 3, age_days

    if age_days <= 7:

        return 1, age_days

    return 0, age_days


# =========================================================
# DATA THEFT
# =========================================================

DATA_THEFT_PATTERNS = [

    r"\bstolen data\b",

    r"\bdata theft\b",

    r"\bdata was stolen\b",

    r"\bstole data\b",

    r"\bdata exfiltration\b",

    r"\bexfiltrated data\b",

    r"\bstolen customer data\b",

    r"\bstolen user data\b",
]


def detects_data_theft(
    title,
    text
):
    """
    Detect explicit evidence that data was stolen
    or exfiltrated.
    """

    combined = (
        f"{title or ''} "
        f"{text or ''}"
    )

    for pattern in (
        DATA_THEFT_PATTERNS
    ):

        if re.search(
            pattern,
            combined,
            re.IGNORECASE
        ):

            return True

    return False


# =========================================================
# LARGE-SCALE IMPACT
# =========================================================

def parse_number(
    number_text,
    suffix=None
):
    """
    Convert values such as:

        12,000
        15 thousand
        2 million

    into integers.
    """

    try:

        number = float(
            number_text.replace(
                ",",
                ""
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    suffix = (
        suffix
        or ""
    ).lower()

    if suffix in (
        "k",
        "thousand",
    ):

        number *= 1_000

    elif suffix in (
        "m",
        "million",
    ):

        number *= 1_000_000

    return int(
        number
    )


def detect_affected_count(
    title,
    text
):
    """
    Detect phrases such as:

        12,000 accounts compromised
        5,000 users affected
        2 million records exposed
        affected 20,000 customers
    """

    combined = (
        f"{title or ''} "
        f"{text or ''}"
    )

    impact_nouns = (

        r"accounts?|"

        r"users?|"

        r"customers?|"

        r"people|"

        r"victims?|"

        r"devices?|"

        r"systems?|"

        r"organizations?|"

        r"organisations?|"

        r"records?"
    )

    impact_words = (

        r"compromised|"

        r"affected|"

        r"breached|"

        r"exposed|"

        r"stolen|"

        r"impacted|"

        r"infected"
    )

    number_pattern = (

        r"(?P<number>"
        r"\d[\d,]*(?:\.\d+)?)"

        r"\s*"

        r"(?P<suffix>"
        r"million|"
        r"thousand|"
        r"m|"
        r"k"
        r")?"
    )

    patterns = [

        (
            number_pattern

            + r"(?:\s+[A-Za-z0-9_-]+){0,3}"

            + r"\s+(?:"

            + impact_nouns

            + r")"

            + r".{0,60}?"

            + r"\b(?:"

            + impact_words

            + r")\b"
        ),

        (
            r"\b(?:"

            + impact_words

            + r")\b"

            + r".{0,40}?"

            + number_pattern

            + r"(?:\s+[A-Za-z0-9_-]+){0,3}"

            + r"\s+(?:"

            + impact_nouns

            + r")"
        ),
    ]

    detected_counts = []

    for pattern in patterns:

        matches = re.finditer(
            pattern,
            combined,
            re.IGNORECASE
        )

        for match in matches:

            count = parse_number(
                match.group(
                    "number"
                ),
                match.group(
                    "suffix"
                ),
            )

            if count is not None:

                detected_counts.append(
                    count
                )

    if not detected_counts:

        return None

    return max(
        detected_counts
    )


def affected_count_points(
    count
):
    """
    Convert the number of affected entities into
    severity points.
    """

    if count is None:

        return 0

    if count >= 100_000:

        return 35

    if count >= 10_000:

        return 30

    if count >= 1_000:

        return 20

    if count >= 100:

        return 10

    return 5


# =========================================================
# CRITICAL INFRASTRUCTURE
# =========================================================

CRITICAL_INFRASTRUCTURE_PATTERNS = [

    r"\bcritical infrastructure\b",

    r"\bindustrial control systems?\b",

    r"\boperational technology\b",

    r"\bpower grid\b",
]


def detects_critical_infrastructure(
    title,
    text
):
    """
    Detect explicit references to critical
    infrastructure or operational technology.
    """

    combined = (
        f"{title or ''} "
        f"{text or ''}"
    )

    for pattern in (
        CRITICAL_INFRASTRUCTURE_PATTERNS
    ):

        if re.search(
            pattern,
            combined,
            re.IGNORECASE
        ):

            return True

    return False


# =========================================================
# MAIN SEVERITY CALCULATION
# =========================================================

def calculate_severity(
    article
):
    """
    Calculate CYBERHEAD threat severity.

    Step 1:
        Evidence indicators accumulate a raw score.

    Step 2:
        The raw score is calibrated into the final
        CYBERHEAD 0-100 Severity Score.

    Step 3:
        The final score is converted to:
        Low / Medium / High / Critical.
    """

    score = 0

    reasons = []


    category = (
        article.get(
            "category"
        )
        or ""
    ).strip()


    tags = {

        str(
            tag
        ).strip()

        for tag in article.get(
            "tags",
            []
        )

        if str(
            tag
        ).strip()
    }


    cves = article.get(
        "cves",
        []
    )


    title = (
        article.get(
            "title"
        )
        or ""
    )


    text = (
        article.get(
            "full_content"
        )

        or article.get(
            "content"
        )

        or ""
    )


    # =====================================================
    # 1. CVSS
    # =====================================================

    max_cvss = (
        get_max_cvss(
            cves
        )
    )


    if max_cvss is not None:

        if max_cvss >= 9.0:

            score += 35

            reasons.append(
                f"Critical CVSS score "
                f"{max_cvss:.1f}: +35"
            )


        elif max_cvss >= 7.0:

            score += 25

            reasons.append(
                f"High CVSS score "
                f"{max_cvss:.1f}: +25"
            )


        elif max_cvss >= 4.0:

            score += 15

            reasons.append(
                f"Medium CVSS score "
                f"{max_cvss:.1f}: +15"
            )


        elif max_cvss > 0:

            score += 5

            reasons.append(
                f"Low CVSS score "
                f"{max_cvss:.1f}: +5"
            )


    # =====================================================
    # 2. CISA KEV / ACTIVE EXPLOITATION
    # =====================================================

    kev = (
        has_cisa_kev(
            cves
        )
    )


    if kev:

        score += 40

        reasons.append(
            "CVE listed in CISA Known Exploited "
            "Vulnerabilities catalog: +40"
        )


    # =====================================================
    # 3. RANSOMWARE USE CONFIRMED BY CISA
    # =====================================================

    ransomware_use = (
        has_known_ransomware_use(
            cves
        )
    )


    if ransomware_use:

        score += 20

        reasons.append(
            "CISA reports known ransomware "
            "campaign use: +20"
        )


    # =====================================================
    # 4. ZERO-DAY
    # =====================================================

    if "Zero-Day" in tags:

        score += 20

        reasons.append(
            "Zero-day vulnerability detected: +20"
        )


    # =====================================================
    # 5. CATEGORY
    # =====================================================

    if category == "Ransomware":

        score += 25

        reasons.append(
            "Ransomware incident: +25"
        )


    elif category == "Data breaches":

        score += 20

        reasons.append(
            "Data breach incident: +20"
        )


    elif category == "DDoS":

        score += 15

        reasons.append(
            "DDoS incident: +15"
        )


    elif category == "Other malware":

        score += 10

        reasons.append(
            "Malware-related incident: +10"
        )


    elif category == "Phishing":

        score += 10

        reasons.append(
            "Phishing incident: +10"
        )


    # Vulnerabilities and Other cybersecurity news
    # do not receive automatic category points.


    # =====================================================
    # 6. TECHNICAL TAGS
    # =====================================================

    if "Remote Code Execution" in tags:

        score += 20

        reasons.append(
            "Remote Code Execution detected: +20"
        )


    if "Privilege Escalation" in tags:

        score += 12

        reasons.append(
            "Privilege Escalation detected: +12"
        )


    if "Supply Chain" in tags:

        score += 12

        reasons.append(
            "Supply-chain attack detected: +12"
        )


    if "Credential Theft" in tags:

        score += 15

        reasons.append(
            "Credential theft detected: +15"
        )


    if "SQL Injection" in tags:

        score += 10

        reasons.append(
            "SQL Injection detected: +10"
        )


    if (
        "Social Engineering" in tags

        and

        category != "Phishing"
    ):

        score += 8

        reasons.append(
            "Social engineering detected: +8"
        )


    # =====================================================
    # 7. DATA THEFT
    # =====================================================

    if detects_data_theft(
        title,
        text
    ):

        score += 15

        reasons.append(
            "Explicit data-theft evidence "
            "found in article: +15"
        )


    # =====================================================
    # 8. NUMBER AFFECTED
    # =====================================================

    affected_count = (
        detect_affected_count(
            title,
            text
        )
    )


    if affected_count is not None:

        impact_points = (
            affected_count_points(
                affected_count
            )
        )

        score += (
            impact_points
        )

        reasons.append(
            f"Large-scale impact detected "
            f"({affected_count:,} affected): "
            f"+{impact_points}"
        )


    # =====================================================
    # 9. CRITICAL INFRASTRUCTURE
    # =====================================================

    critical_infrastructure = (
        detects_critical_infrastructure(
            title,
            text
        )
    )


    if critical_infrastructure:

        score += 15

        reasons.append(
            "Critical-infrastructure impact "
            "detected: +15"
        )


    # =====================================================
    # 10. RECENCY
    # =====================================================

    (
        recency_points,
        age_days
    ) = calculate_recency_points(
        article.get(
            "published_at"
        )
    )


    if recency_points:

        score += (
            recency_points
        )

        reasons.append(
            f"Recent publication "
            f"({age_days:.1f} days old): "
            f"+{recency_points}"
        )


    # =====================================================
    # RAW EVIDENCE SCORE
    # =====================================================

    raw_score = int(
        round(
            score
        )
    )


    # =====================================================
    # FINAL CALIBRATED SCORE
    # =====================================================

    score = (
        calibrate_score(
            raw_score
        )
    )


    severity = (
        score_to_severity(
            score
        )
    )


    # Explain when calibration changed the numeric result.
    if score != raw_score:

        reasons.append(
            f"CYBERHEAD score calibration: "
            f"raw evidence total "
            f"{raw_score} -> "
            f"{score}/100"
        )


    # If no evidence at all was detected.
    if not reasons:

        reasons.append(
            "No strong severity indicators "
            "were detected: +0"
        )


    # =====================================================
    # RESULT
    # =====================================================

    return {

        "severity":
            severity,

        "score":
            score,

        "raw_score":
            raw_score,

        "reasons":
            reasons,

        "max_cvss":
            max_cvss,

        "active_exploitation":
            kev,

        "ransomware_use":
            ransomware_use,

        "affected_count":
            affected_count,

        "critical_infrastructure":
            critical_infrastructure,

        "tags":
            sorted(
                tags
            ),
    }


# =========================================================
# PROCESS ARTICLES
# =========================================================

def process_articles(
    limit=20,
    retry_failed=False
):
    """
    Process articles waiting for severity analysis.
    """

    initialise_database()


    articles = (
        get_articles_for_severity(
            limit=limit,
            retry_failed=retry_failed
        )
    )


    if not articles:

        print(
            "No articles are waiting "
            "for severity analysis."
        )

        return


    success = 0

    excluded = 0

    failed = 0


    for (
        position,
        queued_article
    ) in enumerate(
        articles,
        start=1
    ):

        article_id = (
            queued_article[
                "id"
            ]
        )


        try:

            article = (
                get_article_severity_context(
                    article_id
                )
            )


            if article is None:

                raise ValueError(
                    f"Article {article_id} "
                    f"could not be loaded."
                )


            # =================================================
            # CHECK ARTICLE SUITABILITY
            # =================================================

            text = (

                article.get(
                    "full_content"
                )

                or article.get(
                    "content"
                )

                or ""
            )


            (
                suitable,
                exclusion_reason
            ) = check_article_suitability(

                article.get(
                    "title"
                ),

                text
            )


            if not suitable:

                save_severity_exclusion(

                    article_id=
                        article_id,

                    reason=
                        exclusion_reason,

                    rules_version=
                        RULES_VERSION,
                )


                print(
                    f"[{position}/{len(articles)}] "
                    f"Article {article_id}: "
                    f"EXCLUDED "
                    f"({exclusion_reason})"
                )


                excluded += 1

                continue


            # =================================================
            # CALCULATE SEVERITY
            # =================================================

            result = (
                calculate_severity(
                    article
                )
            )


            save_severity_result(

                article_id=
                    article_id,

                severity=
                    result[
                        "severity"
                    ],

                score=
                    result[
                        "score"
                    ],

                reasons=
                    result[
                        "reasons"
                    ],

                rules_version=
                    RULES_VERSION,
            )


            print(
                f"[{position}/{len(articles)}] "
                f"Article {article_id}: "
                f"{result['severity']} "
                f"({result['score']}/100)"
            )


            # Show the raw score too when calibration
            # actually changed the result.

            if (
                result[
                    "raw_score"
                ]
                != result[
                    "score"
                ]
            ):

                print(
                    f"    Raw evidence score: "
                    f"{result['raw_score']}"
                )

                print(
                    f"    Calibrated score: "
                    f"{result['score']}/100"
                )


            for reason in (
                result[
                    "reasons"
                ]
            ):

                print(
                    f"    - {reason}"
                )


            success += 1


        except Exception as error:

            save_severity_failure(
                article_id,
                error
            )


            print(
                f"ERROR: article "
                f"{article_id}; "
                f"{error}"
            )


            failed += 1


    # =====================================================
    # PROCESSING SUMMARY
    # =====================================================

    print()

    print(
        "--- SEVERITY SUMMARY ---"
    )


    print(
        f"Scored successfully: "
        f"{success}"
    )


    print(
        f"Excluded: "
        f"{excluded}"
    )


    print(
        f"Failed: "
        f"{failed}"
    )


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    parser = (
        argparse.ArgumentParser(
            description=(
                "Run CYBERHEAD "
                "severity analysis."
            )
        )
    )


    parser.add_argument(

        "--limit",

        type=int,

        default=20,

        help=(
            "Maximum number of articles "
            "to process."
        ),
    )


    parser.add_argument(

        "--retry-failed",

        action="store_true",

        help=(
            "Retry articles whose previous "
            "severity analysis failed."
        ),
    )


    args = (
        parser.parse_args()
    )


    if args.limit < 1:

        parser.error(
            "--limit must be at least 1."
        )


    process_articles(

        limit=
            args.limit,

        retry_failed=
            args.retry_failed,
    )