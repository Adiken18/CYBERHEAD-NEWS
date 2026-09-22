# CYBERHEAD-NEWS:

- An AI-powered web application that collects and summarises
cybersecurity threats and incidents.

# Features:

- Automated Information Collection: Gather cybersecurity news, vulnerability reports and security advisories from multiple sources.

- Key Information Extraction: Identify threat names, affected software and attack types from collected reports.

- Duplicate Detection: Recognise reports covering the same threat or incident and consolidate them to reduce repetition.

- Threat Classification: Organise reports into categories such as phishing, ransomware, malware, vulnerabilities and data breaches along with severity prioritisation.

- Daily Cybersecurity Briefing: Generate a concise daily summary highlighting the most important threats and incidents.

# Team Members:

- Adiken Moutoussamy     2412798
- Bapu Naidu Daiva Rao   2412798
- Bahsu Muhammad Aftab   2411678

## Current implementation and setup

The frontend currently uses fictional demo data. The backend creates an SQLite database
and provides `/`, `/articles` and `/categories`. Article collection, ML training and
live dashboard integration are still to be implemented.

From the repository root on Windows (Command Prompt):

```bat
cd backend
py -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

On macOS/Linux, use `python3 -m venv venv` and `source venv/bin/activate` instead.
Open http://127.0.0.1:8000/docs to inspect the API. Starting the backend creates or
extends `backend/cyberhead.db` while keeping existing articles. The frontend remains
in demo mode; switching to API mode needs additional backend endpoints.

See [the data model and labelling rules](docs/data-model.md) for the agreed categories,
report/source relationships and database checks.

