# Proposal

## Why

Player-minute tracking for the FC Famalicão youth sides and SC Braga currently lives in an Excel workbook
produced by the FPF skill. Every new match means re-running the skill and re-sending a file. A web app lets
coaches and staff open the current numbers at any time and refresh them by uploading the saved FPF match
page, with the same calculation rules and the same auditability.

## What Changes

- New web application with a JSON API and server-rendered pages, backed by a local database.
- Upload of one or many saved FPF match-report HTML files; each is parsed, validated, stored and the
  statistics are updated. Re-uploading the same match replaces its data (idempotent).
- Minutes, call-ups, appearances, goals and yellow cards computed with the FPF skill rules, including
  stoppage time, half-time substitutions, dismissals and per-match duration corrections.
- Player identity resolution across leagues without silently merging different people.
- Dashboard per club: one view per league (players × matches), a global summary across leagues, and the two
  club utilization indicators, each showing numerator and denominator.
- Per-match audit page: reconciliation (Σ minutes vs 11 × duration), warnings and duration correction.
- Repository set up with OpenSpec, tests and a pt-PT user interface.

**Out of scope (later changes):** user accounts and authentication, Excel export, fetching match pages from
the FPF site, editing player identities by hand, multi-club tenancy and roles, hosted deployment.

## Capabilities

### New Capabilities
- `match-ingestion`: upload, parsing, validation and idempotent storage of FPF match reports.
- `minutes-calculation`: playing minutes, goals and cards per player-match, plus match reconciliation and corrections.
- `player-identity`: resolving the same person across matches and leagues, and flagging homonyms.
- `participation-metrics`: call-up and appearance counts and the two club utilization indicators.
- `stats-dashboard`: league views, global summary, indicator block and match audit pages.

### Modified Capabilities
<!-- none: greenfield -->

## Impact

- New codebase (Python package, SQLite database, HTML templates, tests). No existing system is changed.
- Reuses the HTML-extraction approach of the FPF skill's `extract_fpf_match.py`.
- Adds the privacy requirement that data on minors must not be exposed publicly; v0.1 binds to localhost only.
