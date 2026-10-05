import json

from contextlib import asynccontextmanager

from typing import (
    Literal,
    Optional,
)

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.categories import (
    PRIMARY_CATEGORIES,
)

from app.database import (
    initialise_database,
    get_connection,
    get_articles,
    get_article_cves,
    get_cve_details,
)

from app.briefing_database import (
    initialise_briefing_database,
    get_current_briefing,
)


# =========================================================
# APPLICATION STARTUP
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Make sure the main CYBERHEAD database exists.
    initialise_database()

    # Make sure the Daily Briefing tables exist.
    initialise_briefing_database()

    yield


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="CYBERHEAD News API",

    description=(
        "Backend API for the CYBERHEAD "
        "cybersecurity news intelligence platform."
    ),

    version="1.0.0",

    lifespan=lifespan,
)


# =========================================================
# CORS
# =========================================================
#
# This allows the frontend to request data from FastAPI
# while you are developing locally.
#
# We can restrict this later when the final deployment
# address is known.
# =========================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "*"
    ],

    allow_credentials=False,

    allow_methods=[
        "GET"
    ],

    allow_headers=[
        "*"
    ],
)


# =========================================================
# BASIC STATUS ROUTE
# =========================================================

@app.get("/")
def home():

    return {
        "message":
            "CYBERHEAD News backend is running",

        "status":
            "ok",

        "api_version":
            "1.0.0",
    }


# =========================================================
# API STATUS
# =========================================================

@app.get("/api")
def api_status():

    return {
        "name":
            "CYBERHEAD News API",

        "status":
            "online",

        "version":
            "1.0.0",
    }


# =========================================================
# ARTICLE LIST
# =========================================================

@app.get("/api/articles")
def api_articles(

    category: Optional[str] = Query(
        default=None,
        description=(
            "Filter articles by cybersecurity category."
        ),
    ),

    severity: Optional[
        Literal[
            "Low",
            "Medium",
            "High",
            "Critical",
        ]
    ] = Query(
        default=None,
        description=(
            "Filter articles by severity."
        ),
    ),

    search: Optional[str] = Query(
        default=None,
        min_length=1,
        description=(
            "Search article title, summary "
            "and extracted article text."
        ),
    ),

    sort: Literal[
        "latest",
        "severity",
    ] = Query(
        default="latest",
        description=(
            "Sort by latest publication "
            "or highest severity."
        ),
    ),

    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description=(
            "Maximum number of articles returned."
        ),
    ),

    offset: int = Query(
        default=0,
        ge=0,
        description=(
            "Number of matching articles to skip."
        ),
    ),
):

    # -----------------------------------------------------
    # Validate category
    # -----------------------------------------------------

    if (
        category is not None

        and category
        not in PRIMARY_CATEGORIES
    ):

        raise HTTPException(
            status_code=400,

            detail={
                "message":
                    "Invalid category.",

                "valid_categories":
                    list(
                        PRIMARY_CATEGORIES
                    ),
            },
        )

    # -----------------------------------------------------
    # Build SQL filters safely
    # -----------------------------------------------------

    conditions = [

        "summary_status = 'success'",

        "severity_status = 'success'",

        "severity IS NOT NULL",

        "severity_score IS NOT NULL",
    ]

    parameters = []

    if category is not None:

        conditions.append(
            "category = ?"
        )

        parameters.append(
            category
        )

    if severity is not None:

        conditions.append(
            "severity = ?"
        )

        parameters.append(
            severity
        )

    if search is not None:

        search_value = (
            f"%{search.strip().lower()}%"
        )

        conditions.append(
            """
            (
                lower(title) LIKE ?

                OR lower(
                    COALESCE(
                        summary,
                        ''
                    )
                ) LIKE ?

                OR lower(
                    COALESCE(
                        full_content,
                        ''
                    )
                ) LIKE ?
            )
            """
        )

        parameters.extend([
            search_value,
            search_value,
            search_value,
        ])

    where_clause = (
        " AND ".join(
            conditions
        )
    )

    # -----------------------------------------------------
    # Sorting
    # -----------------------------------------------------

    if sort == "severity":

        order_clause = """
            severity_score DESC,

            COALESCE(
                published_at,
                collected_at
            ) DESC,

            id DESC
        """

    else:

        order_clause = """
            COALESCE(
                published_at,
                collected_at
            ) DESC,

            id DESC
        """

    # -----------------------------------------------------
    # Database queries
    # -----------------------------------------------------

    with get_connection() as connection:

        total_row = (
            connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total

                FROM articles

                WHERE
                    {where_clause}
                """,
                parameters,
            ).fetchone()
        )

        total = (
            total_row[
                "total"
            ]
        )

        rows = (
            connection.execute(
                f"""
                SELECT

                    id,

                    title,

                    url,

                    source,

                    published_at,

                    collected_at,

                    category,

                    severity,

                    severity_score,

                    summary,

                    why_it_matters,

                    recommendations

                FROM articles

                WHERE
                    {where_clause}

                ORDER BY
                    {order_clause}

                LIMIT ?

                OFFSET ?
                """,
                (
                    *parameters,

                    limit,

                    offset,
                ),
            ).fetchall()
        )

    articles = [
        dict(row)
        for row in rows
    ]

    return {

        "total":
            total,

        "returned":
            len(
                articles
            ),

        "limit":
            limit,

        "offset":
            offset,

        "filters": {

            "category":
                category,

            "severity":
                severity,

            "search":
                search,

            "sort":
                sort,
        },

        "articles":
            articles,
    }


# =========================================================
# HELPER - READ NVD RECORD
# =========================================================

def get_cve_api_details(
    row
):
    """
    Convert stored NVD/CISA data into a smaller,
    frontend-friendly structure.
    """

    record = {}

    if row[
        "record_json"
    ]:

        try:

            record = json.loads(
                row[
                    "record_json"
                ]
            )

        except json.JSONDecodeError:

            record = {}

    # -----------------------------------------------------
    # NVD English description
    # -----------------------------------------------------

    description = None

    for item in record.get(
        "descriptions",
        []
    ):

        if (
            item.get(
                "lang"
            )
            == "en"
        ):

            description = (
                item.get(
                    "value"
                )
            )

            break

    # -----------------------------------------------------
    # Maximum CVSS score
    # -----------------------------------------------------

    maximum_cvss = None

    for (
        metric_name,
        assessments
    ) in record.get(
        "metrics",
        {}
    ).items():

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

            score = (
                cvss_data.get(
                    "baseScore"
                )
            )

            if score is None:

                continue

            try:

                score = float(
                    score
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            if (
                maximum_cvss is None

                or score
                > maximum_cvss
            ):

                maximum_cvss = (
                    score
                )

    # -----------------------------------------------------
    # Return readable API structure
    # -----------------------------------------------------

    return {

        "cve_id":
            row[
                "cve_id"
            ],

        "nvd_status":
            row[
                "lookup_status"
            ],

        "vulnerability_status":
            record.get(
                "vulnStatus"
            ),

        "description":
            description,

        "max_cvss":
            maximum_cvss,

        "nvd_url":
            (
                "https://nvd.nist.gov/vuln/detail/"
                + row[
                    "cve_id"
                ]
            ),

        "cisa_kev": {

            "listed":
                (
                    row[
                        "kev_cve_id"
                    ]
                    is not None
                ),

            "vendor":
                row[
                    "vendor_project"
                ],

            "product":
                row[
                    "product"
                ],

            "vulnerability_name":
                row[
                    "vulnerability_name"
                ],

            "date_added":
                row[
                    "date_added"
                ],

            "required_action":
                row[
                    "required_action"
                ],

            "due_date":
                row[
                    "due_date"
                ],

            "known_ransomware_campaign_use":
                row[
                    "known_ransomware_campaign_use"
                ],
        },
    }


# =========================================================
# SINGLE ARTICLE
# =========================================================

@app.get(
    "/api/articles/{article_id}"
)
def api_article_detail(
    article_id: int
):

    # -----------------------------------------------------
    # Article
    # -----------------------------------------------------

    with get_connection() as connection:

        article_row = (
            connection.execute(
                """
                SELECT

                    id,

                    title,

                    url,

                    source,

                    published_at,

                    collected_at,

                    category,

                    severity,

                    severity_score,

                    severity_reason,

                    summary,

                    why_it_matters,

                    recommendations,

                    summary_method

                FROM articles

                WHERE id = ?
                """,
                (
                    article_id,
                ),
            ).fetchone()
        )

        if article_row is None:

            raise HTTPException(
                status_code=404,

                detail=(
                    "Article not found."
                ),
            )

        # -------------------------------------------------
        # Threat tags
        # -------------------------------------------------

        tag_rows = (
            connection.execute(
                """
                SELECT

                    tag,

                    score,

                    evidence_json

                FROM article_tags

                WHERE article_id = ?

                ORDER BY
                    score DESC,
                    tag ASC
                """,
                (
                    article_id,
                ),
            ).fetchall()
        )

        # -------------------------------------------------
        # CVE + NVD + CISA information
        # -------------------------------------------------

        cve_rows = (
            connection.execute(
                """
                SELECT

                    article_cves.cve_id,

                    cve_details.lookup_status,

                    cve_details.record_json,

                    cisa_kev.cve_id
                        AS kev_cve_id,

                    cisa_kev.vendor_project,

                    cisa_kev.product,

                    cisa_kev.vulnerability_name,

                    cisa_kev.date_added,

                    cisa_kev.required_action,

                    cisa_kev.due_date,

                    cisa_kev.known_ransomware_campaign_use

                FROM article_cves

                LEFT JOIN cve_details

                    ON cve_details.cve_id =
                       article_cves.cve_id

                LEFT JOIN cisa_kev

                    ON cisa_kev.cve_id =
                       article_cves.cve_id

                WHERE
                    article_cves.article_id = ?

                ORDER BY
                    article_cves.cve_id
                """,
                (
                    article_id,
                ),
            ).fetchall()
        )

    article = dict(
        article_row
    )

    # -----------------------------------------------------
    # Prepare tags
    # -----------------------------------------------------

    tags = []

    for row in tag_rows:

        evidence = {}

        if row[
            "evidence_json"
        ]:

            try:

                evidence = json.loads(
                    row[
                        "evidence_json"
                    ]
                )

            except json.JSONDecodeError:

                evidence = {}

        tags.append({

            "tag":
                row[
                    "tag"
                ],

            "score":
                row[
                    "score"
                ],

            "evidence":
                evidence,
        })

    # -----------------------------------------------------
    # Prepare CVEs
    # -----------------------------------------------------

    cves = [
        get_cve_api_details(
            row
        )
        for row in cve_rows
    ]

    article[
        "threat_tags"
    ] = tags

    article[
        "cves"
    ] = cves

    return article


# =========================================================
# DAILY BRIEFING
# =========================================================

@app.get(
    "/api/daily-briefing"
)
def api_daily_briefing():

    briefing = (
        get_current_briefing()
    )

    if briefing is None:

        raise HTTPException(

            status_code=404,

            detail=(
                "No Daily Briefing "
                "has been generated yet."
            ),
        )

    # category_counts_json is the raw DB field.
    # The parsed category_counts field is better
    # for the frontend.

    briefing.pop(
        "category_counts_json",
        None,
    )

    return {

        "name":
            "CYBERHEAD Daily Briefing",

        "coverage_hours":
            24,

        "minimum_priority_articles":
            5,

        "critical_rule":
            (
                "All Critical threats "
                "within the rolling "
                "24-hour period are included."
            ),

        **briefing,
    }


# =========================================================
# DASHBOARD STATISTICS
# =========================================================

@app.get(
    "/api/stats"
)
def api_stats():

    with get_connection() as connection:

        # -------------------------------------------------
        # Total collected articles
        # -------------------------------------------------

        total_articles = (
            connection.execute(
                """
                SELECT COUNT(*)
                AS total

                FROM articles
                """
            ).fetchone()[
                "total"
            ]
        )

        # -------------------------------------------------
        # Articles ready for website display
        # -------------------------------------------------

        processed_articles = (
            connection.execute(
                """
                SELECT COUNT(*)
                AS total

                FROM articles

                WHERE
                    summary_status = 'success'

                AND
                    severity_status = 'success'

                AND
                    severity IS NOT NULL
                """
            ).fetchone()[
                "total"
            ]
        )

        # -------------------------------------------------
        # Severity distribution
        # -------------------------------------------------

        severity_rows = (
            connection.execute(
                """
                SELECT

                    severity,

                    COUNT(*) AS total

                FROM articles

                WHERE
                    summary_status = 'success'

                AND
                    severity IS NOT NULL

                GROUP BY
                    severity
                """
            ).fetchall()
        )

        # -------------------------------------------------
        # Category distribution
        # -------------------------------------------------

        category_rows = (
            connection.execute(
                """
                SELECT

                    category,

                    COUNT(*) AS total

                FROM articles

                WHERE
                    summary_status = 'success'

                AND
                    category IS NOT NULL

                GROUP BY
                    category

                ORDER BY
                    total DESC
                """
            ).fetchall()
        )

    severity_distribution = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
    }

    for row in severity_rows:

        severity = (
            row[
                "severity"
            ]
        )

        if (
            severity
            in severity_distribution
        ):

            severity_distribution[
                severity
            ] = row[
                "total"
            ]

    category_distribution = {

        row[
            "category"
        ]:
            row[
                "total"
            ]

        for row in category_rows
    }

    # -----------------------------------------------------
    # Current rolling Daily Briefing statistics
    # -----------------------------------------------------

    briefing = (
        get_current_briefing()
    )

    if briefing is None:

        last_24_hours = {

            "available":
                False,

            "last_updated":
                None,

            "articles_considered":
                0,

            "articles_in_briefing":
                0,

            "severity":
                {
                    "Critical": 0,
                    "High": 0,
                    "Medium": 0,
                    "Low": 0,
                },
        }

    else:

        last_24_hours = {

            "available":
                True,

            "last_updated":
                briefing[
                    "generated_at"
                ],

            "period_start":
                briefing[
                    "period_start"
                ],

            "period_end":
                briefing[
                    "period_end"
                ],

            "articles_considered":
                briefing[
                    "total_considered"
                ],

            "articles_in_briefing":
                len(
                    briefing.get(
                        "articles",
                        []
                    )
                ),

            "severity": {

                "Critical":
                    briefing[
                        "critical_count"
                    ],

                "High":
                    briefing[
                        "high_count"
                    ],

                "Medium":
                    briefing[
                        "medium_count"
                    ],

                "Low":
                    briefing[
                        "low_count"
                    ],
            },
        }

    return {

        "total_articles":
            total_articles,

        "processed_articles":
            processed_articles,

        "severity_distribution":
            severity_distribution,

        "category_distribution":
            category_distribution,

        "last_24_hours":
            last_24_hours,
    }


# =========================================================
# CATEGORY LIST FOR FRONTEND FILTERS
# =========================================================

@app.get(
    "/api/categories"
)
def api_categories():

    return {
        "categories":
            list(
                PRIMARY_CATEGORIES
            )
    }


# =========================================================
# SEVERITY LIST FOR FRONTEND FILTERS
# =========================================================

@app.get(
    "/api/severities"
)
def api_severities():

    return {
        "severities": [
            "Critical",
            "High",
            "Medium",
            "Low",
        ]
    }


# =========================================================
# OLD DEVELOPMENT / TEST ROUTES
# =========================================================
#
# Keeping these so your previous API tests do not break.
# The frontend should use /api/... routes instead.
# =========================================================

@app.get(
    "/articles"
)
def list_articles():

    articles = (
        get_articles()
    )

    return {

        "count":
            len(
                articles
            ),

        "articles":
            articles,
    }


@app.get(
    "/categories"
)
def list_categories():

    return {
        "categories":
            list(
                PRIMARY_CATEGORIES
            )
    }


@app.get(
    "/article-cves"
)
def list_article_cves():

    links = (
        get_article_cves()
    )

    return {

        "count":
            len(
                links
            ),

        "article_cves":
            links,
    }


@app.get(
    "/cves"
)
def list_cve_details():

    details = (
        get_cve_details()
    )

    return {

        "count":
            len(
                details
            ),

        "cves":
            details,
    }