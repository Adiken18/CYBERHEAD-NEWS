/* =========================================================
   CYBERHEAD FRONTEND API
   ========================================================= */

window.CyberheadAPI = (() => {

  "use strict";


  const config =
    window.CYBERHEAD_CONFIG;


  // =======================================================
  // GENERIC REQUEST
  // =======================================================

  async function request(
    path,
    options = {}
  ) {

    const controller =
      new AbortController();


    const timer =
      setTimeout(
        () =>
          controller.abort(),

        config.timeoutMs
        ||
        10000
      );


    const method =
      options.method
      ||
      "GET";


    const headers = {

      Accept:
        "application/json",

      ...(
        options.body
          ? {
              "Content-Type":
                "application/json"
            }
          : {}
      ),

      ...(
        options.headers
        ||
        {}
      )
    };


    try {

      const response =
        await fetch(

          config.apiBaseUrl
            .replace(
              /\/$/,
              ""
            )

          +

          path,

          {

            method,

            headers,

            signal:
              controller.signal,

            body:
              options.body
              ?? undefined
          }
        );


      let data =
        null;


      try {

        data =
          await response.json();

      } catch {

        data =
          null;
      }


      if (
        !response.ok
      ) {

        let message =
          `Server returned ${response.status}`;


        if (
          typeof data?.detail
          === "string"
        ) {

          message =
            data.detail;

        } else if (
          data?.detail?.message
        ) {

          message =
            data.detail.message;

        }


        throw new Error(
          message
        );
      }


      return data;


    } finally {

      clearTimeout(
        timer
      );
    }
  }


  // =======================================================
  // QUERY STRING
  // =======================================================

  function buildQuery(
    parameters
  ) {

    const query =
      new URLSearchParams();


    Object.entries(
      parameters
      ||
      {}
    ).forEach(
      ([
        key,
        value
      ]) => {

        if (
          value === undefined
          ||
          value === null
          ||
          value === ""
        ) {

          return;
        }


        query.set(
          key,
          value
        );
      }
    );


    const text =
      query.toString();


    return (
      text
        ? `?${text}`
        : ""
    );
  }


  // =======================================================
  // DAILY BRIEFING
  // =======================================================

  async function getDailyBriefing() {

    return request(
      "/daily-briefing"
    );
  }


  // =======================================================
  // STATISTICS
  // =======================================================

  async function getStats() {

    return request(
      "/stats"
    );
  }


  // =======================================================
  // ARTICLES
  // =======================================================

  async function getArticles(
    {
      category = "",
      severity = "",
      search = "",
      sort = "latest",
      limit = 20,
      offset = 0
    } = {}
  ) {

    const query =
      buildQuery({

        category,

        severity,

        search,

        sort,

        limit,

        offset
      });


    return request(
      `/articles${query}`
    );
  }


  // =======================================================
  // SINGLE ARTICLE
  // =======================================================

  async function getArticleDetail(
    articleId
  ) {

    return request(
      `/articles/${encodeURIComponent(
        articleId
      )}`
    );
  }


  // =======================================================
  // CATEGORY LIST
  // =======================================================

  async function getCategories() {

    return request(
      "/categories"
    );
  }


  // =======================================================
  // SEVERITY LIST
  // =======================================================

  async function getSeverities() {

    return request(
      "/severities"
    );
  }


  // =======================================================
  // SOURCE LIST
  // =======================================================

  async function getSources() {

    return request(
      "/sources"
    );
  }


  // =======================================================
  // TEST SOURCE
  // =======================================================

  async function testSource(
    url
  ) {

    return request(
      "/sources/test",
      {

        method:
          "POST",

        body:
          JSON.stringify({
            url
          })
      }
    );
  }


  // =======================================================
  // ADD SOURCE
  // =======================================================

  async function addSource(
    name,
    url
  ) {

    return request(
      "/sources",
      {

        method:
          "POST",

        body:
          JSON.stringify({
            name,
            url
          })
      }
    );
  }


  // =======================================================
  // ENABLE / DISABLE SOURCE
  // =======================================================

  async function setSourceEnabled(
    sourceId,
    enabled
  ) {

    return request(

      `/sources/${encodeURIComponent(
        sourceId
      )}/enabled`,

      {

        method:
          "PATCH",

        body:
          JSON.stringify({
            enabled
          })
      }
    );
  }


  // =======================================================
  // PUBLIC API
  // =======================================================

  return {

    getDailyBriefing,

    getStats,

    getArticles,

    getArticleDetail,

    getCategories,

    getSeverities,

    getSources,

    testSource,

    addSource,

    setSourceEnabled
  };

})();