import argparse
import logging
import time

import requests

from app.database import (
    initialise_database,
    get_cves_for_lookup,
    save_cve_lookup,
)


logger = logging.getLogger(__name__)

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
REQUEST_DELAY = 6.5


def fetch_cve(session, cve_id):
    with session.get(
        NVD_API_URL,
        params={"cveId": cve_id},
        timeout=(10, 45)
    ) as response:
        response.raise_for_status()
        payload = response.json()

    vulnerabilities = payload.get("vulnerabilities")

    if not isinstance(vulnerabilities, list):
        raise ValueError("NVD returned an unexpected response structure.")

    if not vulnerabilities:
        if payload.get("totalResults") == 0:
            return None

        raise ValueError("NVD returned an inconsistent empty response.")

    for item in vulnerabilities:
        record = item.get("cve", {})

        if record.get("id") == cve_id:
            return record

    raise ValueError("NVD did not return the requested CVE ID.")


def enrich_cves(limit=5):
    initialise_database()
    cve_ids = get_cves_for_lookup(limit)

    if not cve_ids:
        logger.info(
            "No CVEs need lookup. Cached results are reused for 24 hours."
        )
        return 0

    counts = {"found": 0, "not_found": 0, "error": 0}

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "CyberheadNews/0.1 (academic CVE lookup)",
            "Accept": "application/json"
        })

        for cve_id in cve_ids:
            # Also wait before the first request to space consecutive runs.
            time.sleep(REQUEST_DELAY)

            logger.info("Looking up %s...", cve_id)

            record = None
            error_message = None
            stop_batch = False

            try:
                record = fetch_cve(session, cve_id)
                status = "found" if record is not None else "not_found"

            except requests.HTTPError as error:
                status = "error"
                code = error.response.status_code
                error_message = f"NVD returned HTTP {code}."

                # Stop rather than repeatedly contacting a blocked,
                # rate-limited or unavailable service.
                stop_batch = code in (403, 429) or code >= 500

                retry_after = error.response.headers.get("Retry-After")
                if retry_after:
                    error_message += f" Retry-After: {retry_after}."

            except (requests.RequestException, ValueError) as error:
                status = "error"
                error_message = str(error)
                stop_batch = True

            save_cve_lookup(
                cve_id=cve_id,
                status=status,
                record=record,
                error=error_message
            )

            counts[status] += 1

            if status == "found":
                logger.info(
                    "%s: record found; status=%s.",
                    cve_id,
                    record.get("vulnStatus", "unknown")
                )
            elif status == "not_found":
                logger.warning("%s: no matching NVD record.", cve_id)
            else:
                logger.error("%s: %s", cve_id, error_message)

            if stop_batch:
                logger.warning(
                    "Stopping this batch. Unprocessed CVEs remain available "
                    "for a later run."
                )
                break

    logger.info(
        "Finished: %s found, %s not found, %s errors.",
        counts["found"],
        counts["not_found"],
        counts["error"]
    )

    return counts["error"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Fetch NVD details for CVEs mentioned in articles."
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1.")

    errors = enrich_cves(limit=args.limit)

    raise SystemExit(1 if errors else 0)
