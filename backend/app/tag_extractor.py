import argparse
import json
import re

from app.content_filter import check_article_suitability

from app.database import (
    initialise_database,
    get_articles_for_tagging,
    get_nvd_records_for_article,
    save_article_tags,
    save_tagging_failure,
)


MIN_SCORE = 4


TAG_RULES = {

    "Man-in-the-Middle": {
        "patterns": [
            r"\bman[- ]in[- ]the[- ]middle\b",
            r"\bmitm attack\b",
        ],
        "cwes": set(),
    },

    "SQL Injection": {
        "patterns": [
            r"\bsql injection\b",
            r"\bsqli\b",
        ],
        "cwes": {
            "CWE-89",
        },
    },

    "Insider Threat": {
        "patterns": [
            r"\binsider threat\b",
            r"\bmalicious insider\b",
            r"\brogue employee\b",
            r"\bdisgruntled employee\b",
        ],
        "cwes": set(),
    },

    "Zero-Day": {
        "patterns": [
            r"\bzero[- ]day\b",
            r"\b0[- ]day\b",
        ],
        "cwes": set(),
    },

    "Password Attack": {
        "patterns": [
            r"\bpassword spraying\b",
            r"\bpassword spray\b",
            r"\bpassword guessing\b",
            r"\bcredential stuffing\b",
            r"\bdictionary attack\b",
        ],
        "cwes": set(),
    },

    "Credential Theft": {
        "patterns": [
            r"\bcredential theft\b",
            r"\bstolen credentials\b",
            r"\bcredential harvesting\b",
            r"\bsteal(?:ing|s)? credentials\b",
        ],
        "cwes": set(),
    },

    "Brute Force": {
        "patterns": [
            r"\bbrute[- ]force\b",
            r"\bpassword spraying\b",
            r"\bpassword spray\b",
        ],
        "cwes": set(),
    },

    "Supply Chain": {
        "patterns": [
            r"\bsupply[- ]chain\b",
            r"\bsoftware supply chain\b",
            r"\bmalicious npm package\b",
            r"\bmalicious pypi package\b",
        ],
        "cwes": set(),
    },

    "Remote Code Execution": {
        "patterns": [
            r"\bremote code execution\b",
            r"\brce vulnerability\b",
            r"\brce flaw\b",
        ],
        "cwes": set(),
    },

    "Privilege Escalation": {
        "patterns": [
            r"\bprivilege escalation\b",
            r"\belevation of privilege\b",
        ],
        "cwes": {
            "CWE-269",
        },
    },

    "Social Engineering": {
        "patterns": [
            r"\bsocial engineering\b",
            r"\bphishing\b",
            r"\bvishing\b",
            r"\bsmishing\b",
        ],
        "cwes": set(),
    },
}


def find_match(text, patterns):

    if not text:
        return None

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(0)

    return None


def extract_nvd_information(rows):

    descriptions = []
    cwes = set()

    for row in rows:

        if not row["record_json"]:
            continue

        record = json.loads(
            row["record_json"]
        )

        for description in record.get(
            "descriptions",
            []
        ):

            if description.get("lang") == "en":

                descriptions.append(
                    description.get(
                        "value",
                        ""
                    )
                )

        for weakness in record.get(
            "weaknesses",
            []
        ):

            for description in weakness.get(
                "description",
                []
            ):

                value = description.get(
                    "value"
                )

                if (
                    value
                    and value.startswith("CWE-")
                ):
                    cwes.add(value)

    return (
        " ".join(descriptions),
        cwes
    )


def detect_tags(article, nvd_rows):

    title = article["title"] or ""

    full_text = (
        article["full_content"]
        or article["content"]
        or ""
    )

    # First part of the article is stronger evidence
    # than a random mention later in the article.
    lead_text = full_text[:1500]

    body_text = full_text[1500:]

    nvd_description, cwes = (
        extract_nvd_information(
            nvd_rows
        )
    )

    results = []

    for tag, rule in TAG_RULES.items():

        score = 0
        evidence = []

        # TITLE
        # Strong evidence
        match = find_match(
            title,
            rule["patterns"]
        )

        if match:

            score += 5

            evidence.append(
                f"Title: {match}"
            )

        # ARTICLE OPENING
        # Strong evidence
        match = find_match(
            lead_text,
            rule["patterns"]
        )

        if match:

            score += 4

            evidence.append(
                f"Article opening: {match}"
            )

        # ARTICLE BODY
        # Weak evidence
        match = find_match(
            body_text,
            rule["patterns"]
        )

        if match:

            score += 1

            evidence.append(
                f"Article body: {match}"
            )

        # NVD DESCRIPTION
        # Strong technical evidence
        match = find_match(
            nvd_description,
            rule["patterns"]
        )

        if match:

            score += 5

            evidence.append(
                f"NVD description: {match}"
            )

        # NVD CWE
        # Very strong evidence
        matching_cwes = (
            cwes
            & rule["cwes"]
        )

        if matching_cwes:

            score += 6

            evidence.append(
                "NVD CWE: "
                + ", ".join(
                    sorted(matching_cwes)
                )
            )

        # CATEGORY CONTEXT
        if (
            tag == "Social Engineering"
            and article["category"] == "Phishing"
        ):

            score += 5

            evidence.append(
                "ML category: Phishing"
            )

        # FINAL DECISION
        if score >= MIN_SCORE:

            results.append({
                "tag": tag,
                "score": score,
                "evidence": evidence,
            })

    return results


def process_articles(
    limit=20,
    retry_failed=False
):

    initialise_database()

    articles = get_articles_for_tagging(
        limit=limit,
        retry_failed=retry_failed
    )

    if not articles:

        print(
            "No articles are waiting "
            "for tag detection."
        )

        return

    processed = 0
    failed = 0

    for article in articles:

        article_id = article["id"]

        try:

            text = (
                article["full_content"]
                or article["content"]
                or ""
            )

            is_suitable, reason = (
                check_article_suitability(
                    article["title"],
                    text
                )
            )

            if not is_suitable:

                save_article_tags(
                    article_id,
                    []
                )

                print(
                    f"SKIPPED: article {article_id}; "
                    f"{reason}"
                )

                processed += 1
                continue

            nvd_rows = (
                get_nvd_records_for_article(
                    article_id
                )
            )

            tag_results = detect_tags(
                article,
                nvd_rows
            )

            save_article_tags(
                article_id,
                tag_results
            )

            if tag_results:

                display = ", ".join(
                    f"{result['tag']} "
                    f"(score={result['score']})"
                    for result in tag_results
                )

            else:

                display = "No relevant tags"

            print(
                f"SUCCESS: article {article_id}; "
                f"{display}"
            )

            processed += 1

        except Exception as error:

            save_tagging_failure(
                article_id,
                error
            )

            print(
                f"ERROR: article {article_id}; "
                f"{error}"
            )

            failed += 1

    print(
        "\n--- TAG DETECTION SUMMARY ---"
    )

    print(
        f"Processed: {processed}"
    )

    print(
        f"Failed: {failed}"
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=20
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true"
    )

    args = parser.parse_args()

    process_articles(
        limit=args.limit,
        retry_failed=args.retry_failed
    )