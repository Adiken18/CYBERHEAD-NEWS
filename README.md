# CYBERHEAD News

CYBERHEAD News is a self-hosted cybersecurity news intelligence web application.

It collects cybersecurity news from configured RSS/Atom sources, extracts article content, identifies CVEs, classifies reports with a trained machine-learning model, enriches vulnerability information using NVD and CISA KEV, performs explainable severity analysis, generates extractive NLP summaries, and builds a rolling 24-hour Daily Briefing.

CYBERHEAD does **not** require a permanent public server for standalone use. Each user can run their own local copy on Windows or macOS with their own local SQLite database.

For a shorter installation/automation guide, see [`docs/CYBERHEAD_SETUP_AND_AUTOMATION.md`](docs/CYBERHEAD_SETUP_AND_AUTOMATION.md).

---

## 1. What CYBERHEAD Does

The current processing pipeline is:

```text
Configured RSS / Atom Sources
        ↓
Article Collection
        ↓
Full-text Extraction
        ↓
CVE Extraction
        ↓
Machine-Learning Category Classification
        ↓
NVD Vulnerability Enrichment
        ↓
CISA Known Exploited Vulnerabilities
        ↓
Threat Tagging
        ↓
Explainable Severity Analysis
        ↓
NLP Article Summarisation
        ↓
Rolling 24-hour Daily Briefing
        ↓
FastAPI
        ↓
CYBERHEAD Web Dashboard
```

Main features include:

- automatic cybersecurity-news collection
- dynamic RSS/Atom source management
- full-article text extraction
- CVE extraction
- ML category classification
- NVD vulnerability enrichment
- CISA KEV matching
- threat tagging
- Low / Medium / High / Critical severity analysis
- extractive NLP article summaries
- “Why it matters” explanations
- defensive recommendations
- rolling 24-hour Daily Briefing
- searchable and filterable reports
- Threats & Alerts
- Saved Stories
- live Analysis statistics
- self-hosted local operation
- optional six-hour automatic processing

---

## 2. Project Structure

```text
CYBERHEAD-NEWS/
│
├── backend/
│   ├── app/
│   │   ├── collector.py
│   │   ├── extractor.py
│   │   ├── cve_extractor.py
│   │   ├── category_classifier.py
│   │   ├── cve_enricher.py
│   │   ├── cisa_enricher.py
│   │   ├── tag_extractor.py
│   │   ├── severity_engine.py
│   │   ├── summarizer.py
│   │   ├── daily_briefing.py
│   │   ├── source_manager.py
│   │   ├── source_api.py
│   │   ├── pipeline.py
│   │   ├── database.py
│   │   └── main.py
│   │
│   ├── requirements.txt
│   ├── run_pipeline.bat
│   └── run_pipeline.sh
│
├── Frontend/
│   ├── index.html
│   ├── landing.css
│   ├── landing.js
│   └── dashboard/
│       ├── index.html
│       ├── styles.css
│       ├── dashboard.css
│       ├── config.js
│       ├── api.js
│       └── app.js
│
├── ml/
│   ├── data/
│   ├── training/
│   └── saved_models/
│       ├── category_model.joblib
│       └── category_model_metrics.json
│
├── docs/
├── .gitignore
└── README.md
```

---

# 3. Requirements

CYBERHEAD was developed and tested using Python 3.13.

You need:

- Python 3.13 or another compatible Python 3 version
- Git
- an internet connection for article collection and NVD/CISA enrichment
- a modern web browser

VS Code is useful for development but is **not required** to run CYBERHEAD.

The frontend can be served with Python's built-in HTTP server.

---

# 4. Windows Installation

## 4.1 Check Python and Git

Open PowerShell:

```powershell
py --version
git --version
```

If `py` is not available, try:

```powershell
python --version
```

---

## 4.2 Clone CYBERHEAD

```powershell
git clone https://github.com/Adiken18/CYBERHEAD-NEWS.git
cd CYBERHEAD-NEWS
```

---

## 4.3 Create the Python virtual environment

```powershell
cd backend
py -m venv .venv
```

If `py` is unavailable:

```powershell
python -m venv .venv
```

You do not have to activate the virtual environment. The following instructions call its Python executable directly, which avoids PowerShell execution-policy problems.

---

## 4.4 Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Check the main dependencies:

```powershell
.\.venv\Scripts\python.exe -c "import fastapi, sklearn, joblib, feedparser, requests, trafilatura, numpy; print('CYBERHEAD dependencies OK')"
```

---

## 4.5 Confirm the trained ML model exists

From the `backend` directory:

```powershell
Test-Path ..\ml\saved_models\category_model.joblib
```

Expected:

```text
True
```

---

# 5. macOS Installation

## 5.1 Check Python and Git

Open Terminal:

```bash
python3 --version
git --version
```

If Git is not installed, macOS may offer to install the Xcode Command Line Tools.

---

## 5.2 Clone CYBERHEAD

```bash
git clone https://github.com/Adiken18/CYBERHEAD-NEWS.git
cd CYBERHEAD-NEWS
```

---

## 5.3 Create the Python virtual environment

```bash
cd backend
python3 -m venv .venv
```

Activation is optional. The remaining commands use the environment's Python directly.

---

## 5.4 Install dependencies

```bash
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

Check the main dependencies:

```bash
./.venv/bin/python -c "import fastapi, sklearn, joblib, feedparser, requests, trafilatura, numpy; print('CYBERHEAD dependencies OK')"
```

---

## 5.5 Confirm the trained ML model exists

```bash
test -f ../ml/saved_models/category_model.joblib && echo "ML model found"
```

Expected:

```text
ML model found
```

---

# 6. First CYBERHEAD Data Run

A fresh clone does not contain the developer's local SQLite database.

This is intentional.

Each installation creates its own:

```text
backend/cyberhead.db
```

Before expecting reports on the website, run the intelligence pipeline at least once.

## Windows

From `CYBERHEAD-NEWS\backend`:

```powershell
.\.venv\Scripts\python.exe -m app.pipeline
```

## macOS

From `CYBERHEAD-NEWS/backend`:

```bash
./.venv/bin/python -m app.pipeline
```

The first run can take several minutes because CYBERHEAD deliberately spaces NVD requests to respect the external service.

### Important first-run NVD behaviour

CYBERHEAD limits the number of NVD lookups in one pipeline run.

If a fresh installation discovers more CVEs than can be safely enriched in one run, the pipeline may stop before threat scoring because some CVEs still have no usable NVD data.

This is a safety feature.

Run the pipeline again without collecting duplicate news:

### Windows

```powershell
.\.venv\Scripts\python.exe -m app.pipeline --skip-collect
```

### macOS

```bash
./.venv/bin/python -m app.pipeline --skip-collect
```

Repeat after a short wait if necessary until the run reaches:

```text
PIPELINE COMPLETE
No pipeline warnings.
```

Later runs are normally much faster because NVD results are cached and only new or stale vulnerability data needs refreshing.

---

# 7. Start the CYBERHEAD Website

CYBERHEAD has two local parts:

```text
Browser
   ↓
Frontend web server
   ↓
FastAPI backend
   ↓
SQLite database
```

You normally run the backend in one terminal and the frontend web server in another.

---

# 8. Start the Backend on Windows

Open PowerShell:

```powershell
cd path\to\CYBERHEAD-NEWS\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend is now available at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Keep this terminal open while using the website.

---

# 9. Start the Frontend on Windows

Open a second PowerShell window.

Move to the repository root:

```powershell
cd path\to\CYBERHEAD-NEWS
```

Start the frontend server using the same virtual environment:

```powershell
.\backend\.venv\Scripts\python.exe -m http.server 5500 --directory Frontend
```

Open:

```text
http://127.0.0.1:5500/
```

This loads the CYBERHEAD landing page.

The dashboard connects to:

```text
http://127.0.0.1:8000/api
```

as configured in:

```text
Frontend/dashboard/config.js
```

---

# 10. Start the Backend on macOS

Open Terminal:

```bash
cd /path/to/CYBERHEAD-NEWS/backend
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open API documentation at:

```text
http://127.0.0.1:8000/docs
```

Keep this terminal open.

---

# 11. Start the Frontend on macOS

Open a second Terminal window.

Move to the repository root:

```bash
cd /path/to/CYBERHEAD-NEWS
```

Run:

```bash
./backend/.venv/bin/python -m http.server 5500 --directory Frontend
```

Open:

```text
http://127.0.0.1:5500/
```

---

# 12. Stopping CYBERHEAD

In the terminal running FastAPI, press:

```text
Ctrl + C
```

Do the same in the terminal running the frontend HTTP server.

Stopping the web servers does **not** delete the database.

---

# 13. Manual Pipeline Updates

The intelligence pipeline does not require FastAPI or the frontend to be running.

You can update CYBERHEAD's database independently.

## Windows

```powershell
cd path\to\CYBERHEAD-NEWS\backend
.\.venv\Scripts\python.exe -m app.pipeline
```

## macOS

```bash
cd /path/to/CYBERHEAD-NEWS/backend
./.venv/bin/python -m app.pipeline
```

When the website is opened later, it will read the updated database.

---

# 14. Windows Automatic Processing Every Six Hours

CYBERHEAD includes:

```text
backend/run_pipeline.bat
```

This script changes into the backend directory, runs the pipeline using:

```text
backend\.venv\Scripts\python.exe
```

and writes output to:

```text
backend/pipeline.log
```

## Recommended Task Scheduler setup

1. Open **Task Scheduler**.
2. Choose **Create Task**.
3. Set the name to:

```text
CYBERHEAD News Pipeline
```

4. Under **General**, using “Run only when user is logged on” is the simplest setup for a personal installation.
5. Open **Triggers** and create a new trigger.
6. Select **Daily**.
7. Choose the first time you want CYBERHEAD to run.
8. Enable **Repeat task every: 6 hours**.
9. Set **for a duration of: 1 day**.
10. Ensure the trigger is enabled.
11. Open **Actions** and choose **Start a program**.
12. Program/script:

```text
C:\Windows\System32\cmd.exe
```

13. Add arguments:

```text
/c ""C:\FULL\PATH\TO\CYBERHEAD-NEWS\backend\run_pipeline.bat""
```

14. Start in:

```text
C:\FULL\PATH\TO\CYBERHEAD-NEWS\backend
```

15. Under **Settings**, enabling **Run task as soon as possible after a scheduled start is missed** is recommended.
16. If you want CYBERHEAD to run while a laptop is on battery power, review the battery options under **Conditions**.
17. Save the task.

The path must match the actual location of the repository on that computer.

## Test the Windows task

```powershell
schtasks /Run /TN "CYBERHEAD News Pipeline"
```

Check it:

```powershell
schtasks /Query /TN "CYBERHEAD News Pipeline" /V /FO LIST
```

A successful completed run normally shows:

```text
Last Result: 0
```

Check the pipeline log:

```powershell
Get-Content .\backend\pipeline.log -Tail 50
```

---

# 15. macOS Automatic Processing Every Six Hours

macOS uses `launchd` for scheduled background jobs.

CYBERHEAD includes:

```text
backend/run_pipeline.sh
```

First make it executable:

```bash
cd /path/to/CYBERHEAD-NEWS/backend
chmod +x run_pipeline.sh
```

Test it manually:

```bash
./run_pipeline.sh
```

It writes pipeline output to:

```text
backend/pipeline.log
```

---

## 15.1 Create a LaunchAgent

Find the absolute backend path:

```bash
pwd
```

For example:

```text
/Users/alex/Documents/CYBERHEAD-NEWS/backend
```

Create the LaunchAgents directory if needed:

```bash
mkdir -p ~/Library/LaunchAgents
```

Create:

```text
~/Library/LaunchAgents/com.cyberhead.pipeline.plist
```

with this content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">

<plist version="1.0">
<dict>

    <key>Label</key>
    <string>com.cyberhead.pipeline</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/FULL/PATH/TO/CYBERHEAD-NEWS/backend/run_pipeline.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/FULL/PATH/TO/CYBERHEAD-NEWS/backend</string>

    <key>StartInterval</key>
    <integer>21600</integer>

    <key>RunAtLoad</key>
    <true/>

</dict>
</plist>
```

`21600` seconds equals six hours.

Replace **both** `/FULL/PATH/...` values with the real absolute path shown by `pwd`.

---

## 15.2 Load the macOS automation

Run:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.cyberhead.pipeline.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cyberhead.pipeline.plist
launchctl enable gui/$(id -u)/com.cyberhead.pipeline
```

Start a test run immediately:

```bash
launchctl kickstart -k gui/$(id -u)/com.cyberhead.pipeline
```

Inspect the job:

```bash
launchctl print gui/$(id -u)/com.cyberhead.pipeline
```

Check CYBERHEAD's pipeline log:

```bash
tail -n 50 /FULL/PATH/TO/CYBERHEAD-NEWS/backend/pipeline.log
```

---

## 15.3 Disable macOS automation

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.cyberhead.pipeline.plist
```

To remove it completely:

```bash
rm ~/Library/LaunchAgents/com.cyberhead.pipeline.plist
```

---

# 16. What the Six-Hour Automation Does

The scheduled job runs the intelligence pipeline only.

It can:

- check enabled RSS/Atom sources
- collect new articles
- extract full article text
- identify CVEs
- classify new articles
- refresh necessary NVD information
- check CISA KEV
- detect threat tags
- calculate severity
- generate article summaries
- refresh the rolling Daily Briefing

The frontend does **not** need to be open for this processing to happen.

FastAPI also does **not** need to be running for the scheduled pipeline itself.

When the user later starts the website, the dashboard reads the latest information from the local SQLite database.

---

# 17. Important Automation Notes

A computer cannot process news while it is powered off.

Laptop sleep, battery settings, lack of internet connectivity or the user's login state can also delay scheduled runs depending on operating-system settings.

On Windows, enabling **Run task as soon as possible after a scheduled start is missed** is recommended.

On macOS, a LaunchAgent runs in the user's login session. Sleep can delay execution until the computer is available again.

---

# 18. Source Management

The Sources page can:

- list configured sources
- test an RSS/Atom URL
- add a source
- enable a source
- disable a source
- display source health and collection information

The collector reads enabled sources from the local database.

Full-text extraction also recognises domains belonging to configured CYBERHEAD sources.

Each installation can therefore maintain its own news-source configuration.

---

# 19. Machine Learning

CYBERHEAD uses a trained category classifier stored at:

```text
ml/saved_models/category_model.joblib
```

The classifier uses TF-IDF text features and a Linear Support Vector Machine.

Current categories are:

- Vulnerabilities
- Data breaches
- Ransomware
- Phishing
- DDoS
- Other malware
- Other cybersecurity news

---

# 20. Severity Analysis

CYBERHEAD calculates an internal prioritisation score from 0 to 100.

| Score | Severity |
|---:|---|
| 70–100 | Critical |
| 40–69 | High |
| 20–39 | Medium |
| 0–19 | Low |

The CYBERHEAD score is an internal prioritisation mechanism and is not a replacement for CVSS.

Evidence can include:

- CVSS information
- CISA KEV presence
- known ransomware use
- zero-day indicators
- remote code execution
- privilege escalation
- data theft
- large-scale impact
- critical-infrastructure impact
- recency
- category context

---

# 21. NLP Summarisation

CYBERHEAD uses lightweight extractive NLP based on TF-IDF sentence ranking.

The summary is generated from important original article sentences.

“Why it matters” and defensive recommendations are generated separately from structured cybersecurity evidence and rules.

They should not be described as outputs of the ML category classifier.

---

# 22. Daily Briefing

The Daily Briefing covers a rolling previous 24-hour window.

All qualifying Critical threats are included.

If there are fewer than five Critical items, the briefing is filled using the highest-priority remaining reports.

The briefing is refreshed whenever the complete pipeline reaches the Daily Briefing stage.

---

# 23. Local Database

CYBERHEAD stores local data in:

```text
backend/cyberhead.db
```

The database is intentionally ignored by Git.

This means:

- the repository does not distribute one person's collected database
- every installation can build its own data
- adding sources on one computer does not automatically add them to another computer

---

# 24. Saved Stories

Saved Stories currently use the browser's `localStorage`.

They remain in that browser on that device.

They are not currently synchronised between computers.

---

# 25. API

When FastAPI is running:

```text
http://127.0.0.1:8000/docs
```

provides interactive API documentation.

Important routes include:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/articles` | Browse/search/filter processed reports |
| GET | `/api/articles/{id}` | View one report |
| GET | `/api/daily-briefing` | Current rolling Daily Briefing |
| GET | `/api/stats` | Dashboard analysis statistics |
| GET | `/api/categories` | Category information |
| GET | `/api/severities` | Severity information |
| GET | `/api/sources` | Configured sources |
| POST | `/api/sources/test` | Test a source feed |
| POST | `/api/sources` | Add a source |
| PATCH | `/api/sources/{id}/enabled` | Enable or disable a source |

---

# 26. Troubleshooting

## Website opens but has no live data

Check that FastAPI is running:

```text
http://127.0.0.1:8000/docs
```

A fresh database may also need its first pipeline run.

---

## PowerShell says script execution is disabled

CYBERHEAD does not require virtual-environment activation.

Use:

```powershell
.\.venv\Scripts\python.exe
```

directly as shown in this README.

---

## NVD temporarily returns HTTP 503 or times out

CYBERHEAD retains an existing cached NVD record when available.

If a detected CVE has no usable NVD data at all, the pipeline deliberately stops before threat scoring.

Wait and rerun:

```powershell
.\.venv\Scripts\python.exe -m app.pipeline --skip-collect
```

or on macOS:

```bash
./.venv/bin/python -m app.pipeline --skip-collect
```

---

## A first pipeline run stops after the NVD stage

A fresh installation may contain more CVEs than the configured NVD batch size.

Rerun with `--skip-collect` until all detected CVEs have usable NVD results.

This avoids collecting the same feeds unnecessarily while allowing threat-intelligence enrichment to continue safely.

---

## Port 8000 is already in use

Stop the existing FastAPI process or identify the process already using the port.

The frontend is currently configured for:

```text
http://127.0.0.1:8000/api
```

so changing the backend port also requires changing:

```text
Frontend/dashboard/config.js
```

---

## Port 5500 is already in use

Use another frontend port only if necessary.

The backend CORS configuration supports the local frontend, but browser bookmarks and instructions in this README assume port 5500.

---

# 27. Public Deployment

The current version is designed primarily as a trusted self-hosted installation.

Do not expose the current local development configuration directly to the public internet without additional deployment work.

A shared/public deployment should normally add:

- authentication and authorisation
- protection for source-management endpoints
- HTTPS
- production web serving
- production FastAPI process management
- appropriate database and backup strategy
- tighter CORS configuration
- operating-system/server hardening

Public deployment is optional and is not required for local CYBERHEAD use.

---