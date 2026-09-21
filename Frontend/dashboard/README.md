# CYBERHEAD — Neon Briefing frontend

A plain HTML, CSS and JavaScript implementation of your selected Option 1 design. No framework, build process, backend or model is required to try it.

## Open it now

1. Extract the whole ZIP first.
2. Open `cyberhead-frontend/index.html` in a browser.
3. Keep all files and the assets folder together. Opening only a copied HTML file will lose styling and behaviour.

Alternatively open the folder in VS Code and use Live Server. A local server is recommended when connecting an API.

## Add it after your existing welcome page

Copy this entire folder into your existing project. Point the welcome page’s Enter button or link to `cyberhead-frontend/index.html`. For example:

    <a href="cyberhead-frontend/index.html">Enter Cyberhead</a>

This is an independent frontend module; your existing landing and welcome files were not edited. Routes inside this module use URL hashes, so static hosting needs no special routing configuration.

## Included

- Daily briefing first, featured story, secondary stories and briefing selection.
- Threats and alerts; all reports; saved stories; analysis; sources; About.
- Search, severity/category filters and priority/date sorting.
- Report dialog with classification, confidence, priority, summary, suggested review, indicators, source references and grouped coverage count.
- Browser-local saved stories, keyboard focus, Escape-to-close dialog and responsive layout.
- Loading, request failure/retry and empty states.
- Fictional data clearly labelled. No live collection, notifications, authentication or model execution.

## Files you will change later

| File | Responsibility |
| --- | --- |
| index.html | Page shell and script order |
| styles.css | Layout, colours and responsive rules |
| app.js | Rendering and interactions |
| mock-data.js | Fictional sample data only |
| config.js | Demo/API switch and backend base URL |
| api.js | Network calls, timeout and response validation |
| api-example.json | Example backend response matching the demo |
| assets/server-room.png | Generated pixel-art asset |

## Connect your future backend

1. Implement `GET /api/dashboard` on your backend. Return JSON matching `api-example.json` (top-level object, no extra `data` wrapper).
2. In `config.js`, change `mode: 'mock'` to `mode: 'api'` and set `apiBaseUrl` to your backend’s `/api` URL.
3. Serve the frontend over HTTP, for example with VS Code Live Server. Configure the backend’s CORS policy for the actual frontend origin. On deployment use HTTPS or a same-origin `/api` base URL.
4. The frontend will fetch the dashboard when opened or reloaded. It does not poll for updates in this version. A failed API call shows a retry button; it never silently substitutes fake reports.

The demo fixture remains bundled but is not read in API mode. There are no secret keys in this project. Keep collector credentials, model credentials and model files on the backend. Authentication and user-specific saved stories can be added later; current saves use localStorage only.

### Proposed response contract

`GET /api/dashboard` returns:

- `generatedAt`: ISO timestamp for the dashboard snapshot.
- `briefing`: `title`, `summary`, and `reportIds` ordered by your briefing pipeline. The first ID is the featured story.
- `reports`: array of normalised report objects.
- `alerts`: objects containing `reportId`, `time` (display text), and `text`.
- `sources`: objects containing `id`, `name`, `url` (HTTPS URL or null), `status`, and `description`.
- `pipeline`: map of stage names to readable status strings.

Each report contains:

| Field | Type / meaning |
| --- | --- |
| id | Unique stable string; used by saved stories and briefing references |
| title, summary, details | Plain text; no HTML required |
| category | Classification label, e.g. Phishing, Ransomware, Vulnerability |
| severity | Critical, High, Medium or Low |
| score | Number 0–100; higher = higher priority |
| confidence | Number 0–1; classification confidence, separate from score |
| publishedAt | Valid ISO timestamp |
| recommendation | Plain-text suggested review |
| sourceIds | Array of IDs resolving to sources |
| relatedCount | Positive integer; total coverage grouped by the backend |
| indicators | Array of extracted indicator strings; displayed as inert text |
| tags | Array of searchable strings |
| image | server, mail or skull; chooses a bundled illustration |

Return every report referenced by briefing or alerts, and every source referenced by reports. This starter loads one complete dashboard snapshot; pagination, server-side search and full grouped-article records are future extensions. The interface shows supplied source references and a coverage count; it does not invent missing article links. For real coverage, each source entry can represent a specific article URL. All scores and ordering must come from your backend, not a fake frontend classifier.

### Intended backend flow

Scheduled collection → extraction/normalisation → duplicate grouping → ML classification → priority ranking → daily briefing generation → stored dashboard response → this frontend.

Collection usually belongs to a scheduled collector or agent that fetches allowed feeds/APIs. A classification model does not collect articles on its own. Your backend can orchestrate all these stages as one system. Briefing generation may be extractive or a separate summarisation component, depending on your project requirements.

The frontend does not prescribe Python, FastAPI, Flask, Node or a particular model. Any backend that follows the JSON contract can connect to it.

## Illustrations

The server-room art was generated with the built-in image-generation tool using the selected Neon Briefing screenshot as its visual reference. Prompt: “Create a project asset based on the exact supplied website reference: a wide pixel art cybersecurity server room illustration, dark navy black, luminous cyan server racks, central red warning triangle on a terminal, crisp detailed retro game pixels. Match the reference's top story artwork palette and atmosphere. Artwork ONLY filling whole frame, no UI, no labels, no lettering, no borders. Landscape 3:2.”

The email and ransomware cards reuse that asset with category symbols. This is a close implementation of the layout, rather than a pixel-for-pixel reproduction of all artwork and fonts.

## Validation performed

JavaScript syntax checks passed. API adapter checks passed for fixture loading, linked report/source IDs, request URL construction, successful JSON responses, HTTP errors, malformed payloads and timeout propagation. Local script/style/image references were checked. Browser visual and interaction testing could not be completed in the build environment because the required browser download was unavailable; inspect the desktop and mobile layouts in your own browser.
