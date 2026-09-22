# CYBERHEAD News data model

## Primary category and tags

Every classified report has one primary category. A missing analysis/category means
the report has not yet been classified; it must not be shown as an ML prediction.
The shared labels live in `backend/app/categories.py` and are available at
`GET /categories`.

| Primary category | Main subject |
| --- | --- |
| Phishing | Deceptive messages or sites intended to steal credentials or trick victims |
| Ransomware | Ransomware infection, encryption or ransomware-related extortion |
| Other malware | Malicious software other than ransomware, including spyware, trojans and worms |
| Vulnerabilities | Software or hardware weaknesses, exploits and patches |
| Data breaches | Unauthorised access to or exposure/theft of data as the main reported incident |
| DDoS | Distributed denial-of-service attacks that disrupt availability |
| Other cybersecurity news | Relevant cybersecurity news outside the six categories above |

Choose the main subject of the report, not every attack technique mentioned.
An article about a ransomware incident delivered through phishing is **Ransomware**,
with tags such as `phishing` and `data theft`. An article primarily about fixing a
vulnerability remains **Vulnerabilities** even if ransomware is mentioned as context.
Use lower-case, trimmed tags consistently. Ambiguous training examples need human
review; do not automatically label all unknown articles as Other cybersecurity news.

## Storage

| Table | Purpose |
| --- | --- |
| `articles` | Original title, unique URL, publisher, dates and available text |
| `categories` | The seven primary category labels |
| `reports` | Consolidated incident title, summary, why it matters and timestamps |
| `report_articles` | Links reports to original articles, preserving all source URLs |
| `report_analysis` | One current analysis per report: category, optional confidence, predicted/final severity, explanation, recommendations and model/rules versions |
| `report_tags` | Additional topics; a tag can appear once per report |
| `report_cves` | Related CVE identifiers; future extraction must validate identifiers |
| `report_affected_systems` | Named products, services or systems affected |

Three articles about one incident remain three rows in `articles`, linked to one
row in `reports`. Recollecting the same URL must not add an article. Different URLs
are retained even when their content overlaps. The join table also permits an
article covering several incidents to support more than one report.

The schema supports consolidation; automatic grouping and collection are not yet
implemented. Report timestamps use UTC; future update operations must explicitly
set `updated_at`. Store supplied publication dates in UTC ISO 8601 format when known.
Missing text, dates or analysis must stay missing rather than being invented.

Severity is Low, Medium, High or Critical. `predicted_severity` stores the ML output;
`final_severity` stores the decision after rules; `severity_reason` explains it.
Record model and rules versions when analysis runs. Do not fabricate confidence
for models that do not provide a suitable probability estimate. There is no separate
ranking score or ranking model in this schema. Analysis storage keeps the latest
result; retaining previous runs can be added later if needed.

## Compatibility

Initialisation adds tables without dropping or rebuilding `articles`. Existing IDs,
URLs and text are preserved. The old article-level `category` and `severity` columns
remain for compatibility with `/articles`; new report processing must use
`report_analysis` as the authoritative classification. Old classifications are not
automatically copied into report analysis or represented as new model predictions.

Foreign keys are enabled by `get_connection()`. Use this helper for database access.
Deleting a report removes its links and analysis but preserves original articles.
Deleting an article that is still linked to a report is blocked.

## Verification

From `backend`, run:

```sh
python -m unittest discover -s tests -v
```

The tests use temporary databases, including the original article schema. They check
repeated initialisation, preservation of existing data, report/source relationships,
category and severity constraints, and foreign-key enforcement. They require only
Python's standard library and do not change your local development database.
