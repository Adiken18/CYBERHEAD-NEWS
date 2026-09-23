import logging

import requests

from app.database import (
    initialise_database,
    get_detected_cve_ids,
    save_cisa_kev_record,
)


logger = logging.getLogger(__name__)


# Official CISA KEV feed
CISA_KEV_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/"
    "known_exploited_vulnerabilities.json"
)

# Official CISA GitHub mirror.
# Used only if cisa.gov cannot be reached.
CISA_GITHUB_FALLBACK = (
    "https://raw.githubusercontent.com/"
    "cisagov/kev-data/develop/"
    "known_exploited_vulnerabilities.json"
)


def download_catalog(session):
    """
    Download the CISA Known Exploited Vulnerabilities catalog.

    Try CISA first.
    If CISA cannot be reached, use CISA's official GitHub mirror.
    """

    urls = [
        CISA_KEV_URL,
        CISA_GITHUB_FALLBACK,
    ]

    last_error = None

    for url in urls:

        logger.info("Downloading CISA KEV catalog from %s", url)

        try:
            response = session.get(
                url,
                timeout=(10, 45)
            )

            response.raise_for_status()

            payload = response.json()

            vulnerabilities = payload.get("vulnerabilities")

            if not isinstance(vulnerabilities, list):
                raise ValueError(
                    "CISA returned an unexpected catalog structure."
                )

            logger.info(
                "CISA catalog downloaded successfully: %s entries.",
                len(vulnerabilities)
            )

            return payload

        except (
            requests.RequestException,
            ValueError
        ) as error:

            last_error = error

            logger.warning(
                "Could not use this CISA source: %s",
                error
            )

    raise RuntimeError(
        f"Unable to download the CISA KEV catalog: {last_error}"
    )


def enrich_cisa_kev():
    """
    Compare detected article CVEs with CISA KEV.

    Only KEV records matching CVEs already detected
    in CYBERHEAD articles are stored.
    """

    initialise_database()

    detected_cves = set(
        get_detected_cve_ids()
    )

    if not detected_cves:
        logger.info(
            "No detected CVEs are available for CISA matching."
        )
        return 0

    logger.info(
        "%s distinct detected CVEs will be checked against CISA KEV.",
        len(detected_cves)
    )

    with requests.Session() as session:

        session.headers.update({
            "User-Agent": (
                "CyberheadNews/0.1 "
                "(academic CISA KEV lookup)"
            ),
            "Accept": "application/json"
        })

        catalog = download_catalog(session)

    vulnerabilities = catalog["vulnerabilities"]

    matches = 0

    for record in vulnerabilities:

        cve_id = record.get("cveID")

        if cve_id not in detected_cves:
            continue

        save_cisa_kev_record(record)

        matches += 1

        logger.info(
            "KEV MATCH: %s | %s | ransomware=%s",
            cve_id,
            record.get(
                "vulnerabilityName",
                "Unknown vulnerability"
            ),
            record.get(
                "knownRansomwareCampaignUse",
                "Unknown"
            )
        )

    logger.info(
        "Finished: %s detected CVEs checked; "
        "%s are present in CISA KEV.",
        len(detected_cves),
        matches
    )

    return 0


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    try:
        enrich_cisa_kev()

    except (
        requests.RequestException,
        RuntimeError,
        ValueError
    ) as error:

        logger.error(
            "CISA KEV enrichment failed: %s",
            error
        )

        raise SystemExit(1)

    raise SystemExit(0)