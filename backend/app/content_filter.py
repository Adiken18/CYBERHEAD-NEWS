import re


UNSUITABLE_PATTERNS = {
    "webinar/event": [
        r"\bwebinar\b",
        r"\bvirtual event\b",
        r"\bregister now\b",
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
        if the article is promotional, an event,
        a roundup, or another unsuitable item.
    """

    title = title or ""
    text = text or ""

    lead_text = text[:1200]

    # -----------------------------------------------------
    # EVENT / WEBINAR
    #
    # Only check the TITLE.
    #
    # A normal news article may mention a conference
    # or webinar inside its body without being an event.
    # -----------------------------------------------------

    for pattern in UNSUITABLE_PATTERNS[
        "webinar/event"
    ]:

        if re.search(
            pattern,
            title,
            re.IGNORECASE
        ):
            return False, "webinar/event"

    # -----------------------------------------------------
    # ROUNDUPS
    #
    # Also check only the TITLE because a normal article
    # could mention another roundup inside the body.
    # -----------------------------------------------------

    for pattern in UNSUITABLE_PATTERNS[
        "mixed roundup"
    ]:

        if re.search(
            pattern,
            title,
            re.IGNORECASE
        ):
            return False, "mixed roundup"

    # -----------------------------------------------------
    # PROMOTIONAL / SPONSORED
    #
    # These indicators can appear near the beginning
    # even if they are not in the title.
    # -----------------------------------------------------

    combined = (
        f"{title} {lead_text}"
    )

    for pattern in UNSUITABLE_PATTERNS[
        "promotional/sponsored"
    ]:

        if re.search(
            pattern,
            combined,
            re.IGNORECASE
        ):
            return False, "promotional/sponsored"

    # -----------------------------------------------------
    # PRESS RELEASE
    # -----------------------------------------------------

    for pattern in UNSUITABLE_PATTERNS[
        "press release"
    ]:

        if re.search(
            pattern,
            combined,
            re.IGNORECASE
        ):
            return False, "press release"

    return True, None