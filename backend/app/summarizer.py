import argparse
import json
import re

import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.content_filter import check_article_suitability

from app.database import (
    initialise_database,
    get_articles_for_summarization,
    get_article_summary_context,
    save_summary_result,
    save_summary_failure,
    save_summary_exclusion,
)


SUMMARY_METHOD = "tfidf_sentence_rank_v2"


# =========================================================
# TEXT CLEANING
# =========================================================

BOILERPLATE_PATTERNS = [
    r"\bsubscribe to our newsletter\b",
    r"\bsign up for our newsletter\b",
    r"\bfollow us on\b",
    r"\badvertisement\b",
    r"\bsponsored content\b",
    r"\bclick here\b",
    r"\bread more\b",
]


SECURITY_KEYWORDS = {
    "vulnerability",
    "vulnerabilities",
    "exploit",
    "exploited",
    "attack",
    "attacker",
    "attackers",
    "malware",
    "ransomware",
    "phishing",
    "breach",
    "breached",
    "compromised",
    "zero-day",
    "zero day",
    "cve",
    "cvss",
    "remote code execution",
    "privilege escalation",
    "data theft",
    "credentials",
    "critical",
    "patch",
    "security flaw",
}


def clean_text(text):
    """
    Normalize whitespace and remove common
    website-navigation fragments.
    """

    text = text or ""

    # Remove website cross-link text such as:
    # [ Read: Another Article ]
    text = re.sub(
        r"\[\s*read\s*:.*?\]",
        " ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def is_boilerplate(sentence):
    """
    Detect obvious non-article content.
    """

    for pattern in BOILERPLATE_PATTERNS:

        if re.search(
            pattern,
            sentence,
            re.IGNORECASE
        ):
            return True

    return False


# =========================================================
# SENTENCE SPLITTING
# =========================================================

def split_sentences(text):
    """
    Split article text into useful sentences while
    protecting common abbreviations.
    """

    text = clean_text(text)

    if not text:
        return []

    protected = text

    abbreviations = {
        "vs.": "vs<PERIOD>",
        "Mr.": "Mr<PERIOD>",
        "Mrs.": "Mrs<PERIOD>",
        "Dr.": "Dr<PERIOD>",
        "Prof.": "Prof<PERIOD>",
        "e.g.": "e<PERIOD>g<PERIOD>",
        "i.e.": "i<PERIOD>e<PERIOD>",
        "U.S.": "U<PERIOD>S<PERIOD>",
        "U.K.": "U<PERIOD>K<PERIOD>",
    }

    for original, replacement in abbreviations.items():

        protected = re.sub(
            re.escape(original),
            replacement,
            protected,
            flags=re.IGNORECASE
        )

    marked_text = re.sub(
        r'([.!?]["”’]?)\s+(?=(?:["“‘])?[A-Z0-9])',
        r'\1<SENTENCE_SPLIT>',
        protected
    )

    raw_sentences = marked_text.split(
        "<SENTENCE_SPLIT>"
    )

    sentences = []

    for sentence in raw_sentences:

        sentence = sentence.replace(
            "<PERIOD>",
            "."
        )

        sentence = sentence.strip()

        word_count = len(
            sentence.split()
        )

        if word_count < 8:
            continue

        if word_count > 90:
            continue

        if is_boilerplate(
            sentence
        ):
            continue

        sentences.append(
            sentence
        )

    return sentences


# =========================================================
# CYBERSECURITY KEYWORD SCORE
# =========================================================

def security_keyword_score(sentence):
    """
    Give a small relevance bonus when a sentence
    contains cybersecurity terminology.
    """

    lowered = sentence.lower()

    matches = sum(
        1
        for keyword in SECURITY_KEYWORDS
        if keyword in lowered
    )

    return min(
        matches / 4,
        1.0
    )


# =========================================================
# NLP SUMMARY
# =========================================================

def generate_summary(
    title,
    text,
    max_sentences=3,
    max_words=140
):
    """
    Generate an extractive summary using TF-IDF.

    Sentence importance combines:
    - overall article relevance
    - similarity to the article title
    - sentence position
    - cybersecurity keyword relevance
    """

    text = clean_text(
        text
    )

    clean_title = clean_text(
        title
    )

    # Some extracted articles begin by repeating
    # the article title. Remove it before summarizing.
    if (
        clean_title
        and text.lower().startswith(
            clean_title.lower()
        )
    ):

        text = text[
            len(clean_title):
        ].lstrip(
            " :-–—"
        )

    sentences = split_sentences(
        text
    )

    if not sentences:

        raise ValueError(
            "No usable article sentences were found."
        )

    # Short articles do not require ranking.
    if len(sentences) <= max_sentences:

        return " ".join(
            sentences
        )

    documents = [
        clean_title
    ] + sentences

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=5000,
    )

    matrix = vectorizer.fit_transform(
        documents
    )

    title_vector = matrix[0]

    sentence_vectors = matrix[1:]

    # Represents the overall subject matter
    # of the article.
    article_centroid = np.asarray(
        sentence_vectors.mean(
            axis=0
        )
    )

    article_similarity = (
        cosine_similarity(
            sentence_vectors,
            article_centroid
        ).flatten()
    )

    title_similarity = (
        cosine_similarity(
            sentence_vectors,
            title_vector
        ).flatten()
    )

    scored_sentences = []

    total_sentences = len(
        sentences
    )

    for index, sentence in enumerate(
        sentences
    ):

        # News articles often introduce the most
        # important information near the beginning.
        position_score = (
            1
            - (
                index
                / max(
                    total_sentences - 1,
                    1
                )
            )
        )

        keyword_score = (
            security_keyword_score(
                sentence
            )
        )

        final_score = (
            article_similarity[index] * 0.55
            + title_similarity[index] * 0.25
            + position_score * 0.10
            + keyword_score * 0.10
        )

        scored_sentences.append({
            "index": index,
            "sentence": sentence,
            "score": final_score,
        })

    ranked = sorted(
        scored_sentences,
        key=lambda item: item["score"],
        reverse=True
    )

    selected = []

    selected_indexes = []

    current_words = 0

    for candidate in ranked:

        if len(selected) >= max_sentences:
            break

        candidate_index = (
            candidate["index"]
        )

        candidate_sentence = (
            candidate["sentence"]
        )

        candidate_words = len(
            candidate_sentence.split()
        )

        duplicate = False

        # Avoid selecting sentences that say
        # almost the same thing.
        for selected_index in selected_indexes:

            similarity = cosine_similarity(
                sentence_vectors[
                    candidate_index
                ],
                sentence_vectors[
                    selected_index
                ]
            )[0][0]

            if similarity >= 0.65:

                duplicate = True

                break

        if duplicate:
            continue

        if (
            selected
            and current_words
            + candidate_words
            > max_words
        ):
            continue

        selected.append(
            candidate
        )

        selected_indexes.append(
            candidate_index
        )

        current_words += (
            candidate_words
        )

    if not selected:

        selected = [
            ranked[0]
        ]

    # Return chosen sentences in their original
    # article order rather than score order.
    selected.sort(
        key=lambda item: item["index"]
    )

    return " ".join(
        item["sentence"]
        for item in selected
    )


# =========================================================
# NVD / CVE HELPERS
# =========================================================

def get_max_cvss(cve_rows):
    """
    Return the highest CVSS score found in
    the stored NVD records.
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

        except json.JSONDecodeError:
            continue

        metrics = record.get(
            "metrics",
            {}
        )

        for metric_name, assessments in metrics.items():

            if not metric_name.startswith(
                "cvssMetric"
            ):
                continue

            for assessment in assessments:

                cvss_data = assessment.get(
                    "cvssData",
                    {}
                )

                score = cvss_data.get(
                    "baseScore"
                )

                if isinstance(
                    score,
                    (int, float)
                ):

                    scores.append(
                        float(score)
                    )

    if not scores:
        return None

    return max(
        scores
    )


def get_kev_cves(cve_rows):
    """
    Return article CVEs appearing in CISA KEV.
    """

    return [
        row["cve_id"]
        for row in cve_rows
        if row.get(
            "kev_cve_id"
        )
    ]


def has_known_ransomware(cve_rows):
    """
    Check whether CISA reports known ransomware use.
    """

    for row in cve_rows:

        value = (
            row.get(
                "known_ransomware_campaign_use"
            )
            or ""
        )

        if (
            value.strip().lower()
            == "known"
        ):
            return True

    return False


# =========================================================
# WHY IT MATTERS
# =========================================================

def generate_why_it_matters(
    article,
    context
):
    """
    Explain the importance of an article using
    CYBERHEAD's structured evidence.
    """

    severity = article.get(
        "severity"
    )

    score = article.get(
        "severity_score"
    )

    cves = context[
        "cves"
    ]

    tags = [
        row["tag"]
        for row in context["tags"]
    ]

    max_cvss = get_max_cvss(
        cves
    )

    kev_cves = get_kev_cves(
        cves
    )

    ransomware = (
        has_known_ransomware(
            cves
        )
    )

    statements = []

    # -----------------------------------------------------
    # CYBERHEAD SEVERITY
    # -----------------------------------------------------

    if severity is not None:

        if score is not None:

            statements.append(
                f"CYBERHEAD rates this development "
                f"as {severity} severity "
                f"({score}/100)."
            )

        else:

            statements.append(
                f"CYBERHEAD rates this development "
                f"as {severity} severity."
            )

    # -----------------------------------------------------
    # STRUCTURED TECHNICAL EVIDENCE
    # -----------------------------------------------------

    evidence = []

    if max_cvss is not None:

        evidence.append(
            f"a maximum CVSS score of "
            f"{max_cvss:g}"
        )

    if kev_cves:

        cve_word = (
            "CVE"
            if len(kev_cves) == 1
            else "CVEs"
        )

        evidence.append(
            f"{len(kev_cves)} {cve_word} "
            f"listed in CISA's Known Exploited "
            f"Vulnerabilities catalog"
        )

    if ransomware:

        evidence.append(
            "known ransomware campaign use"
        )

    important_tags = [
        tag
        for tag in tags
        if tag in {
            "Zero-Day",
            "Remote Code Execution",
            "Privilege Escalation",
            "Credential Theft",
            "Supply Chain",
            "SQL Injection",
            "Password Attack",
            "Brute Force",
        }
    ]

    if important_tags:

        evidence.append(
            "threat indicators including "
            + ", ".join(
                important_tags[:3]
            )
        )

    if evidence:

        if len(evidence) == 1:

            evidence_text = (
                evidence[0]
            )

        else:

            evidence_text = (
                ", ".join(
                    evidence[:-1]
                )
                + " and "
                + evidence[-1]
            )

        statements.append(
            "Its importance is supported by "
            + evidence_text
            + "."
        )

    if not statements:

        statements.append(
            "The article is relevant to cybersecurity "
            "monitoring, but CYBERHEAD did not detect "
            "strong structured severity indicators."
        )

    return " ".join(
        statements
    )


# =========================================================
# RECOMMENDATION HELPERS
# =========================================================

def add_unique(
    recommendations,
    value
):
    """
    Add a recommendation only once.
    """

    if value not in recommendations:

        recommendations.append(
            value
        )


# =========================================================
# DEFENSIVE RECOMMENDATIONS
# =========================================================

def generate_recommendations(
    article,
    context
):
    """
    Produce conservative defensive recommendations
    using category, threat tags, CVEs and CISA evidence.
    """

    category = (
        article.get(
            "category"
        )
        or ""
    )

    tags = {
        row["tag"]
        for row in context["tags"]
    }

    cve_rows = context[
        "cves"
    ]

    severity_score = (
        article.get(
            "severity_score"
        )
        or 0
    )

    has_cves = bool(
        cve_rows
    )

    technical_vulnerability_tags = {
        "Zero-Day",
        "Remote Code Execution",
        "Privilege Escalation",
        "SQL Injection",
    }

    recommendations = []

    # =====================================================
    # CATEGORY-BASED GUIDANCE
    # =====================================================

    if category == "Vulnerabilities":

        # Only give direct remediation guidance when
        # actual technical evidence is present.
        if (
            has_cves
            or tags
            & technical_vulnerability_tags
        ):

            add_unique(
                recommendations,
                (
                    "Review vendor security advisories "
                    "and apply available patches or "
                    "firmware updates."
                )
            )

            add_unique(
                recommendations,
                (
                    "Identify affected systems and "
                    "reduce unnecessary internet exposure "
                    "until remediation is complete."
                )
            )

        else:

            add_unique(
                recommendations,
                (
                    "Review the development and assess "
                    "whether it affects technologies or "
                    "services used by the organisation."
                )
            )

    elif category == "Ransomware":

        add_unique(
            recommendations,
            (
                "Isolate suspected affected systems "
                "and activate the organisation's "
                "incident-response process."
            )
        )

        add_unique(
            recommendations,
            (
                "Verify that recent offline or "
                "immutable backups are available "
                "and recoverable."
            )
        )

    elif category == "Phishing":

        add_unique(
            recommendations,
            (
                "Block identified malicious domains, "
                "URLs or senders where appropriate."
            )
        )

        add_unique(
            recommendations,
            (
                "Use multi-factor authentication and "
                "warn users about the reported "
                "phishing technique."
            )
        )

    elif category == "Data breaches":

        add_unique(
            recommendations,
            (
                "Investigate possible data exposure "
                "and begin the appropriate "
                "incident-response process."
            )
        )

        add_unique(
            recommendations,
            (
                "Reset or rotate exposed credentials "
                "and monitor affected accounts "
                "for misuse."
            )
        )

    elif category == "DDoS":

        add_unique(
            recommendations,
            (
                "Review DDoS protections, traffic "
                "filtering and rate-limiting controls."
            )
        )

        add_unique(
            recommendations,
            (
                "Monitor network availability and "
                "unusual traffic patterns."
            )
        )

    elif category == "Other malware":

        add_unique(
            recommendations,
            (
                "Update endpoint detections and "
                "monitor systems for indicators "
                "associated with the reported malware."
            )
        )

        add_unique(
            recommendations,
            (
                "Isolate systems showing suspicious "
                "behaviour and investigate them "
                "before reconnecting."
            )
        )

    else:

        add_unique(
            recommendations,
            (
                "Review the reported development and "
                "determine whether the affected products "
                "or services are used in the organisation."
            )
        )

    # =====================================================
    # TAG-BASED GUIDANCE
    # =====================================================

    # Low severity articles can contain technical terms
    # merely as background discussion. Avoid turning every
    # mention into a strong remediation instruction.
    use_tag_recommendations = (
        severity_score >= 20
    )

    if (
        use_tag_recommendations
        and "Zero-Day" in tags
    ):

        add_unique(
            recommendations,
            (
                "Prioritise vendor mitigations and "
                "monitor for updates while a complete "
                "patch is unavailable."
            )
        )

    if (
        use_tag_recommendations
        and "Remote Code Execution" in tags
    ):

        add_unique(
            recommendations,
            (
                "Restrict external access to affected "
                "services and prioritise remediation "
                "of remote code execution exposure."
            )
        )

    if (
        use_tag_recommendations
        and "Privilege Escalation" in tags
    ):

        add_unique(
            recommendations,
            (
                "Review privileged access and apply "
                "least-privilege controls to "
                "affected systems."
            )
        )

    if (
        use_tag_recommendations
        and "Credential Theft" in tags
    ):

        add_unique(
            recommendations,
            (
                "Reset potentially compromised "
                "credentials, revoke active sessions "
                "and enforce multi-factor authentication."
            )
        )

    if (
        use_tag_recommendations
        and "Supply Chain" in tags
    ):

        add_unique(
            recommendations,
            (
                "Review affected dependencies, packages "
                "or suppliers and verify trusted "
                "versions before deployment."
            )
        )

    if (
        use_tag_recommendations
        and "SQL Injection" in tags
    ):

        add_unique(
            recommendations,
            (
                "Use parameterised queries and review "
                "exposed web applications for SQL "
                "injection weaknesses."
            )
        )

    if (
        use_tag_recommendations
        and "Social Engineering" in tags
        and category != "Phishing"
    ):

        add_unique(
            recommendations,
            (
                "Remind users to independently verify "
                "unusual requests before sharing "
                "credentials or sensitive information."
            )
        )

    # =====================================================
    # CISA KEV GUIDANCE
    # =====================================================

    if get_kev_cves(
        cve_rows
    ):

        add_unique(
            recommendations,
            (
                "Prioritise remediation because at "
                "least one related CVE appears in "
                "CISA's Known Exploited "
                "Vulnerabilities catalog."
            )
        )

    # Keep output concise for the website.
    recommendations = (
        recommendations[:4]
    )

    return "\n".join(
        f"- {item}"
        for item in recommendations
    )


# =========================================================
# PROCESS ARTICLES
# =========================================================

def process_articles(
    limit=5,
    retry_failed=False
):
    """
    Generate summaries for pending articles.
    """

    initialise_database()

    articles = (
        get_articles_for_summarization(
            limit=limit,
            retry_failed=retry_failed,
        )
    )

    if not articles:

        print(
            "No articles are waiting "
            "for summarization."
        )

        return

    counts = {
        "success": 0,
        "excluded": 0,
        "failed": 0,
    }

    for article in articles:

        article_id = (
            article["id"]
        )

        title = (
            article["title"]
            or ""
        )

        text = (
            article["full_content"]
            or article["content"]
            or ""
        )

        try:

            # Use the same suitability filter
            # already used by tagging and severity.
            suitable, reason = (
                check_article_suitability(
                    title,
                    text
                )
            )

            if not suitable:

                save_summary_exclusion(
                    article_id,
                    reason
                )

                print(
                    f"EXCLUDED: article "
                    f"{article_id}; {reason}"
                )

                counts[
                    "excluded"
                ] += 1

                continue

            context = (
                get_article_summary_context(
                    article_id
                )
            )

            summary = (
                generate_summary(
                    title,
                    text
                )
            )

            why_it_matters = (
                generate_why_it_matters(
                    article,
                    context
                )
            )

            recommendations = (
                generate_recommendations(
                    article,
                    context
                )
            )

            save_summary_result(
                article_id=article_id,
                summary=summary,
                why_it_matters=why_it_matters,
                recommendations=recommendations,
                method=SUMMARY_METHOD,
            )

            print()
            print(
                "=" * 70
            )

            print(
                f"ARTICLE {article_id}: "
                f"{title}"
            )

            print(
                "-" * 70
            )

            print(
                "SUMMARY:"
            )

            print(
                summary
            )

            print()

            print(
                "WHY IT MATTERS:"
            )

            print(
                why_it_matters
            )

            print()

            print(
                "RECOMMENDATIONS:"
            )

            print(
                recommendations
            )

            counts[
                "success"
            ] += 1

        except Exception as error:

            save_summary_failure(
                article_id,
                error
            )

            print(
                f"ERROR: article "
                f"{article_id}; "
                f"{error}"
            )

            counts[
                "failed"
            ] += 1

    print()
    print(
        "=" * 70
    )

    print(
        "SUMMARY GENERATION RESULTS"
    )

    print(
        "=" * 70
    )

    print(
        f"Successful: "
        f"{counts['success']}"
    )

    print(
        f"Excluded: "
        f"{counts['excluded']}"
    )

    print(
        f"Failed: "
        f"{counts['failed']}"
    )


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Generate lightweight NLP summaries "
            "for CYBERHEAD articles."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true"
    )

    args = parser.parse_args()

    if args.limit < 1:

        parser.error(
            "--limit must be at least 1."
        )

    process_articles(
        limit=args.limit,
        retry_failed=args.retry_failed,
    )