(() => {
  "use strict";

  /* =========================================================
     BASIC HELPERS
     ========================================================= */

  const $ = (selector) =>
    document.querySelector(selector);


  const escape = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[character]
    );


  const withBreaks = (value) =>
    escape(value ?? "").replace(
      /\n/g,
      "<br>"
    );


  function parseDate(value) {

    const result =
      new Date(value);

    return Number.isNaN(
      result.getTime()
    )
      ? null
      : result;
  }


  function formatDate(value) {

    const result =
      parseDate(value);

    if (!result) {
      return "Date unavailable";
    }

    return result.toLocaleDateString(
      "en-GB",
      {
        day: "2-digit",
        month: "short",
        year: "numeric"
      }
    );
  }


  function formatTime(value) {

    const result =
      parseDate(value);

    if (!result) {
      return "--:--";
    }

    return result.toLocaleTimeString(
      "en-GB",
      {
        hour: "2-digit",
        minute: "2-digit"
      }
    );
  }


  function formatDateTime(value) {

    const result =
      parseDate(value);

    if (!result) {
      return "Not available";
    }

    return (
      result.toLocaleDateString(
        "en-GB",
        {
          day: "2-digit",
          month: "short",
          year: "numeric"
        }
      )
      +
      " · "
      +
      result.toLocaleTimeString(
        "en-GB",
        {
          hour: "2-digit",
          minute: "2-digit"
        }
      )
    );
  }


  /* =========================================================
     ROUTES
     ========================================================= */

  const routes = [

    [
      "briefing",
      "⌂",
      "Daily Briefing"
    ],

    [
      "alerts",
      "△",
      "Threats & Alerts"
    ],

    [
      "reports",
      "▤",
      "All Reports"
    ],

    [
      "saved",
      "♧",
      "Saved Stories"
    ],

    [
      "analysis",
      "▥",
      "Analysis"
    ],

    [
      "sources",
      "⚒",
      "Sources"
    ],

    [
      "about",
      "ⓘ",
      "About"
    ]
  ];


  /* =========================================================
     GENERAL LIVE DATA
     ========================================================= */

  let liveBriefing =
    null;

  let liveStats =
    null;

  let liveLoadError =
    null;

  let liveLoading =
    false;


  /* =========================================================
     REPORT STATE
     ========================================================= */

  let articleResponse =
    null;

  let articlesLoading =
    false;

  let articlesError =
    null;

  const ARTICLE_LIMIT =
    20;

  let articleOffset =
    0;

  let query =
    "";

  let severity =
    "All";

  let category =
    "All";

  let sort =
    "latest";

  let searchTimer =
    null;


  /* =========================================================
     ALERT STATE
     ========================================================= */

  let criticalAlertsResponse =
    null;

  let highAlertsResponse =
    null;

  let alertsLoading =
    false;

  let alertsError =
    null;


  /* =========================================================
     SAVED STORIES STATE
     ========================================================= */

  let saved =
    [];

  let savedArticles =
    [];

  let savedLoading =
    false;

  let savedError =
    null;

  let savedSeverityFilter =
    "All";


  /* =========================================================
     SOURCES STATE
     ========================================================= */

  let sourcesResponse =
    null;

  let sourcesLoading =
    false;

  let sourcesError =
    null;

  let sourceDraftName =
    "";

  let sourceDraftUrl =
    "";

  let sourceTestResult =
    null;

  let sourceTestLoading =
    false;

  let sourceAddLoading =
    false;

  let sourceToggleLoadingId =
    null;

  let sourceMessage =
    "";

  let sourceMessageType =
    "success";


  /* =========================================================
     SAVED STORIES STORAGE
     ========================================================= */

  try {

    const stored =
      JSON.parse(
        localStorage.getItem(
          "cyberhead.saved"
        )
        ||
        "[]"
      );


    if (
      Array.isArray(stored)
    ) {

      saved =
        stored.map(
          (value) =>
            String(value)
        );
    }

  } catch {

    saved =
      [];
  }


  function persistSaved() {

    try {

      localStorage.setItem(
        "cyberhead.saved",
        JSON.stringify(saved)
      );

      return true;

    } catch {

      $("#status").textContent =
        "Browser storage is unavailable. Saved stories may not persist.";

      return false;
    }
  }


  /* =========================================================
     CURRENT PAGE
     ========================================================= */

  function page() {

    const hash =
      location.hash.slice(1);


    return routes.some(
      (route) =>
        route[0] === hash
    )
      ? hash
      : "briefing";
  }


  /* =========================================================
     ARTICLE HELPERS
     ========================================================= */

  function liveArticleId(article) {

    return String(
      article.article_id
      ??
      article.id
    );
  }


  function liveBadges(article) {

    return `

      <span
        class="badge severity ${escape(
          article.severity
        )}"
      >
        ${escape(
          String(
            article.severity
            ??
            ""
          ).toUpperCase()
        )}
      </span>

      <span class="badge">
        ${escape(
          String(
            article.category
            ??
            "Uncategorised"
          ).toUpperCase()
        )}
      </span>
    `;
  }


  function liveArt(article) {

    const imageClass =
      article.severity === "Critical"
        ? "skull"
        : "";


    return `

      <div
        class="art ${imageClass}"
        role="img"
        aria-label="Cybersecurity threat illustration"
      ></div>
    `;
  }


  /* =========================================================
     ARTICLE CARD
     ========================================================= */

  function liveCard(
    article,
    featured = false
  ) {

    const articleId =
      liveArticleId(article);


    const published =
      article.published_at
      ||
      article.collected_at;


    return `

      <article
        class="card ${
          featured
            ? "featured"
            : ""
        }"
      >

        ${liveArt(article)}

        <div>

          <div class="meta">

            ${liveBadges(article)}

            <time>
              ${escape(
                formatDate(
                  published
                )
              )}
            </time>

          </div>

          <h3>
            ${escape(
              article.title
            )}
          </h3>

          <p>
            ${escape(
              article.summary
              ||
              "Summary unavailable."
            )}
          </p>

          <div class="actions">

            <span
              class="
                eyebrow
                severity-score
                ${escape(
                  article.severity
                )}
              "
            >

              CYBERHEAD SEVERITY SCORE

              ${escape(
                article.severity_score
              )}/100

            </span>

            <button
              data-live-open="${escape(
                articleId
              )}"
            >
              Read report →
            </button>

          </div>

          <div class="related">

            Source:

            ${escape(
              article.source
              ||
              "Unknown"
            )}

          </div>

        </div>

      </article>
    `;
  }


  /* =========================================================
     GENERIC PAGE HEADER
     ========================================================= */

  function pageIntro(
    title,
    subtitle
  ) {

    return `

      <div class="intro">

        <div>

          <div class="eyebrow">
            CYBERHEAD NEWS
          </div>

          <h1>
            ${title}
          </h1>

          <p>
            ${escape(
              subtitle
            )}
          </p>

        </div>

        <div class="clock">

          ${escape(
            formatDate(
              new Date()
            )
          )}

          <strong id="clock">

            ${
              new Date()
                .toLocaleTimeString(
                  "en-GB",
                  {
                    hour:
                      "2-digit",

                    minute:
                      "2-digit"
                  }
                )
            }

          </strong>

        </div>

      </div>
    `;
  }


  /* =========================================================
     DAILY BRIEFING
     ========================================================= */

  function liveBriefingIntro() {

    if (!liveBriefing) {

      return `

        <div class="intro">

          <div>

            <div class="eyebrow">
              CYBERHEAD INTELLIGENCE
            </div>

            <h1>
              Your
              <em>Daily Briefing</em>
            </h1>

            <p>
              Rolling cybersecurity briefing
              covering the previous 24 hours.
            </p>

          </div>

        </div>
      `;
    }


    return `

      <div class="intro">

        <div>

          <div class="eyebrow">
            CYBERHEAD INTELLIGENCE
          </div>

          <h1>
            Your
            <em>Daily Briefing</em>
          </h1>

          <p>

            ${escape(
              liveBriefing
                .total_considered
            )}

            analysed article(s)
            from the rolling previous
            24 hours.

          </p>

        </div>

        <div class="clock">

          LAST UPDATED

          <strong>

            ${escape(
              formatTime(
                liveBriefing
                  .generated_at
              )
            )}

          </strong>

          <span>

            ${escape(
              formatDate(
                liveBriefing
                  .generated_at
              )
            )}

          </span>

        </div>

      </div>
    `;
  }


  function briefingOverviewButton(
    level,
    count
  ) {

    return `

      <button
        class="brief-filter-row"
        data-briefing-severity="${escape(
          level
        )}"
      >

        <span
          class="
            brief-filter-name
            severity-text-${escape(
              level
            )}
          "
        >
          ${escape(level)}
        </span>

        <strong>
          ${escape(
            count ?? 0
          )}
        </strong>

        <span aria-hidden="true">
          →
        </span>

      </button>
    `;
  }


  function briefingCategoryButton(
    name,
    count
  ) {

    return `

      <button
        class="brief-filter-row"
        data-briefing-category="${escape(
          name
        )}"
      >

        <span class="brief-filter-name">
          ${escape(name)}
        </span>

        <strong>
          ${escape(count)}
        </strong>

        <span aria-hidden="true">
          →
        </span>

      </button>
    `;
  }


  function briefing() {

    if (liveLoadError) {

      return `

        ${liveBriefingIntro()}

        <div class="empty">

          <h2>
            DAILY BRIEFING UNAVAILABLE
          </h2>

          <p>
            ${escape(
              liveLoadError
            )}
          </p>

          <button id="retry-live">
            Retry connection
          </button>

        </div>
      `;
    }


    if (!liveBriefing) {

      return `

        ${liveBriefingIntro()}

        <div class="empty">
          Loading Daily Briefing...
        </div>
      `;
    }


    const stories =
      Array.isArray(
        liveBriefing.articles
      )
        ? liveBriefing.articles
        : [];


    const categories =
      liveBriefing
        .category_counts
      ||
      {};


    return `

      ${liveBriefingIntro()}

      <div class="layout">

        <div>

          <div class="section-label">
            TOP PRIORITY THREAT
          </div>

          ${
            stories[0]

              ? liveCard(
                  stories[0],
                  true
                )

              : `

                <div class="empty">

                  No qualifying threats
                  were found in the
                  previous 24 hours.

                </div>
              `
          }

          ${
            stories.length > 1

              ? `

                <div class="section-label">
                  MORE PRIORITY THREATS
                </div>

                <div class="grid">

                  ${
                    stories
                      .slice(1)
                      .map(
                        (article) =>
                          liveCard(
                            article
                          )
                      )
                      .join("")
                  }

                </div>
              `

              : ""
          }

        </div>


        <aside class="rail">

          <section class="panel">

            <h2>
              △ 24-HOUR THREAT OVERVIEW
            </h2>

            <div class="brief-filter-list">

              ${
                briefingOverviewButton(
                  "Critical",
                  liveBriefing
                    .critical_count
                )
              }

              ${
                briefingOverviewButton(
                  "High",
                  liveBriefing
                    .high_count
                )
              }

              ${
                briefingOverviewButton(
                  "Medium",
                  liveBriefing
                    .medium_count
                )
              }

              ${
                briefingOverviewButton(
                  "Low",
                  liveBriefing
                    .low_count
                )
              }

            </div>

          </section>


          <section class="panel">

            <h2>
              ▤ TODAY'S BRIEFING
            </h2>

            ${
              stories
                .map(
                  (
                    article,
                    index
                  ) => `

                    <button
                      class="brief-item"
                      data-live-open="${escape(
                        liveArticleId(
                          article
                        )
                      )}"
                    >

                      <span class="number">

                        ${String(
                          index + 1
                        ).padStart(
                          2,
                          "0"
                        )}

                      </span>

                      ${escape(
                        article.title
                      )}

                    </button>
                  `
                )
                .join("")
            }

          </section>


          <section class="panel">

            <h2>
              ▥ CATEGORIES
            </h2>

            <div class="brief-filter-list">

              ${
                Object.entries(
                  categories
                )
                  .map(
                    ([
                      name,
                      total
                    ]) =>
                      briefingCategoryButton(
                        name,
                        total
                      )
                  )
                  .join("")

                ||

                "<p>No category data.</p>"
              }

            </div>

          </section>

        </aside>

      </div>
    `;
  }


  /* =========================================================
     ALERTS
     ========================================================= */

  function isArticleInCurrentWindow(
    article
  ) {

    const articleDate =
      parseDate(
        article.published_at
        ||
        article.collected_at
      );


    if (!articleDate) {
      return false;
    }


    let start =
      parseDate(
        liveBriefing
          ?.period_start
      );


    let end =
      parseDate(
        liveBriefing
          ?.period_end
      );


    if (
      !start
      ||
      !end
    ) {

      end =
        new Date();


      start =
        new Date(
          end.getTime()
          -
          24
          *
          60
          *
          60
          *
          1000
        );
    }


    return (
      articleDate >= start
      &&
      articleDate <= end
    );
  }


  function currentThreatLevel() {

    if (!liveBriefing) {
      return "Unknown";
    }


    if (
      liveBriefing
        .critical_count > 0
    ) {

      return "Critical";
    }


    if (
      liveBriefing
        .high_count > 0
    ) {

      return "High";
    }


    if (
      liveBriefing
        .medium_count > 0
    ) {

      return "Medium";
    }


    return "Low";
  }


  function alertCard(article) {

    const published =
      article.published_at
      ||
      article.collected_at;


    return `

      <article class="panel">

        <div class="meta">

          ${liveBadges(article)}

          <time>

            ${escape(
              formatDate(
                published
              )
            )}

            ·

            ${escape(
              formatTime(
                published
              )
            )}

          </time>

        </div>

        <h3>
          ${escape(
            article.title
          )}
        </h3>

        <p>
          ${escape(
            article.summary
            ||
            "Summary unavailable."
          )}
        </p>

        <p>

          Source:

          <strong>
            ${escape(
              article.source
              ||
              "Unknown"
            )}
          </strong>

        </p>

        <div class="actions">

          <span
            class="
              eyebrow
              severity-score
              ${escape(
                article.severity
              )}
            "
          >

            CYBERHEAD SEVERITY SCORE

            ${escape(
              article.severity_score
            )}/100

          </span>

          <button
            data-live-open="${escape(
              liveArticleId(
                article
              )
            )}"
          >
            Read report →
          </button>

        </div>

      </article>
    `;
  }


  function alertsPage() {

    const threatLevel =
      currentThreatLevel();


    if (alertsLoading) {

      return `

        ${
          pageIntro(
            "Threats <em>& Alerts</em>",
            "Monitoring Critical and High threats from the rolling previous 24 hours."
          )
        }

        <div class="empty">
          Loading current threats...
        </div>
      `;
    }


    if (alertsError) {

      return `

        ${
          pageIntro(
            "Threats <em>& Alerts</em>",
            "Current cybersecurity threat monitoring."
          )
        }

        <div class="empty">

          <h2>
            ALERT DATA UNAVAILABLE
          </h2>

          <p>
            ${escape(
              alertsError
            )}
          </p>

          <button id="retry-alerts">
            Retry
          </button>

        </div>
      `;
    }


    const criticalArticles =
      (
        criticalAlertsResponse
          ?.articles
        ||
        []
      )
        .filter(
          isArticleInCurrentWindow
        );


    const highArticles =
      (
        highAlertsResponse
          ?.articles
        ||
        []
      )
        .filter(
          isArticleInCurrentWindow
        );


    return `

      <div class="intro">

        <div>

          <div class="eyebrow">
            CYBERHEAD THREAT MONITOR
          </div>

          <h1>
            Threats
            <em>& Alerts</em>
          </h1>

          <p>

            Current Critical and High
            cybersecurity threats detected
            within the rolling 24-hour
            briefing window.

          </p>

        </div>

        <div class="clock threat-level-box">

          HIGHEST ACTIVE SEVERITY

          <span
            class="
              threat-level-badge
              ${escape(
                threatLevel
              )}
            "
          >

            ${escape(
              threatLevel
                .toUpperCase()
            )}

          </span>

          <span class="demo">
            LIVE THREAT DATA
          </span>

        </div>

      </div>


      <div class="stat-grid">

        <div class="panel">

          Critical · Last 24h

          <strong>
            ${escape(
              liveBriefing
                ?.critical_count
              ||
              0
            )}
          </strong>

        </div>


        <div class="panel">

          High · Last 24h

          <strong>
            ${escape(
              liveBriefing
                ?.high_count
              ||
              0
            )}
          </strong>

        </div>


        <div class="panel">

          Total analysed · Last 24h

          <strong>
            ${escape(
              liveBriefing
                ?.total_considered
              ||
              0
            )}
          </strong>

        </div>

      </div>


      <div class="section-label">
        URGENT CRITICAL THREATS
      </div>

      ${
        criticalArticles.length

          ? `

            <div class="grid">

              ${
                criticalArticles
                  .map(
                    alertCard
                  )
                  .join("")
              }

            </div>
          `

          : `

            <div class="empty">

              No Critical threats were
              detected in the current
              24-hour monitoring window.

            </div>
          `
      }


      <div
        class="section-label"
        style="margin-top:24px;"
      >
        HIGH-PRIORITY THREATS
      </div>

      ${
        highArticles.length

          ? `

            <div class="grid">

              ${
                highArticles
                  .map(
                    alertCard
                  )
                  .join("")
              }

            </div>
          `

          : `

            <div class="empty">

              No High-severity threats
              were detected in the current
              24-hour monitoring window.

            </div>
          `
      }
    `;
  }


  async function loadAlerts() {

    if (alertsLoading) {
      return;
    }


    alertsLoading =
      true;

    alertsError =
      null;


    if (
      page() === "alerts"
    ) {
      render();
    }


    try {

      const [
        criticalResponse,
        highResponse
      ] =
        await Promise.all([

          CyberheadAPI
            .getArticles({
              severity:
                "Critical",

              sort:
                "latest",

              limit:
                100,

              offset:
                0
            }),

          CyberheadAPI
            .getArticles({
              severity:
                "High",

              sort:
                "latest",

              limit:
                100,

              offset:
                0
            })

        ]);


      criticalAlertsResponse =
        criticalResponse;


      highAlertsResponse =
        highResponse;


    } catch (error) {

      alertsError =
        error.name === "AbortError"

          ? "The alert request timed out."

          : error.message;


    } finally {

      alertsLoading =
        false;


      if (
        page() === "alerts"
      ) {
        render();
      }
    }
  }


  /* =========================================================
     REPORTS
     ========================================================= */

  function getAvailableCategories() {

    const statsCategories =
      Object.keys(
        liveStats
          ?.category_distribution
        ||
        {}
      );


    if (
      statsCategories.length
    ) {

      return statsCategories;
    }


    return [

      "Vulnerabilities",

      "Other cybersecurity news",

      "Other malware",

      "Data breaches",

      "Phishing",

      "Ransomware",

      "DDoS"
    ];
  }


  function options(
    values,
    current
  ) {

    return values
      .map(
        (value) => `

          <option
            value="${escape(
              value
            )}"
            ${
              value === current
                ? "selected"
                : ""
            }
          >
            ${escape(value)}
          </option>
        `
      )
      .join("");
  }


  function reportsIntro() {

    const total =
      liveStats
        ?.processed_articles

      ??

      articleResponse
        ?.total

      ??

      0;


    return `

      <div class="intro">

        <div>

          <div class="eyebrow">
            CYBERHEAD THREAT DATABASE
          </div>

          <h1>
            All
            <em>Reports</em>
          </h1>

          <p>

            Browse

            ${escape(total)}

            processed cybersecurity reports.

            Search, filter and sort results
            directly from the CYBERHEAD database.

          </p>

        </div>

        <div class="clock">

          LIVE DATABASE

          <strong>
            ${escape(total)}
          </strong>

          <span>
            PROCESSED REPORTS
          </span>

        </div>

      </div>
    `;
  }


  function reportsToolbar() {

    return `

      <div class="toolbar">

        <label>

          Severity

          <select id="severity">

            ${
              options(
                [
                  "All",
                  "Critical",
                  "High",
                  "Medium",
                  "Low"
                ],
                severity
              )
            }

          </select>

        </label>


        <label>

          Category

          <select id="category">

            ${
              options(
                [
                  "All",
                  ...getAvailableCategories()
                ],
                category
              )
            }

          </select>

        </label>


        <label>

          Sort

          <select id="sort">

            <option
              value="latest"
              ${
                sort === "latest"
                  ? "selected"
                  : ""
              }
            >
              Newest first
            </option>

            <option
              value="severity"
              ${
                sort === "severity"
                  ? "selected"
                  : ""
              }
            >
              Most severe first
            </option>

          </select>

        </label>


        <button id="reset-reports">
          Reset filters
        </button>

      </div>
    `;
  }


  function reportsPagination() {

    if (!articleResponse) {
      return "";
    }


    const total =
      articleResponse.total;


    const returned =
      articleResponse.returned;


    const start =
      total === 0

        ? 0

        : articleOffset + 1;


    const end =
      Math.min(
        articleOffset
        +
        returned,
        total
      );


    const hasPrevious =
      articleOffset > 0;


    const hasNext =
      articleOffset
      +
      returned
      <
      total;


    return `

      <div
        class="toolbar"
        style="
          margin-top:20px;
          justify-content:space-between;
        "
      >

        <span>

          Showing

          ${escape(start)}

          -

          ${escape(end)}

          of

          ${escape(total)}

          reports

        </span>

        <div>

          <button
            id="previous-page"
            ${
              !hasPrevious
                ? "disabled"
                : ""
            }
          >
            ← Previous
          </button>

          <button
            id="next-page"
            ${
              !hasNext
                ? "disabled"
                : ""
            }
          >
            Next →
          </button>

        </div>

      </div>
    `;
  }


  function reportsPage() {

    if (articlesLoading) {

      return `

        ${reportsIntro()}

        ${reportsToolbar()}

        <div class="empty">
          Loading cybersecurity reports...
        </div>
      `;
    }


    if (articlesError) {

      return `

        ${reportsIntro()}

        ${reportsToolbar()}

        <div class="empty">

          <h2>
            REPORTS UNAVAILABLE
          </h2>

          <p>
            ${escape(
              articlesError
            )}
          </p>

          <button id="retry-reports">
            Retry
          </button>

        </div>
      `;
    }


    if (!articleResponse) {

      return `

        ${reportsIntro()}

        ${reportsToolbar()}

        <div class="empty">
          Loading reports...
        </div>
      `;
    }


    const articles =
      Array.isArray(
        articleResponse.articles
      )
        ? articleResponse.articles
        : [];


    return `

      ${reportsIntro()}

      ${reportsToolbar()}

      <div class="section-label">
        SEARCH RESULTS
      </div>

      ${
        articles.length

          ? `

            <div class="grid">

              ${
                articles
                  .map(
                    (article) =>
                      liveCard(
                        article
                      )
                  )
                  .join("")
              }

            </div>
          `

          : `

            <div class="empty">

              <h2>
                NO MATCHING REPORTS
              </h2>

              <p>

                Try changing the search,
                category or severity filters.

              </p>

            </div>
          `
      }

      ${reportsPagination()}
    `;
  }


  async function loadArticles() {

    if (articlesLoading) {
      return;
    }


    articlesLoading =
      true;

    articlesError =
      null;


    if (
      page() === "reports"
    ) {
      render();
    }


    try {

      articleResponse =
        await CyberheadAPI
          .getArticles({

            category:
              category === "All"
                ? ""
                : category,

            severity:
              severity === "All"
                ? ""
                : severity,

            search:
              query.trim(),

            sort,

            limit:
              ARTICLE_LIMIT,

            offset:
              articleOffset
          });


    } catch (error) {

      articlesError =
        error.name === "AbortError"

          ? "The article request timed out."

          : error.message;


    } finally {

      articlesLoading =
        false;


      if (
        page() === "reports"
      ) {
        render();
      }
    }
  }


  /* =========================================================
     SAVED STORIES
     ========================================================= */

  async function loadSavedArticles() {

    if (savedLoading) {
      return;
    }


    savedLoading =
      true;

    savedError =
      null;


    if (
      page() === "saved"
    ) {
      render();
    }


    if (!saved.length) {

      savedArticles =
        [];

      savedLoading =
        false;


      if (
        page() === "saved"
      ) {
        render();
      }

      return;
    }


    try {

      const results =
        await Promise.allSettled(

          saved.map(
            (id) =>
              CyberheadAPI
                .getArticleDetail(id)
          )
        );


      savedArticles =
        results
          .filter(
            (result) =>
              result.status ===
              "fulfilled"
          )
          .map(
            (result) =>
              result.value
          );


      const validIds =
        new Set(

          savedArticles.map(
            (article) =>
              String(
                article.id
              )
          )
        );


      const cleanedSaved =
        saved.filter(
          (id) =>
            validIds.has(
              String(id)
            )
        );


      if (
        cleanedSaved.length
        !==
        saved.length
      ) {

        saved =
          cleanedSaved;

        persistSaved();
      }


    } catch (error) {

      savedError =
        error.name === "AbortError"

          ? "The saved-story request timed out."

          : error.message;


    } finally {

      savedLoading =
        false;


      if (
        page() === "saved"
      ) {
        render();
      }
    }
  }


  function savedCount(level) {

    return savedArticles
      .filter(
        (article) =>
          article.severity === level
      )
      .length;
  }


  function savedFilterCard(
    label,
    count,
    value
  ) {

    const active =
      savedSeverityFilter
      === value;


    return `

      <button
        class="
          saved-filter-card
          ${escape(value)}
          ${
            active
              ? "active"
              : ""
          }
        "
        data-saved-filter="${escape(
          value
        )}"
      >

        <span>
          ${escape(label)}
        </span>

        <strong>
          ${escape(count)}
        </strong>

      </button>
    `;
  }


  function savedCard(article) {

    const articleId =
      liveArticleId(article);


    const published =
      article.published_at
      ||
      article.collected_at;


    return `

      <article class="card">

        ${liveArt(article)}

        <div>

          <div class="meta">

            ${liveBadges(article)}

            <time>
              ${escape(
                formatDate(
                  published
                )
              )}
            </time>

          </div>

          <h3>
            ${escape(
              article.title
            )}
          </h3>

          <p>
            ${escape(
              article.summary
              ||
              "Summary unavailable."
            )}
          </p>

          <div class="actions">

            <span
              class="
                eyebrow
                severity-score
                ${escape(
                  article.severity
                )}
              "
            >

              CYBERHEAD SEVERITY SCORE

              ${escape(
                article.severity_score
              )}/100

            </span>

            <button
              data-live-open="${escape(
                articleId
              )}"
            >
              Read report →
            </button>

          </div>

          <div class="related">

            Source:

            ${escape(
              article.source
              ||
              "Unknown"
            )}

            <br>

            <button
              class="text-button"
              data-remove-saved="${escape(
                articleId
              )}"
            >
              Remove from saved ♧
            </button>

          </div>

        </div>

      </article>
    `;
  }


  function savedPage() {

    if (savedLoading) {

      return `

        ${
          pageIntro(
            "Saved <em>Stories</em>",
            "Save important reports while browsing CYBERHEAD and return to them here."
          )
        }

        <div class="empty">
          Loading saved stories...
        </div>
      `;
    }


    if (savedError) {

      return `

        ${
          pageIntro(
            "Saved <em>Stories</em>",
            "Save important reports while browsing CYBERHEAD and return to them here."
          )
        }

        <div class="empty">

          <h2>
            SAVED STORIES UNAVAILABLE
          </h2>

          <p>
            ${escape(
              savedError
            )}
          </p>

          <button id="retry-saved">
            Retry
          </button>

        </div>
      `;
    }


    const filteredSaved =
      savedSeverityFilter === "All"

        ? savedArticles

        : savedArticles.filter(
            (article) =>
              article.severity
              ===
              savedSeverityFilter
          );


    return `

      ${
        pageIntro(
          "Saved <em>Stories</em>",
          "Save important reports while browsing CYBERHEAD and return to them here."
        )
      }


      <div class="saved-filter-grid">

        ${
          savedFilterCard(
            "Saved Reports",
            savedArticles.length,
            "All"
          )
        }

        ${
          savedFilterCard(
            "Critical",
            savedCount(
              "Critical"
            ),
            "Critical"
          )
        }

        ${
          savedFilterCard(
            "High",
            savedCount(
              "High"
            ),
            "High"
          )
        }

        ${
          savedFilterCard(
            "Medium",
            savedCount(
              "Medium"
            ),
            "Medium"
          )
        }

        ${
          savedFilterCard(
            "Low",
            savedCount(
              "Low"
            ),
            "Low"
          )
        }

      </div>


      <div class="section-label">

        ${
          savedSeverityFilter === "All"

            ? "YOUR SAVED REPORTS"

            : `SAVED ${escape(
                savedSeverityFilter
                  .toUpperCase()
              )} REPORTS`
        }

      </div>


      ${
        filteredSaved.length

          ? `

            <div class="grid">

              ${
                filteredSaved
                  .map(
                    savedCard
                  )
                  .join("")
              }

            </div>
          `

          : `

            <div class="empty">

              <h2>

                ${
                  savedArticles.length

                    ? `NO SAVED ${escape(
                        savedSeverityFilter
                          .toUpperCase()
                      )} REPORTS`

                    : "NO SAVED STORIES YET"
                }

              </h2>

              <p>

                ${
                  savedArticles.length

                    ? "Choose another severity filter or save more reports."

                    : "Open any CYBERHEAD report and select Save story ♧. It will appear here automatically."
                }

              </p>

              ${
                savedArticles.length

                  ? ""

                  : `

                    <a href="#reports">
                      Browse All Reports →
                    </a>
                  `
              }

            </div>
          `
      }
    `;
  }


  /* =========================================================
     ARTICLE DETAILS
     ========================================================= */

  async function openLiveArticle(
    articleId
  ) {

    const dialog =
      $("#report-dialog");


    const content =
      $("#report-content");


    content.innerHTML = `

      <div class="eyebrow">
        LOADING INTELLIGENCE REPORT
      </div>

      <p>
        Retrieving analysis...
      </p>
    `;


    if (!dialog.open) {
      dialog.showModal();
    }


    try {

      const article =
        await CyberheadAPI
          .getArticleDetail(
            articleId
          );


      const tags =
        Array.isArray(
          article.threat_tags
        )
          ? article.threat_tags
          : [];


      const cves =
        Array.isArray(
          article.cves
        )
          ? article.cves
          : [];


      const tagText =
        tags.length

          ? tags
              .map(
                (item) =>

                  typeof item ===
                  "string"

                    ? escape(item)

                    : escape(
                        item.tag
                        ??
                        item.name
                        ??
                        ""
                      )
              )
              .filter(Boolean)
              .join("<br>")

          : "No threat tags detected.";


      const cveText =
        cves.length

          ? cves
              .map(
                (item) => {

                  let text =
                    escape(
                      item.cve_id
                      ||
                      "Unknown CVE"
                    );


                  if (
                    item.max_cvss !== null
                    &&
                    item.max_cvss !== undefined
                  ) {

                    text +=
                      ` · CVSS ${escape(
                        item.max_cvss
                      )}`;
                  }


                  if (
                    item.cisa_kev
                      ?.listed
                  ) {

                    text +=
                      " · CISA KEV";
                  }


                  return text;
                }
              )
              .join("<br>")

          : "No CVEs detected.";


      content.innerHTML = `

        <div class="eyebrow">
          CYBERHEAD INTELLIGENCE REPORT
        </div>

        <h2>
          ${escape(
            article.title
          )}
        </h2>

        <div class="meta">
          ${liveBadges(article)}
        </div>


        <div class="detail-grid">

          <div class="panel">

            CYBERHEAD Severity Score

            <strong
              class="
                severity-score-value
                ${escape(
                  article.severity
                )}
              "
            >
              ${escape(
                article.severity_score
              )}/100
            </strong>

          </div>


          <div class="panel">

            Category

            <strong>
              ${escape(
                article.category
                ||
                "Unknown"
              )}
            </strong>

          </div>


          <div class="panel">

            CVEs Detected

            <strong>
              ${escape(
                cves.length
              )}
            </strong>

          </div>

        </div>


        <h3>
          Summary
        </h3>

        <p>
          ${escape(
            article.summary
            ||
            "Summary unavailable."
          )}
        </p>


        <h3>
          Why it matters
        </h3>

        <p>
          ${escape(
            article.why_it_matters
            ||
            "No explanation available."
          )}
        </p>


        <h3>
          Defensive recommendations
        </h3>

        <p>
          ${withBreaks(
            article.recommendations
            ||
            "No recommendations available."
          )}
        </p>


        <h3>
          Severity evidence
        </h3>

        <p>
          ${withBreaks(
            article.severity_reason
            ||
            "No severity evidence available."
          )}
        </p>


        <h3>
          Threat indicators
        </h3>

        <p>
          ${tagText}
        </p>


        <h3>
          CVE intelligence
        </h3>

        <p>
          ${cveText}
        </p>


        <h3>
          Source
        </h3>

        <p>
          ${escape(
            article.source
            ||
            "Unknown"
          )}
        </p>


        ${
          article.url

            ? `

              <p>

                ${
                  safeLink(
                    article.url,
                    "Open original article"
                  )
                }

              </p>
            `

            : ""
        }


        <p>

          <time>

            Published

            ${escape(
              formatDate(
                article.published_at
                ||
                article.collected_at
              )
            )}

          </time>

        </p>


        <button
          data-save-live="${escape(
            String(
              article.id
            )
          )}"
        >

          ${
            saved.includes(
              String(
                article.id
              )
            )

              ? "Remove from saved"

              : "Save story ♧"
          }

        </button>
      `;


    } catch (error) {

      content.innerHTML = `

        <div class="eyebrow">
          REPORT ERROR
        </div>

        <h2>
          Unable to load article
        </h2>

        <p>
          ${escape(
            error.message
          )}
        </p>
      `;
    }
  }


  /* =========================================================
     SAFE LINKS
     ========================================================= */

  function safeLink(
    url,
    label
  ) {

    try {

      const parsed =
        new URL(url);


      if (
        [
          "https:",
          "http:"
        ].includes(
          parsed.protocol
        )
      ) {

        return `

          <a
            href="${escape(
              parsed.href
            )}"
            target="_blank"
            rel="noopener noreferrer"
          >

            ${escape(label)}
            ↗

          </a>
        `;
      }

    } catch {

      // Invalid URL.
    }


    return `

      <span>

        ${escape(label)}
        — source unavailable

      </span>
    `;
  }


  /* =========================================================
     ANALYSIS
     ========================================================= */

  function analysisSeverityCard(
    level,
    count
  ) {

    return `

      <button
        class="
          analysis-stat-card
          severity-analysis
          ${escape(level)}
        "
        data-analysis-severity="${escape(
          level
        )}"
      >

        <span>
          ${escape(level)}
        </span>

        <strong>
          ${escape(
            count ?? 0
          )}
        </strong>

        <small>
          VIEW REPORTS →
        </small>

      </button>
    `;
  }


  function analysisCategoryRow(
    name,
    count,
    maximum
  ) {

    const percentage =
      maximum > 0

        ? (
            Number(count)
            /
            Number(maximum)
            *
            100
          )

        : 0;


    return `

      <button
        class="analysis-category-row"
        data-analysis-category="${escape(
          name
        )}"
      >

        <span class="analysis-category-name">
          ${escape(name)}
        </span>


        <span class="analysis-category-bar">

          <span
            style="
              width:${Math.max(
                3,
                percentage
              )}%;
            "
          ></span>

        </span>


        <strong>
          ${escape(count)}
        </strong>


        <span class="analysis-arrow">
          →
        </span>

      </button>
    `;
  }


  function analysis() {

    if (!liveStats) {

      return `

        ${
          pageIntro(
            "Threat <em>Analysis</em>",
            "Loading live CYBERHEAD threat intelligence statistics."
          )
        }

        <div class="empty">
          Loading analysis...
        </div>
      `;
    }


    const severityData =
      liveStats
        .severity_distribution
      ||
      {};


    const categoryData =
      liveStats
        .category_distribution
      ||
      {};


    const last24 =
      liveStats
        .last_24_hours
      ||
      {};


    const last24Severity =
      last24.severity
      ||
      {};


    const processed =
      Number(
        liveStats
          .processed_articles
        ||
        0
      );


    const totalCollected =
      Number(
        liveStats
          .total_articles
        ||
        0
      );


    const categoryEntries =
      Object.entries(
        categoryData
      )
        .sort(
          (
            first,
            second
          ) =>
            Number(
              second[1]
            )
            -
            Number(
              first[1]
            )
        );


    const maximumCategory =
      categoryEntries.length

        ? Math.max(
            ...categoryEntries.map(
              ([
                ,
                count
              ]) =>
                Number(count)
            )
          )

        : 0;


    let highestSeverity =
      "Low";


    if (
      Number(
        last24Severity.Critical
        ||
        0
      )
      >
      0
    ) {

      highestSeverity =
        "Critical";

    } else if (
      Number(
        last24Severity.High
        ||
        0
      )
      >
      0
    ) {

      highestSeverity =
        "High";

    } else if (
      Number(
        last24Severity.Medium
        ||
        0
      )
      >
      0
    ) {

      highestSeverity =
        "Medium";
    }


    return `

      <div class="intro">

        <div>

          <div class="eyebrow">
            CYBERHEAD ANALYTICS
          </div>

          <h1>
            Threat
            <em>Analysis</em>
          </h1>

          <p>

            Live analysis of processed
            cybersecurity reports,
            severity levels and threat
            categories.

          </p>

        </div>


        <div class="clock analysis-threat-box">

          HIGHEST ACTIVE SEVERITY

          <span
            class="
              threat-level-badge
              ${escape(
                highestSeverity
              )}
            "
          >

            ${escape(
              highestSeverity
                .toUpperCase()
            )}

          </span>

          <span class="demo">
            ROLLING 24 HOURS
          </span>

        </div>

      </div>


      <div class="analysis-overview-grid">

        <div class="panel analysis-overview-card">

          <span>
            PROCESSED REPORTS
          </span>

          <strong>
            ${escape(
              processed
            )}
          </strong>

          <small>
            Fully analysed by CYBERHEAD
          </small>

        </div>


        <div class="panel analysis-overview-card">

          <span>
            ARTICLES COLLECTED
          </span>

          <strong>
            ${escape(
              totalCollected
            )}
          </strong>

          <small>
            Stored in the intelligence database
          </small>

        </div>


        <div class="panel analysis-overview-card">

          <span>
            LAST 24 HOURS
          </span>

          <strong>
            ${escape(
              last24
                .articles_considered
              ||
              0
            )}
          </strong>

          <small>
            Analysed in current briefing window
          </small>

        </div>

      </div>


      <div class="section-label">
        LAST 24 HOURS
      </div>


      <section class="panel analysis-section">

        <div class="analysis-section-heading">

          <div>

            <div class="eyebrow">
              CURRENT THREAT WINDOW
            </div>

            <h2>
              24-HOUR SEVERITY OVERVIEW
            </h2>

          </div>


          <span class="analysis-window-time">

            ${
              last24.last_updated

                ? `Updated ${escape(
                    formatDateTime(
                      last24.last_updated
                    )
                  )}`

                : "Waiting for briefing data"
            }

          </span>

        </div>


        <div class="analysis-severity-grid">

          ${
            analysisSeverityCard(
              "Critical",
              last24Severity.Critical
              ||
              0
            )
          }

          ${
            analysisSeverityCard(
              "High",
              last24Severity.High
              ||
              0
            )
          }

          ${
            analysisSeverityCard(
              "Medium",
              last24Severity.Medium
              ||
              0
            )
          }

          ${
            analysisSeverityCard(
              "Low",
              last24Severity.Low
              ||
              0
            )
          }

        </div>


        <p class="analysis-help">

          Select a severity level to
          open matching reports in the
          CYBERHEAD threat database.

        </p>

      </section>


      <div class="section-label">
        DATABASE SEVERITY DISTRIBUTION
      </div>


      <section class="panel analysis-section">

        <div class="analysis-section-heading">

          <div>

            <div class="eyebrow">
              ALL PROCESSED REPORTS
            </div>

            <h2>
              REPORTS BY SEVERITY
            </h2>

          </div>


          <strong class="analysis-total">

            ${escape(
              processed
            )}

            TOTAL

          </strong>

        </div>


        <div class="analysis-severity-grid">

          ${
            analysisSeverityCard(
              "Critical",
              severityData.Critical
              ||
              0
            )
          }

          ${
            analysisSeverityCard(
              "High",
              severityData.High
              ||
              0
            )
          }

          ${
            analysisSeverityCard(
              "Medium",
              severityData.Medium
              ||
              0
            )
          }

          ${
            analysisSeverityCard(
              "Low",
              severityData.Low
              ||
              0
            )
          }

        </div>

      </section>


      <div class="section-label">
        CATEGORY DISTRIBUTION
      </div>


      <section class="panel analysis-section">

        <div class="analysis-section-heading">

          <div>

            <div class="eyebrow">
              MACHINE LEARNING CLASSIFICATION
            </div>

            <h2>
              REPORTS BY CYBERSECURITY CATEGORY
            </h2>

          </div>

        </div>


        <div class="analysis-category-list">

          ${
            categoryEntries.length

              ? categoryEntries
                  .map(
                    ([
                      name,
                      count
                    ]) =>
                      analysisCategoryRow(
                        name,
                        count,
                        maximumCategory
                      )
                  )
                  .join("")

              : `

                <div class="empty">

                  No category statistics
                  are currently available.

                </div>
              `
          }

        </div>


        <p class="analysis-help">

          Categories are assigned by the
          CYBERHEAD machine-learning
          classification model.

          Select a category to view
          matching reports.

        </p>

      </section>


      <div class="section-label">
        ABOUT THE ANALYSIS
      </div>


      <section class="panel analysis-explanation">

        <div>

          <h3>
            CATEGORY CLASSIFICATION
          </h3>

          <p>

            CYBERHEAD uses the trained
            machine-learning classifier
            to assign each processed
            article to a cybersecurity
            category.

          </p>

        </div>


        <div>

          <h3>
            SEVERITY ANALYSIS
          </h3>

          <p>

            Severity is calculated using
            the CYBERHEAD hybrid
            evidence-based severity engine
            and represented using Low,
            Medium, High and Critical.

          </p>

        </div>


        <div>

          <h3>
            24-HOUR WINDOW
          </h3>

          <p>

            Current threat statistics use
            the same rolling 24-hour window
            as the CYBERHEAD Daily Briefing.

          </p>

        </div>

      </section>
    `;
  }


  /* =========================================================
     SOURCES
     ========================================================= */

  function sourceStatusLabel(
    source
  ) {

    if (!source.enabled) {

      return `

        <span
          class="
            source-status
            Disabled
          "
        >
          ● DISABLED
        </span>
      `;
    }


    if (
      source
        .last_check_status
      ===
      "failed"
    ) {

      return `

        <span
          class="
            source-status
            Failed
          "
        >
          ● COLLECTION ERROR
        </span>
      `;
    }


    return `

      <span
        class="
          source-status
          Active
        "
      >
        ● ACTIVE
      </span>
    `;
  }


  function sourceCard(source) {

    const toggleBusy =
      String(
        sourceToggleLoadingId
      )
      ===
      String(
        source.id
      );


    return `

      <article
        class="
          panel
          source-card
          ${
            source.enabled
              ? ""
              : "source-disabled"
          }
        "
      >

        <div class="source-card-header">

          <div>

            <div class="eyebrow">
              INTELLIGENCE FEED
            </div>

            <h2>
              ${escape(
                source.name
              )}
            </h2>

          </div>

          ${
            sourceStatusLabel(
              source
            )
          }

        </div>


        <div class="source-url">

          ${
            safeLink(
              source.url,
              source.url
            )
          }

        </div>


        <div class="source-metrics">

          <div>

            <span>
              ARTICLES COLLECTED
            </span>

            <strong>
              ${escape(
                source.article_count
                ??
                0
              )}
            </strong>

          </div>


          <div>

            <span>
              LATEST ARTICLE
            </span>

            <strong>

              ${escape(
                source.latest_article_at

                  ? formatDate(
                      source.latest_article_at
                    )

                  : "None yet"
              )}

            </strong>

          </div>


          <div>

            <span>
              LAST CHECKED
            </span>

            <strong>

              ${escape(
                source.last_checked_at

                  ? formatDateTime(
                      source.last_checked_at
                    )

                  : "Not checked yet"
              )}

            </strong>

          </div>


          <div>

            <span>
              COLLECTOR STATUS
            </span>

            <strong>

              ${escape(
                source.last_check_status

                  ? source
                      .last_check_status
                      .toUpperCase()

                  : "NOT CHECKED"
              )}

            </strong>

          </div>

        </div>


        ${
          source.last_check_error

            ? `

              <div class="source-error">

                ${escape(
                  source.last_check_error
                )}

              </div>
            `

            : ""
        }


        <div class="source-actions">

          ${
            safeLink(
              source.url,
              "Open feed"
            )
          }


          <button
            data-toggle-source="${escape(
              source.id
            )}"
            data-next-enabled="${
              source.enabled
                ? "false"
                : "true"
            }"
            ${
              toggleBusy
                ? "disabled"
                : ""
            }
          >

            ${
              toggleBusy

                ? "Updating..."

                : source.enabled

                  ? "Disable source"

                  : "Enable source"
            }

          </button>

        </div>

      </article>
    `;
  }


  function sourcesPage() {

    if (sourcesLoading) {

      return `

        ${
          pageIntro(
            "Intelligence <em>Sources</em>",
            "Manage the RSS and Atom feeds used by CYBERHEAD."
          )
        }

        <div class="empty">
          Loading intelligence sources...
        </div>
      `;
    }


    if (sourcesError) {

      return `

        ${
          pageIntro(
            "Intelligence <em>Sources</em>",
            "Manage the RSS and Atom feeds used by CYBERHEAD."
          )
        }

        <div class="empty">

          <h2>
            SOURCES UNAVAILABLE
          </h2>

          <p>
            ${escape(
              sourcesError
            )}
          </p>

          <button id="retry-sources">
            Retry
          </button>

        </div>
      `;
    }


    if (!sourcesResponse) {

      return `

        ${
          pageIntro(
            "Intelligence <em>Sources</em>",
            "Manage the RSS and Atom feeds used by CYBERHEAD."
          )
        }

        <div class="empty">
          Loading intelligence sources...
        </div>
      `;
    }


    const sourceList =
      Array.isArray(
        sourcesResponse.sources
      )
        ? sourcesResponse.sources
        : [];


    const totalArticles =
      sourceList.reduce(
        (
          total,
          source
        ) =>
          total
          +
          Number(
            source.article_count
            ||
            0
          ),

        0
      );


    const disabledCount =
      Math.max(
        0,

        Number(
          sourcesResponse.count
          ||
          0
        )
        -
        Number(
          sourcesResponse.active_count
          ||
          0
        )
      );


    return `

      ${
        pageIntro(
          "Intelligence <em>Sources</em>",
          "Manage the RSS and Atom feeds used by the CYBERHEAD collector."
        )
      }


      <div class="stat-grid source-stat-grid">

        <div class="panel">

          Active sources

          <strong>
            ${escape(
              sourcesResponse
                .active_count
              ??
              0
            )}
          </strong>

        </div>


        <div class="panel">

          Total sources

          <strong>
            ${escape(
              sourcesResponse.count
              ??
              sourceList.length
            )}
          </strong>

        </div>


        <div class="panel">

          Articles collected

          <strong>
            ${escape(
              totalArticles
            )}
          </strong>

        </div>

      </div>


      <section
        class="
          panel
          source-management-panel
        "
      >

        <div class="source-management-heading">

          <div>

            <div class="eyebrow">
              SOURCE MANAGEMENT
            </div>

            <h2>
              + ADD INTELLIGENCE SOURCE
            </h2>

            <p>

              Add a public RSS or Atom feed.
              CYBERHEAD validates the feed
              before saving it.

            </p>

          </div>


          <span class="source-disabled-count">

            ${escape(
              disabledCount
            )}

            disabled

          </span>

        </div>


        <form
          id="source-form"
          class="source-form"
        >

          <label>

            Source name

            <input
              id="source-name"
              type="text"
              maxlength="100"
              required
              placeholder="Example: Security Blog"
              value="${escape(
                sourceDraftName
              )}"
            >

          </label>


          <label>

            RSS / Atom feed URL

            <input
              id="source-url"
              type="url"
              maxlength="2048"
              required
              placeholder="https://example.com/feed/"
              value="${escape(
                sourceDraftUrl
              )}"
            >

          </label>


          <div class="source-form-actions">

            <button
              id="test-source"
              type="button"
              ${
                sourceTestLoading
                ||
                sourceAddLoading

                  ? "disabled"

                  : ""
              }
            >

              ${
                sourceTestLoading

                  ? "Testing..."

                  : "Test feed"
              }

            </button>


            <button
              type="submit"
              ${
                sourceAddLoading
                ||
                sourceTestLoading

                  ? "disabled"

                  : ""
              }
            >

              ${
                sourceAddLoading

                  ? "Adding..."

                  : "Add source"
              }

            </button>

          </div>

        </form>


        ${
          sourceMessage

            ? `

              <div
                class="
                  source-feedback
                  ${escape(
                    sourceMessageType
                  )}
                "
              >

                ${escape(
                  sourceMessage
                )}

              </div>
            `

            : ""
        }


        ${
          sourceTestResult

            ? `

              <div class="source-test-result">

                <strong>
                  ✓ VALID FEED
                </strong>

                <span>

                  Title:

                  ${escape(
                    sourceTestResult
                      .feed_title
                    ||
                    "Not supplied"
                  )}

                </span>

                <span>

                  Format:

                  ${escape(
                    sourceTestResult
                      .feed_type
                    ||
                    "RSS / Atom"
                  )}

                </span>

                <span>

                  Entries detected:

                  ${escape(
                    sourceTestResult
                      .entry_count
                    ??
                    0
                  )}

                </span>

              </div>
            `

            : ""
        }

      </section>


      <div class="section-label">
        CONFIGURED INTELLIGENCE SOURCES
      </div>


      ${
        sourceList.length

          ? `

            <div class="source-card-grid">

              ${
                sourceList
                  .map(
                    sourceCard
                  )
                  .join("")
              }

            </div>
          `

          : `

            <div class="empty">

              No intelligence sources
              have been configured.

            </div>
          `
      }


      <div class="notice source-note">

        Enabled sources are used by the
        normal CYBERHEAD collection pipeline.

        A newly added source will be included
        automatically on the next scheduled
        collection run.

      </div>
    `;
  }


  async function loadSources() {

    if (sourcesLoading) {
      return;
    }


    sourcesLoading =
      true;

    sourcesError =
      null;


    if (
      page() === "sources"
    ) {
      render();
    }


    try {

      sourcesResponse =
        await CyberheadAPI
          .getSources();


    } catch (error) {

      sourcesError =
        error.name === "AbortError"

          ? "The source request timed out."

          : error.message;


    } finally {

      sourcesLoading =
        false;


      if (
        page() === "sources"
      ) {
        render();
      }
    }
  }


  async function testSourceFeed() {

    sourceDraftName =
      $("#source-name")
        ?.value
      ??
      sourceDraftName;


    sourceDraftUrl =
      $("#source-url")
        ?.value
      ??
      sourceDraftUrl;


    const url =
      sourceDraftUrl.trim();


    sourceMessage =
      "";

    sourceTestResult =
      null;


    if (!url) {

      sourceMessageType =
        "error";


      sourceMessage =
        "Enter an RSS or Atom feed URL first.";


      render();

      return;
    }


    sourceTestLoading =
      true;


    render();


    try {

      sourceTestResult =
        await CyberheadAPI
          .testSource(
            url
          );


      sourceMessageType =
        "success";


      sourceMessage =
        "Feed validation succeeded.";


    } catch (error) {

      sourceMessageType =
        "error";


      sourceMessage =
        error.name === "AbortError"

          ? "Feed validation timed out."

          : error.message;


    } finally {

      sourceTestLoading =
        false;


      if (
        page() === "sources"
      ) {
        render();
      }
    }
  }


  async function addSourceFromForm() {

    sourceDraftName =
      $("#source-name")
        ?.value
      ??
      sourceDraftName;


    sourceDraftUrl =
      $("#source-url")
        ?.value
      ??
      sourceDraftUrl;


    const name =
      sourceDraftName.trim();


    const url =
      sourceDraftUrl.trim();


    sourceMessage =
      "";


    if (
      !name
      ||
      !url
    ) {

      sourceMessageType =
        "error";


      sourceMessage =
        "Enter both a source name and feed URL.";


      render();

      return;
    }


    sourceAddLoading =
      true;


    render();


    try {

      const result =
        await CyberheadAPI
          .addSource(
            name,
            url
          );


      sourceMessageType =
        "success";


      sourceMessage =
        `${
          result
            ?.source
            ?.name
          ||
          name
        } was added successfully.`;


      sourceDraftName =
        "";


      sourceDraftUrl =
        "";


      sourceTestResult =
        null;


      sourcesResponse =
        await CyberheadAPI
          .getSources();


    } catch (error) {

      sourceMessageType =
        "error";


      sourceMessage =
        error.name === "AbortError"

          ? "Adding the source timed out."

          : error.message;


    } finally {

      sourceAddLoading =
        false;


      if (
        page() === "sources"
      ) {
        render();
      }
    }
  }


  async function toggleSource(
    sourceId,
    enabled
  ) {

    sourceToggleLoadingId =
      String(
        sourceId
      );


    sourceMessage =
      "";


    render();


    try {

      const result =
        await CyberheadAPI
          .setSourceEnabled(
            sourceId,
            enabled
          );


      sourceMessageType =
        "success";


      sourceMessage =
        `${
          result
            ?.source
            ?.name
          ||
          "Source"
        } ${
          enabled
            ? "enabled"
            : "disabled"
        }.`;


      sourcesResponse =
        await CyberheadAPI
          .getSources();


    } catch (error) {

      sourceMessageType =
        "error";


      sourceMessage =
        error.name === "AbortError"

          ? "Updating the source timed out."

          : error.message;


    } finally {

      sourceToggleLoadingId =
        null;


      if (
        page() === "sources"
      ) {
        render();
      }
    }
  }


  /* =========================================================
     ABOUT
     ========================================================= */

function about() {

  const processedReports =
    liveStats
      ?.processed_articles
    ??
    0;


  const collectedArticles =
    liveStats
      ?.total_articles
    ??
    0;


  const last24 =
    liveStats
      ?.last_24_hours
      ?.articles_considered
    ??
    0;


  return `

    ${
      pageIntro(
        "About <em>CYBERHEAD</em>",
        "An automated cybersecurity news intelligence and threat-analysis platform."
      )
    }


    <!-- ===================================================
         PROJECT OVERVIEW
         =================================================== -->

    <div class="section-label">
      PROJECT OVERVIEW
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        WHAT IS CYBERHEAD?
      </div>

      <h2>
        CYBERSECURITY NEWS INTELLIGENCE
      </h2>


      <p>

        CYBERHEAD News is a cybersecurity
        intelligence platform designed to
        automatically collect, process,
        classify and analyse cybersecurity
        news from multiple online sources.

      </p>


      <p>

        Instead of requiring an analyst to
        manually check several cybersecurity
        websites, CYBERHEAD gathers the
        articles automatically and transforms
        them into structured intelligence
        reports.

      </p>


      <p>

        The system combines machine learning,
        cybersecurity intelligence enrichment,
        evidence-based severity analysis,
        natural language processing and
        automated news collection in one
        platform.

      </p>

    </section>


    <!-- ===================================================
         LIVE SYSTEM STATUS
         =================================================== -->

    <div class="section-label">
      CURRENT CYBERHEAD DATABASE
    </div>


    <div class="analysis-overview-grid">

      <div class="panel analysis-overview-card">

        <span>
          ARTICLES COLLECTED
        </span>

        <strong>
          ${escape(
            collectedArticles
          )}
        </strong>

        <small>
          Stored cybersecurity articles
        </small>

      </div>


      <div class="panel analysis-overview-card">

        <span>
          PROCESSED REPORTS
        </span>

        <strong>
          ${escape(
            processedReports
          )}
        </strong>

        <small>
          Fully analysed intelligence reports
        </small>

      </div>


      <div class="panel analysis-overview-card">

        <span>
          LAST 24 HOURS
        </span>

        <strong>
          ${escape(
            last24
          )}
        </strong>

        <small>
          Articles analysed in the current briefing window
        </small>

      </div>

    </div>


    <!-- ===================================================
         HOW THE SYSTEM WORKS
         =================================================== -->

    <div class="section-label">
      HOW CYBERHEAD WORKS
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        AUTOMATED INTELLIGENCE PIPELINE
      </div>

      <h2>
        FROM NEWS ARTICLE TO THREAT REPORT
      </h2>


      <p>

        CYBERHEAD processes cybersecurity
        information through a multi-stage
        automated pipeline.

      </p>


      <div class="about-pipeline">

        <div>
          <strong>01</strong>
          <span>RSS / ATOM SOURCES</span>
          <p>
            Cybersecurity articles are collected
            from enabled intelligence sources.
          </p>
        </div>


        <div>
          <strong>02</strong>
          <span>ARTICLE EXTRACTION</span>
          <p>
            Full article content is extracted
            from the collected web pages.
          </p>
        </div>


        <div>
          <strong>03</strong>
          <span>CVE EXTRACTION</span>
          <p>
            CVE identifiers mentioned in
            articles are automatically detected.
          </p>
        </div>


        <div>
          <strong>04</strong>
          <span>ML CLASSIFICATION</span>
          <p>
            The trained machine-learning model
            assigns each article to a
            cybersecurity category.
          </p>
        </div>


        <div>
          <strong>05</strong>
          <span>THREAT INTELLIGENCE</span>
          <p>
            CVE information is enriched using
            NVD and CISA Known Exploited
            Vulnerabilities data.
          </p>
        </div>


        <div>
          <strong>06</strong>
          <span>THREAT TAGGING</span>
          <p>
            Evidence is analysed for indicators
            such as ransomware, exploitation
            and zero-day activity.
          </p>
        </div>


        <div>
          <strong>07</strong>
          <span>SEVERITY ANALYSIS</span>
          <p>
            The CYBERHEAD severity engine
            calculates an explainable threat
            score.
          </p>
        </div>


        <div>
          <strong>08</strong>
          <span>NLP SUMMARY</span>
          <p>
            Important sentences are selected
            to create a concise article summary.
          </p>
        </div>


        <div>
          <strong>09</strong>
          <span>DAILY BRIEFING</span>
          <p>
            Priority threats from the rolling
            previous 24 hours are assembled
            into the Daily Briefing.
          </p>
        </div>


        <div>
          <strong>10</strong>
          <span>CYBERHEAD DASHBOARD</span>
          <p>
            The processed intelligence is
            delivered through the FastAPI
            backend to this interface.
          </p>
        </div>

      </div>

    </section>


    <!-- ===================================================
         MACHINE LEARNING
         =================================================== -->

    <div class="section-label">
      MACHINE LEARNING
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        ARTICLE CLASSIFICATION
      </div>

      <h2>
        CYBERSECURITY CATEGORY CLASSIFIER
      </h2>


      <p>

        CYBERHEAD uses a trained machine-learning
        classifier to identify the main
        cybersecurity category of each processed
        article.

      </p>


      <p>

        The model analyses article text using
        TF-IDF features and a Linear Support
        Vector Machine classifier.

      </p>


      <p>

        The categories currently used by
        CYBERHEAD are:

      </p>


      <div class="about-category-grid">

        <span>Vulnerabilities</span>

        <span>Data Breaches</span>

        <span>Ransomware</span>

        <span>Phishing</span>

        <span>DDoS</span>

        <span>Other Malware</span>

        <span>Other Cybersecurity News</span>

      </div>


      <p>

        The classification result is used
        throughout the dashboard for browsing,
        filtering, Daily Briefing statistics
        and threat analysis.

      </p>

    </section>


    <!-- ===================================================
         SEVERITY ENGINE
         =================================================== -->

    <div class="section-label">
      THREAT SEVERITY
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        EXPLAINABLE THREAT PRIORITISATION
      </div>

      <h2>
        CYBERHEAD SEVERITY SCORE
      </h2>


      <p>

        CYBERHEAD assigns each analysed
        report an internal severity score
        from 0 to 100.

      </p>


      <p>

        Severity considers multiple threat
        indicators, including:

      </p>


      <div class="about-feature-grid">

        <div class="panel">
          CVSS information
        </div>

        <div class="panel">
          Active exploitation
        </div>

        <div class="panel">
          Zero-day status
        </div>

        <div class="panel">
          Ransomware involvement
        </div>

        <div class="panel">
          Data theft
        </div>

        <div class="panel">
          Critical infrastructure impact
        </div>

        <div class="panel">
          Number of affected systems
        </div>

        <div class="panel">
          Threat recency
        </div>

        <div class="panel">
          Malware sophistication
        </div>

      </div>


      <div class="analysis-severity-grid">

        <div class="analysis-stat-card Critical">

          <span>
            CRITICAL
          </span>

          <strong>
            70–100
          </strong>

        </div>


        <div class="analysis-stat-card High">

          <span>
            HIGH
          </span>

          <strong>
            40–69
          </strong>

        </div>


        <div class="analysis-stat-card Medium">

          <span>
            MEDIUM
          </span>

          <strong>
            20–39
          </strong>

        </div>


        <div class="analysis-stat-card Low">

          <span>
            LOW
          </span>

          <strong>
            0–19
          </strong>

        </div>

      </div>


      <div class="notice">

        The CYBERHEAD Severity Score is an
        internal threat-prioritisation score.

        It does not replace the official
        CVSS vulnerability score.

      </div>

    </section>


    <!-- ===================================================
         NLP
         =================================================== -->

    <div class="section-label">
      NATURAL LANGUAGE PROCESSING
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        AUTOMATIC SUMMARISATION
      </div>

      <h2>
        EXTRACTIVE NLP SUMMARY
      </h2>


      <p>

        CYBERHEAD uses lightweight
        extractive natural language
        processing to summarise articles.

      </p>


      <p>

        The summariser ranks sentences using
        TF-IDF-based relevance and selects
        important original sentences from
        the article.

      </p>


      <p>

        This means the current summarisation
        component does not generate completely
        new sentences using a large language
        model. It selects relevant content
        directly from the collected article.

      </p>


      <p>

        The

        <strong>
          Why it matters
        </strong>

        and

        <strong>
          Defensive recommendations
        </strong>

        sections are generated separately
        using structured cybersecurity
        evidence and defensive rules.

      </p>

    </section>


    <!-- ===================================================
         THREAT INTELLIGENCE
         =================================================== -->

    <div class="section-label">
      EXTERNAL THREAT INTELLIGENCE
    </div>


    <section class="analysis-explanation panel">

      <div>

        <h3>
          NVD
        </h3>

        <p>

          CVEs detected in articles can be
          enriched using information from
          the National Vulnerability Database,
          including vulnerability details
          and CVSS information.

        </p>

      </div>


      <div>

        <h3>
          CISA KEV
        </h3>

        <p>

          CYBERHEAD checks whether detected
          vulnerabilities appear in the
          CISA Known Exploited Vulnerabilities
          catalogue.

        </p>

      </div>


      <div>

        <h3>
          SOURCE PROVENANCE
        </h3>

        <p>

          Reports retain their original
          source and article link so analysts
          can trace intelligence back to
          the collected publication.

        </p>

      </div>

    </section>


    <!-- ===================================================
         SOURCE MANAGEMENT
         =================================================== -->

    <div class="section-label">
      INTELLIGENCE SOURCES
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        DYNAMIC RSS / ATOM MANAGEMENT
      </div>

      <h2>
        CONFIGURABLE NEWS COLLECTION
      </h2>


      <p>

        Intelligence sources are stored in
        the CYBERHEAD database rather than
        being permanently fixed in the
        collector code.

      </p>


      <p>

        Through the Sources page, an
        administrator can:

      </p>


      <div class="about-feature-grid">

        <div class="panel">
          View configured sources
        </div>

        <div class="panel">
          Test RSS / Atom feeds
        </div>

        <div class="panel">
          Add new feeds
        </div>

        <div class="panel">
          Enable sources
        </div>

        <div class="panel">
          Disable sources
        </div>

        <div class="panel">
          View collector status
        </div>

      </div>


      <p>

        Enabled feeds are automatically
        included the next time the normal
        CYBERHEAD collection pipeline runs.

      </p>


      <p>

        Feed URLs are validated before
        being accepted, and duplicate
        sources are rejected.

      </p>

    </section>


    <!-- ===================================================
         AUTOMATION
         =================================================== -->

    <div class="section-label">
      AUTOMATION
    </div>


    <section class="panel prose">

      <div class="eyebrow">
        AUTOMATED INTELLIGENCE PIPELINE
      </div>

      <h2>
        SCHEDULED OR MANUAL OPERATION
      </h2>


      <p>

        CYBERHEAD can process new cybersecurity
        articles automatically through its
        complete intelligence pipeline.

      </p>


      <p>

        This installation is currently
        configured to run the CYBERHEAD
        pipeline automatically every six
        hours using Windows Task Scheduler.

      </p>


      <p>

        During each scheduled run,
        enabled intelligence sources are
        checked for new articles.

        New content can then pass through
        extraction, machine-learning
        classification, CVE detection,
        NVD and CISA enrichment,
        threat tagging, severity analysis,
        summarisation and Daily Briefing
        generation.

      </p>


      <p>

        CYBERHEAD does not depend on a
        central online server for this
        automation.

        Each installation can run its own
        local pipeline and maintain its
        own intelligence database.

      </p>


      <p>

        Users installing CYBERHEAD on
        another computer can run the
        pipeline manually or configure
        their own operating-system
        scheduler for automatic updates.

      </p>

    </section>


    <!-- ===================================================
         DASHBOARD
         =================================================== -->

    <div class="section-label">
      DASHBOARD FEATURES
    </div>


    <section class="panel prose">

      <div class="about-feature-grid">

        <div class="panel">

          <h3>
            DAILY BRIEFING
          </h3>

          <p>
            Priority cybersecurity threats
            from the rolling previous
            24 hours.
          </p>

        </div>


        <div class="panel">

          <h3>
            THREATS & ALERTS
          </h3>

          <p>
            Current Critical and High
            threats requiring attention.
          </p>

        </div>


        <div class="panel">

          <h3>
            ALL REPORTS
          </h3>

          <p>
            Search, filter and browse the
            processed intelligence database.
          </p>

        </div>


        <div class="panel">

          <h3>
            SAVED STORIES
          </h3>

          <p>
            Store important reports in the
            current browser for later review.
          </p>

        </div>


        <div class="panel">

          <h3>
            ANALYSIS
          </h3>

          <p>
            Explore severity and category
            statistics with interactive
            report filtering.
          </p>

        </div>


        <div class="panel">

          <h3>
            SOURCES
          </h3>

          <p>
            Manage the RSS and Atom feeds
            used by the collector.
          </p>

        </div>

      </div>

    </section>

    <div class="notice">

      CYBERHEAD NEWS · AI FOR CYBERSECURITY PROJECT

      <br>

      THREATS MOVE FAST.
      STAY ONE STEP AHEAD.

    </div>

  `;
}


  /* =========================================================
     RENDER
     ========================================================= */

  function render() {

    const current =
      page();


    $("#nav").innerHTML =
      routes
        .map(
          ([
            id,
            icon,
            label
          ]) => `

            <a
              href="#${id}"
              class="${
                id === current
                  ? "active"
                  : ""
              }"
              ${
                id === current
                  ? 'aria-current="page"'
                  : ""
              }
            >

              <span
                class="nav-icon"
                aria-hidden="true"
              >
                ${icon}
              </span>

              ${label}

            </a>
          `
        )
        .join("");


    const route =
      routes.find(
        (item) =>
          item[0] === current
      );


    document.title =
      `${
        route
          ? route[2]
          : "CYBERHEAD"
      } — CYBERHEAD`;


    if (
      current === "briefing"
    ) {

      $("#content").innerHTML =
        briefing();


    } else if (
      current === "alerts"
    ) {

      $("#content").innerHTML =
        alertsPage();


    } else if (
      current === "reports"
    ) {

      $("#content").innerHTML =
        reportsPage();


    } else if (
      current === "saved"
    ) {

      $("#content").innerHTML =
        savedPage();


    } else if (
      current === "analysis"
    ) {

      $("#content").innerHTML =
        analysis();


    } else if (
      current === "sources"
    ) {

      $("#content").innerHTML =
        sourcesPage();


    } else if (
      current === "about"
    ) {

      $("#content").innerHTML =
        about();
    }
  }


  /* =========================================================
     LOAD GENERAL LIVE DATA
     ========================================================= */

  async function loadLiveData(
    silent = false
  ) {

    if (liveLoading) {
      return;
    }


    liveLoading =
      true;


    if (!silent) {

      $("#status").textContent =
        "Connecting to CYBERHEAD...";
    }


    try {

      const [
        briefingResponse,
        statsResponse
      ] =
        await Promise.all([

          CyberheadAPI
            .getDailyBriefing(),

          CyberheadAPI
            .getStats()

        ]);


      liveBriefing =
        briefingResponse;


      liveStats =
        statsResponse;


      liveLoadError =
        null;


      $("#status").textContent =
        "";


    } catch (error) {

      liveLoadError =
        error.name === "AbortError"

          ? "The request timed out."

          : error.message;


      $("#status").textContent =
        `Unable to load live CYBERHEAD data: ${liveLoadError}`;


    } finally {

      liveLoading =
        false;


      if (
        page() !== "sources"
      ) {
        render();
      }
    }
  }


  /* =========================================================
     OPEN REPORTS FROM SEVERITY / CATEGORY
     ========================================================= */

  function openReportsFromSeverity(
    level
  ) {

    query =
      "";


    severity =
      level;


    category =
      "All";


    sort =
      "latest";


    articleOffset =
      0;


    articleResponse =
      null;


    $("#search").value =
      "";


    if (
      page() === "reports"
    ) {

      loadArticles();

    } else {

      location.hash =
        "reports";
    }
  }


  function openReportsFromCategory(
    name
  ) {

    query =
      "";


    severity =
      "All";


    category =
      name;


    sort =
      "latest";


    articleOffset =
      0;


    articleResponse =
      null;


    $("#search").value =
      "";


    if (
      page() === "reports"
    ) {

      loadArticles();

    } else {

      location.hash =
        "reports";
    }
  }


  /* =========================================================
     CLICK EVENTS
     ========================================================= */

  document.addEventListener(
    "click",
    (event) => {


      /* -----------------------------------------------------
         OPEN ARTICLE
         ----------------------------------------------------- */

      const liveOpen =
        event.target.closest(
          "[data-live-open]"
        );


      if (liveOpen) {

        openLiveArticle(
          liveOpen
            .dataset
            .liveOpen
        );

        return;
      }


      /* -----------------------------------------------------
         BRIEFING SEVERITY
         ----------------------------------------------------- */

      const briefingSeverity =
        event.target.closest(
          "[data-briefing-severity]"
        );


      if (briefingSeverity) {

        openReportsFromSeverity(
          briefingSeverity
            .dataset
            .briefingSeverity
        );

        return;
      }


      /* -----------------------------------------------------
         BRIEFING CATEGORY
         ----------------------------------------------------- */

      const briefingCategory =
        event.target.closest(
          "[data-briefing-category]"
        );


      if (briefingCategory) {

        openReportsFromCategory(
          briefingCategory
            .dataset
            .briefingCategory
        );

        return;
      }


      /* -----------------------------------------------------
         ANALYSIS SEVERITY
         ----------------------------------------------------- */

      const analysisSeverity =
        event.target.closest(
          "[data-analysis-severity]"
        );


      if (analysisSeverity) {

        openReportsFromSeverity(
          analysisSeverity
            .dataset
            .analysisSeverity
        );

        return;
      }


      /* -----------------------------------------------------
         ANALYSIS CATEGORY
         ----------------------------------------------------- */

      const analysisCategory =
        event.target.closest(
          "[data-analysis-category]"
        );


      if (analysisCategory) {

        openReportsFromCategory(
          analysisCategory
            .dataset
            .analysisCategory
        );

        return;
      }


      /* -----------------------------------------------------
         SAVED FILTER
         ----------------------------------------------------- */

      const savedFilter =
        event.target.closest(
          "[data-saved-filter]"
        );


      if (savedFilter) {

        savedSeverityFilter =
          savedFilter
            .dataset
            .savedFilter;


        render();

        return;
      }


      /* -----------------------------------------------------
         REMOVE SAVED ARTICLE
         ----------------------------------------------------- */

      const removeSaved =
        event.target.closest(
          "[data-remove-saved]"
        );


      if (removeSaved) {

        const id =
          String(
            removeSaved
              .dataset
              .removeSaved
          );


        saved =
          saved.filter(
            (value) =>
              value !== id
          );


        savedArticles =
          savedArticles.filter(
            (article) =>
              String(
                article.id
              )
              !== id
          );


        persistSaved();


        render();

        return;
      }


      /* -----------------------------------------------------
         ENABLE / DISABLE SOURCE
         ----------------------------------------------------- */

      const toggleButton =
        event.target.closest(
          "[data-toggle-source]"
        );


      if (toggleButton) {

        toggleSource(

          toggleButton
            .dataset
            .toggleSource,

          toggleButton
            .dataset
            .nextEnabled
          ===
          "true"
        );


        return;
      }


      /* -----------------------------------------------------
         TEST SOURCE
         ----------------------------------------------------- */

      if (
        event.target.id
        ===
        "test-source"
      ) {

        testSourceFeed();

        return;
      }


      /* -----------------------------------------------------
         RESET REPORT FILTERS
         ----------------------------------------------------- */

      if (
        event.target.id
        ===
        "reset-reports"
      ) {

        query =
          "";


        severity =
          "All";


        category =
          "All";


        sort =
          "latest";


        articleOffset =
          0;


        $("#search").value =
          "";


        loadArticles();

        return;
      }


      /* -----------------------------------------------------
         PREVIOUS REPORT PAGE
         ----------------------------------------------------- */

      if (
        event.target.id
        ===
        "previous-page"
      ) {

        articleOffset =
          Math.max(
            0,
            articleOffset
            -
            ARTICLE_LIMIT
          );


        loadArticles();


        window.scrollTo({
          top:
            0,

          behavior:
            "smooth"
        });


        return;
      }


      /* -----------------------------------------------------
         NEXT REPORT PAGE
         ----------------------------------------------------- */

      if (
        event.target.id
        ===
        "next-page"
      ) {

        articleOffset +=
          ARTICLE_LIMIT;


        loadArticles();


        window.scrollTo({
          top:
            0,

          behavior:
            "smooth"
        });


        return;
      }


      /* -----------------------------------------------------
         RETRY BUTTONS
         ----------------------------------------------------- */

      if (
        event.target.id
        ===
        "retry-reports"
      ) {

        loadArticles();

        return;
      }


      if (
        event.target.id
        ===
        "retry-alerts"
      ) {

        loadAlerts();

        return;
      }


      if (
        event.target.id
        ===
        "retry-saved"
      ) {

        loadSavedArticles();

        return;
      }


      if (
        event.target.id
        ===
        "retry-live"
      ) {

        loadLiveData();

        return;
      }


      if (
        event.target.id
        ===
        "retry-sources"
      ) {

        loadSources();

        return;
      }


      /* -----------------------------------------------------
         SAVE / UNSAVE ARTICLE
         ----------------------------------------------------- */

      const saveButton =
        event.target.closest(
          "[data-save-live]"
        );


      if (saveButton) {

        const id =
          String(
            saveButton
              .dataset
              .saveLive
          );


        if (
          saved.includes(id)
        ) {

          saved =
            saved.filter(
              (value) =>
                value !== id
            );


          savedArticles =
            savedArticles.filter(
              (article) =>
                String(
                  article.id
                )
                !== id
            );


        } else {

          saved.push(id);
        }


        persistSaved();


        saveButton.textContent =
          saved.includes(id)

            ? "Remove from saved"

            : "Save story ♧";


        if (
          page() === "saved"
        ) {

          loadSavedArticles();
        }
      }
    }
  );


  /* =========================================================
     SOURCE FORM SUBMISSION
     ========================================================= */

  document.addEventListener(
    "submit",
    (event) => {

      if (
        event.target.id
        !==
        "source-form"
      ) {

        return;
      }


      event.preventDefault();


      addSourceFromForm();
    }
  );


  /* =========================================================
     SOURCE INPUT
     ========================================================= */

  document.addEventListener(
    "input",
    (event) => {

      if (
        event.target.id
        ===
        "source-name"
      ) {

        sourceDraftName =
          event.target.value;
      }


      if (
        event.target.id
        ===
        "source-url"
      ) {

        sourceDraftUrl =
          event.target.value;


        sourceTestResult =
          null;
      }
    }
  );


  /* =========================================================
     REPORT FILTER CHANGES
     ========================================================= */

  document.addEventListener(
    "change",
    (event) => {

      if (
        event.target.id
        ===
        "severity"
      ) {

        severity =
          event.target.value;


      } else if (
        event.target.id
        ===
        "category"
      ) {

        category =
          event.target.value;


      } else if (
        event.target.id
        ===
        "sort"
      ) {

        sort =
          event.target.value;


      } else {

        return;
      }


      articleOffset =
        0;


      loadArticles();
    }
  );


  /* =========================================================
     SEARCH
     ========================================================= */

  $("#search")
    .addEventListener(
      "input",
      (event) => {

        query =
          event.target.value;


        articleOffset =
          0;


        if (
          page()
          !==
          "reports"
        ) {

          location.hash =
            "reports";
        }


        clearTimeout(
          searchTimer
        );


        searchTimer =
          setTimeout(
            () =>
              loadArticles(),
            350
          );
      }
    );


  /* =========================================================
     DIALOG
     ========================================================= */

  $(".close").onclick =
    () =>
      $("#report-dialog")
        .close();


  $("#report-dialog")
    .addEventListener(
      "click",
      (event) => {

        if (
          event.target
          !==
          $("#report-dialog")
        ) {

          return;
        }


        const box =
          event.target
            .getBoundingClientRect();


        if (
          event.clientX
          <
          box.left

          ||

          event.clientX
          >
          box.right

          ||

          event.clientY
          <
          box.top

          ||

          event.clientY
          >
          box.bottom
        ) {

          event.target.close();
        }
      }
    );


  /* =========================================================
     PAGE NAVIGATION
     ========================================================= */

  window.addEventListener(
    "hashchange",
    () => {

      const current =
        page();


      render();


      /*
       * If the user started directly on Sources,
       * briefing/stats were intentionally not loaded.
       * Load them when moving to another page.
       */

      if (
        current !== "sources"
        &&
        (
          !liveBriefing
          ||
          !liveStats
        )
      ) {

        loadLiveData();
      }


      if (
        current === "reports"
        &&
        articleResponse === null
        &&
        !articlesLoading
      ) {

        loadArticles();
      }


      if (
        current === "alerts"
        &&
        criticalAlertsResponse === null
        &&
        !alertsLoading
      ) {

        loadAlerts();
      }


      if (
        current === "saved"
        &&
        !savedLoading
      ) {

        loadSavedArticles();
      }


      if (
        current === "sources"
        &&
        sourcesResponse === null
        &&
        !sourcesLoading
      ) {

        loadSources();
      }
    }
  );


  /* =========================================================
     CLOCK
     ========================================================= */

  setInterval(
    () => {

      const clock =
        $("#clock");


      if (clock) {

        clock.textContent =
          new Date()
            .toLocaleTimeString(
              "en-GB",
              {
                hour:
                  "2-digit",

                minute:
                  "2-digit"
              }
            );
      }
    },

    30000
  );


  /* =========================================================
     AUTO REFRESH
     ========================================================= */

  setInterval(
    () => {

      const currentPage =
        page();


      /*
       * Do NOT automatically refresh Sources.
       * Keeping Sources stable prevents the
       * Add Source form from being rebuilt.
       */

      if (
        currentPage === "sources"
      ) {

        return;
      }


      loadLiveData(
        true
      );


      if (
        currentPage === "reports"
      ) {

        loadArticles();
      }


      if (
        currentPage === "alerts"
      ) {

        loadAlerts();
      }

    },

    window.CYBERHEAD_CONFIG
      .refreshMs

    ||

    60000
  );


  /* =========================================================
     START
     ========================================================= */

  $("#year").textContent =
    new Date()
      .getFullYear();


  render();


  /*
   * Sources only needs source information.
   * This keeps the source page stable.
   */

  if (
    page() === "sources"
  ) {

    loadSources();

  } else {

    loadLiveData();
  }


  if (
    page() === "reports"
  ) {

    loadArticles();
  }


  if (
    page() === "alerts"
  ) {

    loadAlerts();
  }


  if (
    page() === "saved"
  ) {

    loadSavedArticles();
  }

})();