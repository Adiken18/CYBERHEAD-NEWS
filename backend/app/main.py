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

from app.source_api import (
    router as source_router,
)

from app.source_manager import (
    initialise_source_database,
)


# =========================================================
# APPLICATION STARTUP
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Main CYBERHEAD database
    initialise_database()

    # Daily Briefing tables
    initialise_briefing_database()

    # Source management table
    #
    # IMPORTANT:
    # This runs once when FastAPI starts.
    # GET /api/sources does not need to initialise
    # or write to the database every time.
    initialise_source_database()

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
# SOURCE MANAGEMENT ROUTER
# =========================================================

app.include_router(
    source_router
)


# =========================================================
# CORS
# =========================================================
#
# Required because the frontend is served by VS Code
# Live Server on a different local port.
#
# GET:
#   Reading articles, briefing, stats, sources.
#
# POST:
#   Testing and adding sources.
#
# PATCH:
#   Enabling or disabling sources.
# =========================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "*"
    ],

    allow_credentials=False,

    allow_methods=[
        "GET",
        "POST",
        "PATCH",
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
            "Search article titles, summaries, article text, "
            "sources, categories, severities, CVEs "
            "and threat tags."
        ),
    ),

    sort: Literal[
        "latest",
        "severity",
    ] = Query(

        default="latest",

        description=(
            "Sort matching reports by latest publication "
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

    # =====================================================
    # VALIDATE CATEGORY
    # =====================================================

    if (
        category is not None
        and category not in PRIMARY_CATEGORIES
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


    # =====================================================
    # BASE FILTERS
    # =====================================================

    conditions = [

        "summary_status = 'success'",

        "severity_status = 'success'",

        "severity IS NOT NULL",

        "severity_score IS NOT NULL",
    ]


    parameters = []


    # =====================================================
    # CATEGORY FILTER
    # =====================================================

    if category is not None:

        conditions.append(
            "category = ?"
        )

        parameters.append(
            category
        )


    # =====================================================
    # SEVERITY FILTER
    # =====================================================

    if severity is not None:

        conditions.append(
            "severity = ?"
        )

        parameters.append(
            severity
        )


    # =====================================================
    # SEARCH
    # =====================================================

    search_value = None

    exact_search_value = None


    if search is not None:

        cleaned_search = (
            search
            .strip()
            .lower()
        )


        if cleaned_search:

            search_value = (
                f"%{cleaned_search}%"
            )

            exact_search_value = (
                cleaned_search
            )


            conditions.append(
                """
                (
                    lower(
                        COALESCE(
                            title,
                            ''
                        )
                    ) LIKE ?

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

                    OR lower(
                        COALESCE(
                            source,
                            ''
                        )
                    ) LIKE ?

                    OR lower(
                        COALESCE(
                            category,
                            ''
                        )
                    ) LIKE ?

                    OR lower(
                        COALESCE(
                            severity,
                            ''
                        )
                    ) LIKE ?

                    OR lower(
                        COALESCE(
                            why_it_matters,
                            ''
                        )
                    ) LIKE ?

                    OR lower(
                        COALESCE(
                            recommendations,
                            ''
                        )
                    ) LIKE ?

                    OR EXISTS (

                        SELECT 1

                        FROM article_cves

                        WHERE
                            article_cves.article_id
                            =
                            articles.id

                            AND lower(
                                article_cves.cve_id
                            ) LIKE ?
                    )

                    OR EXISTS (

                        SELECT 1

                        FROM article_tags

                        WHERE
                            article_tags.article_id
                            =
                            articles.id

                            AND lower(
                                article_tags.tag
                            ) LIKE ?
                    )
                )
                """
            )


            parameters.extend([

                search_value,  # title

                search_value,  # summary

                search_value,  # full article

                search_value,  # source

                search_value,  # category

                search_value,  # severity

                search_value,  # why it matters

                search_value,  # recommendations

                search_value,  # CVE

                search_value,  # threat tag
            ])


    # =====================================================
    # BUILD WHERE CLAUSE
    # =====================================================

    where_clause = (
        " AND ".join(
            conditions
        )
    )


    # =====================================================
    # SEARCH RELEVANCE
    # =====================================================

    relevance_clause = ""

    relevance_parameters = []


    if (
        search_value is not None
        and exact_search_value is not None
    ):

        relevance_clause = """
            CASE

                /*
                 * Exact CYBERHEAD severity.
                 *
                 * Example:
                 * search = Critical
                 *
                 * Actual Critical reports should appear
                 * before articles that only mention the
                 * word "critical".
                 */
                WHEN lower(
                    COALESCE(
                        severity,
                        ''
                    )
                ) = ?
                THEN 140


                /*
                 * Exact cybersecurity category.
                 *
                 * Example:
                 * search = Ransomware
                 */
                WHEN lower(
                    COALESCE(
                        category,
                        ''
                    )
                ) = ?
                THEN 135


                /*
                 * Exact CVE match.
                 *
                 * Example:
                 * CVE-2026-12345
                 */
                WHEN EXISTS (

                    SELECT 1

                    FROM article_cves

                    WHERE
                        article_cves.article_id
                        =
                        articles.id

                        AND lower(
                            article_cves.cve_id
                        ) = ?
                )
                THEN 130


                /*
                 * Exact threat-tag match.
                 *
                 * Example:
                 * Remote Code Execution
                 */
                WHEN EXISTS (

                    SELECT 1

                    FROM article_tags

                    WHERE
                        article_tags.article_id
                        =
                        articles.id

                        AND lower(
                            article_tags.tag
                        ) = ?
                )
                THEN 125


                /*
                 * Exact title match.
                 */
                WHEN lower(
                    COALESCE(
                        title,
                        ''
                    )
                ) = ?
                THEN 120


                /*
                 * Search term appears in title.
                 *
                 * Example:
                 * search = Atlassian
                 */
                WHEN lower(
                    COALESCE(
                        title,
                        ''
                    )
                ) LIKE ?
                THEN 110


                /*
                 * Partial CVE match.
                 *
                 * Example:
                 * search = CVE-2026
                 */
                WHEN EXISTS (

                    SELECT 1

                    FROM article_cves

                    WHERE
                        article_cves.article_id
                        =
                        articles.id

                        AND lower(
                            article_cves.cve_id
                        ) LIKE ?
                )
                THEN 100


                /*
                 * Partial threat-tag match.
                 */
                WHEN EXISTS (

                    SELECT 1

                    FROM article_tags

                    WHERE
                        article_tags.article_id
                        =
                        articles.id

                        AND lower(
                            article_tags.tag
                        ) LIKE ?
                )
                THEN 95


                /*
                 * Source match.
                 *
                 * Example:
                 * Security Affairs
                 */
                WHEN lower(
                    COALESCE(
                        source,
                        ''
                    )
                ) LIKE ?
                THEN 80


                /*
                 * Summary match.
                 */
                WHEN lower(
                    COALESCE(
                        summary,
                        ''
                    )
                ) LIKE ?
                THEN 70


                /*
                 * Why-it-matters evidence.
                 */
                WHEN lower(
                    COALESCE(
                        why_it_matters,
                        ''
                    )
                ) LIKE ?
                THEN 60


                /*
                 * Defensive recommendation match.
                 */
                WHEN lower(
                    COALESCE(
                        recommendations,
                        ''
                    )
                ) LIKE ?
                THEN 50


                /*
                 * General article-text match.
                 *
                 * This is deliberately lowest because
                 * an article may only mention the term
                 * briefly and not actually be about it.
                 */
                WHEN lower(
                    COALESCE(
                        full_content,
                        ''
                    )
                ) LIKE ?
                THEN 20


                ELSE 0

            END
        """


        relevance_parameters = [

            # Exact severity
            exact_search_value,

            # Exact category
            exact_search_value,

            # Exact CVE
            exact_search_value,

            # Exact threat tag
            exact_search_value,

            # Exact title
            exact_search_value,

            # Title contains search
            search_value,

            # Partial CVE
            search_value,

            # Partial threat tag
            search_value,

            # Source
            search_value,

            # Summary
            search_value,

            # Why it matters
            search_value,

            # Recommendations
            search_value,

            # Full article text
            search_value,
        ]


    # =====================================================
    # SORTING
    # =====================================================
    
    if search_value is not None:

        if sort == "severity":

            order_clause = f"""
                {relevance_clause} DESC,

                severity_score DESC,

                COALESCE(
                    published_at,
                    collected_at
                ) DESC,

                id DESC
            """

        else:

            order_clause = f"""
                {relevance_clause} DESC,

                COALESCE(
                    published_at,
                    collected_at
                ) DESC,

                id DESC
            """


    elif sort == "severity":

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


    # =====================================================
    # DATABASE
    # =====================================================

    with get_connection() as connection:


        # -------------------------------------------------
        # TOTAL NUMBER OF MATCHES
        # -------------------------------------------------

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


        # -------------------------------------------------
        # ARTICLE RESULTS
        # -------------------------------------------------

        query_parameters = [

            *parameters,

            *relevance_parameters,

            limit,

            offset,
        ]


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

                query_parameters,

            ).fetchall()
        )


    # =====================================================
    # API RESPONSE
    # =====================================================

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
            ==
            "en"
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
                ValueError,
            ):

                continue


            if (
                maximum_cvss is None
                or score > maximum_cvss
            ):

                maximum_cvss = (
                    score
                )

    # -----------------------------------------------------
    # Frontend-friendly result
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
                +
                row[
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

    with get_connection() as connection:

        # -------------------------------------------------
        # Article
        # -------------------------------------------------

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
        # CVE + NVD + CISA
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
                SELECT
                    COUNT(*) AS total

                FROM articles
                """
            ).fetchone()[
                "total"
            ]
        )

        # -------------------------------------------------
        # Processed articles
        # -------------------------------------------------

        processed_articles = (
            connection.execute(
                """
                SELECT
                    COUNT(*) AS total

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

        "Critical":
            0,

        "High":
            0,

        "Medium":
            0,

        "Low":
            0,
    }


    for row in severity_rows:

        severity_name = (
            row[
                "severity"
            ]
        )


        if (
            severity_name
            in severity_distribution
        ):

            severity_distribution[
                severity_name
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
    # Rolling 24-hour briefing statistics
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

            "severity": {

                "Critical":
                    0,

                "High":
                    0,

                "Medium":
                    0,

                "Low":
                    0,
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
# CATEGORY LIST
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
# SEVERITY LIST
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
# These are kept so earlier testing commands still work.
# The frontend should use the /api/... routes.
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