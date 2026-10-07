import argparse
import logging
import time

import requests

from app.database import (
    initialise_database,
    get_cves_for_lookup,
    save_cve_lookup,
    get_connection,
)


logger = logging.getLogger(
    __name__
)


NVD_API_URL = (
    "https://services.nvd.nist.gov/"
    "rest/json/cves/2.0"
)

REQUEST_DELAY = 6.5


# =========================================================
# NVD REQUEST
# =========================================================

def fetch_cve(
    session,
    cve_id
):
    with session.get(

        NVD_API_URL,

        params={
            "cveId": cve_id
        },

        timeout=(
            10,
            45
        )

    ) as response:

        response.raise_for_status()

        payload = (
            response.json()
        )


    vulnerabilities = (
        payload.get(
            "vulnerabilities"
        )
    )


    if not isinstance(
        vulnerabilities,
        list
    ):

        raise ValueError(
            "NVD returned an unexpected "
            "response structure."
        )


    if not vulnerabilities:

        if (
            payload.get(
                "totalResults"
            )
            ==
            0
        ):

            return None


        raise ValueError(
            "NVD returned an inconsistent "
            "empty response."
        )


    for item in vulnerabilities:

        record = (
            item.get(
                "cve",
                {}
            )
        )


        if (
            record.get(
                "id"
            )
            ==
            cve_id
        ):

            return record


    raise ValueError(
        "NVD did not return "
        "the requested CVE ID."
    )


# =========================================================
# CACHE CHECK
# =========================================================

def has_cached_record(
    cve_id
):
    """
    Return True when CYBERHEAD already has
    a previously downloaded NVD record for
    the CVE.

    A refresh failure does not make the
    cached record unusable.
    """

    connection = (
        get_connection()
    )


    try:

        row = (
            connection.execute(
                """
                SELECT record_json
                FROM cve_details
                WHERE cve_id = ?
                """,
                (
                    cve_id,
                )
            ).fetchone()
        )


        return bool(
            row
            and
            row["record_json"]
        )


    finally:

        connection.close()


# =========================================================
# SAFETY CHECK
# =========================================================

def count_unusable_cves():
    """
    Count detected CVEs for which CYBERHEAD
    has no usable NVD result.

    Usable states:

        found + cached record
        not_found
        error + previous cached record

    Unsafe states:

        no NVD lookup exists
        error with no cached record
    """

    connection = (
        get_connection()
    )


    try:

        row = (
            connection.execute(
                """
                SELECT COUNT(DISTINCT ac.cve_id)

                FROM article_cves AS ac

                LEFT JOIN cve_details AS cd
                    ON cd.cve_id = ac.cve_id

                WHERE
                    cd.cve_id IS NULL

                    OR (
                        cd.lookup_status = 'error'
                        AND cd.record_json IS NULL
                    )
                """
            ).fetchone()
        )


        return (
            int(
                row[0]
            )
        )


    finally:

        connection.close()


# =========================================================
# NVD ENRICHMENT
# =========================================================

def enrich_cves(
    limit=5
):
    """
    Refresh NVD information for detected CVEs.

    Temporary NVD failures do not stop the
    CYBERHEAD pipeline when a previous valid
    cached NVD record is already available.

    The pipeline only treats an NVD problem
    as fatal when a detected CVE has no usable
    NVD result at all.
    """

    initialise_database()


    cve_ids = (
        get_cves_for_lookup(
            limit
        )
    )


    if not cve_ids:

        logger.info(
            "No CVEs need lookup. "
            "Cached results are reused "
            "for 24 hours."
        )


        unusable = (
            count_unusable_cves()
        )


        if unusable:

            logger.error(
                "%s detected CVE(s) have "
                "no usable NVD result.",
                unusable
            )


        return unusable


    counts = {

        "found":
            0,

        "not_found":
            0,

        "warning":
            0,

        "error":
            0,
    }


    with requests.Session() as session:

        session.headers.update({

            "User-Agent":
                (
                    "CyberheadNews/0.2 "
                    "(academic CVE lookup)"
                ),

            "Accept":
                "application/json",
        })


        for cve_id in cve_ids:

            # NVD rate limiting.
            time.sleep(
                REQUEST_DELAY
            )


            logger.info(
                "Looking up %s...",
                cve_id
            )


            record = None

            error_message = None

            stop_batch = False


            try:

                record = (
                    fetch_cve(
                        session,
                        cve_id
                    )
                )


                status = (
                    "found"
                    if record is not None
                    else "not_found"
                )


            except requests.HTTPError as error:

                status = (
                    "error"
                )


                code = (
                    error.response.status_code
                )


                error_message = (
                    f"NVD returned HTTP {code}."
                )


                # Avoid repeatedly contacting NVD
                # when the service is unavailable
                # or rate-limiting CYBERHEAD.
                stop_batch = (

                    code
                    in (
                        403,
                        429,
                    )

                    or

                    code >= 500
                )


                retry_after = (
                    error.response.headers.get(
                        "Retry-After"
                    )
                )


                if retry_after:

                    error_message += (
                        " Retry-After: "
                        f"{retry_after}."
                    )


            except (
                requests.RequestException,
                ValueError,
            ) as error:

                status = (
                    "error"
                )


                error_message = (
                    str(error)
                )


                stop_batch = True


            # -------------------------------------------------
            # SAVE RESULT
            #
            # database.py already preserves record_json
            # when status == 'error'.
            # -------------------------------------------------

            save_cve_lookup(

                cve_id=
                    cve_id,

                status=
                    status,

                record=
                    record,

                error=
                    error_message,
            )


            # -------------------------------------------------
            # RESULT HANDLING
            # -------------------------------------------------

            if (
                status
                ==
                "found"
            ):

                counts[
                    "found"
                ] += 1


                logger.info(

                    "%s: record found; "
                    "status=%s.",

                    cve_id,

                    record.get(
                        "vulnStatus",
                        "unknown"
                    ),
                )


            elif (
                status
                ==
                "not_found"
            ):

                counts[
                    "not_found"
                ] += 1


                logger.warning(
                    "%s: no matching "
                    "NVD record.",
                    cve_id
                )


            else:

                # ---------------------------------------------
                # TEMPORARY FAILURE WITH CACHE
                # ---------------------------------------------

                if (
                    has_cached_record(
                        cve_id
                    )
                ):

                    counts[
                        "warning"
                    ] += 1


                    logger.warning(

                        "%s: NVD refresh failed, "
                        "but a previous cached "
                        "record is available. "
                        "CYBERHEAD will retain "
                        "the cached record. Error: %s",

                        cve_id,

                        error_message,
                    )


                # ---------------------------------------------
                # FAILURE WITHOUT CACHE
                # ---------------------------------------------

                else:

                    counts[
                        "error"
                    ] += 1


                    logger.error(

                        "%s: NVD lookup failed "
                        "and no cached record "
                        "is available. Error: %s",

                        cve_id,

                        error_message,
                    )


            # -------------------------------------------------
            # STOP REQUESTING WHEN NVD IS UNAVAILABLE
            # -------------------------------------------------

            if stop_batch:

                logger.warning(
                    "Stopping this NVD request batch "
                    "to avoid repeatedly contacting "
                    "an unavailable or rate-limited "
                    "service."
                )

                break


    # =====================================================
    # FINAL SAFETY CHECK
    # =====================================================

    unusable = (
        count_unusable_cves()
    )


    logger.info(
        "NVD enrichment finished: "
        "%s found, "
        "%s not found, "
        "%s cached-data warning(s), "
        "%s request failure(s) without cache.",
        counts["found"],
        counts["not_found"],
        counts["warning"],
        counts["error"],
    )


    if unusable:

        logger.error(
            "%s detected CVE(s) currently "
            "have no usable NVD information.",
            unusable
        )

    else:

        logger.info(
            "All detected CVEs have a usable "
            "NVD result or a valid cached result."
        )


    # -----------------------------------------------------
    # IMPORTANT
    #
    # pipeline.py interprets a non-zero return value
    # as a reason to stop before threat analysis.
    #
    # We therefore return only the number of CVEs
    # that genuinely have no usable NVD result.
    # -----------------------------------------------------

    return unusable


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    logging.basicConfig(

        level=logging.INFO,

        format=(
            "%(levelname)s: "
            "%(message)s"
        ),
    )


    parser = (
        argparse.ArgumentParser(

            description=(
                "Fetch NVD details for CVEs "
                "mentioned in CYBERHEAD articles."
            )
        )
    )


    parser.add_argument(

        "--limit",

        type=int,

        default=5,
    )


    args = (
        parser.parse_args()
    )


    if (
        args.limit < 1
    ):

        parser.error(
            "--limit must be at least 1."
        )


    errors = (
        enrich_cves(
            limit=args.limit
        )
    )


    raise SystemExit(
        1
        if errors
        else 0
    )