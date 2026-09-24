# CYBERHEAD News - Hybrid Threat Tagging

## Why threat tags were added

- A separate threat-tagging system was added because one article can contain several attack techniques at the same time.
- The ML model still gives each article one main category, while tags provide more technical detail.
- Some cybersecurity concepts are too specific to be main categories.

Examples of tags:

- Zero-Day
- SQL Injection
- Man-in-the-Middle
- Password Attack
- Credential Theft
- Brute Force
- Supply Chain
- Remote Code Execution
- Privilege Escalation
- Social Engineering

Example:

```text
Category:
Vulnerabilities

Tags:
Zero-Day
Remote Code Execution
Privilege Escalation
```

## How the tagger works

- The tagger checks several sources of evidence:
  - article title
  - beginning of the article
  - rest of the article
  - NVD vulnerability description
  - NVD CWE information
  - previously predicted ML category

- Tags are not added just because a word appears somewhere in the article.
- Each type of evidence receives a score.
- A tag is only saved when its total score is at least `4`.

## Tag scoring

```text
Evidence source                  Score

Tag found in article title       +5
Tag found in article opening     +4
Tag found later in article       +1
Tag found in NVD description     +5
Matching NVD CWE                 +6
Relevant ML category context     +5
```

Example:

```text
Article title:
"Critical SQL Injection Vulnerability"

SQL Injection in title      +5
NVD description match       +5
CWE-89 match                +6

Total score                 16

Result:
SQL Injection tag added
```

A random mention later in the article only gives:

```text
Article body mention        +1
```

Since the minimum score is `4`, this alone is not enough to create a tag. This helps reduce irrelevant tags.

## NVD and CWE support

- NVD data provides stronger technical evidence.
- Examples:
  - `CWE-89` supports `SQL Injection`
  - `CWE-269` supports `Privilege Escalation`
- NVD descriptions can also support tags such as `Remote Code Execution`.

## Content Filter

Before an article is tagged, it passes through:

```text
backend/app/content_filter.py
```

The content filter checks whether the page is suitable to be treated as a real cybersecurity incident.

It can filter content such as:

- Webinars
- Virtual events
- Sponsored/promotional content
- Press releases
- Weekly/news roundups

The filter mainly checks the article title and beginning of the article.

Example:

```text
"Webinar tomorrow: Inside real-world Google Workspace breaches"

→ detected as webinar/event
→ threat tagging skipped
```

The article is not deleted from the database. It is simply prevented from being treated as a normal threat incident.

## Database storage

Tags are stored in the:

```text
article_tags
```

table.

For each tag, the database stores:

```text
article ID
tag name
evidence score
evidence used
detection time
```

Each article also has a tagging status:

```text
pending
success
failed
```

This allows the system to know whether an article has already been processed, even when no relevant tags were found.

## Current result

- All 183 existing articles were processed.
- Tagging completed with no failures.
- Articles can have multiple tags.
- Some articles correctly receive no tags.
- Unsuitable content is skipped by the content filter.
