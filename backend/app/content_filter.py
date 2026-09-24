import re


UNSUITABLE_PATTERNS = {
    "webinar/event": [
        r"\bwebinar\b",
        r"\bvirtual event\b",
        r"\bregister now\b",
        r"\bconference\b",
    ],

    "mixed roundup": [
        r"\bweekly recap\b",
        r"\bweekly roundup\b",
        r"\bnews roundup\b",
        r"\bthreatsday\b",
        r"\btop stories\b",
    ],

    "promotional/sponsored": [
        r"\bsponsored content\b",
        r"\bsponsored by\b",
        r"\bpartner content\b",
    ],

    "press release": [
        r"\bpress release\b",
    ],
}


def check_article_suitability(title, text):
    """
    Return:
        (True, None)
        if the article is suitable for threat analysis.

    Return:
        (False, reason)
        if it looks like promotional, event, roundup,
        or other unsuitable content.
    """

    title = title or ""
    text = text or ""

    # Only inspect the title and beginning for this decision.
    # We do not want a random mention later in the article
    # to cause it to be rejected.
    lead_text = text[:1200]

    combined = f"{title} {lead_text}"

    for reason, patterns in UNSUITABLE_PATTERNS.items():

        for pattern in patterns:

            if re.search(
                pattern,
                combined,
                re.IGNORECASE
            ):
                return False, reason

    return True, None