# Tasks

## 1. Project skeleton

- [x] 1.1 Python package `fpf_tracker` (src layout), `pyproject.toml`, `.gitignore` (ignores `data/`), `README.md`. Verify: `pip install -e .` then `python -c "import fpf_tracker"`.
- [x] 1.2 Synthetic FPF page builder for tests (`tests/fpf_fixture.py`). Verify: builder output parses in task 2.

## 2. Parsing (match-ingestion)

- [x] 2.1 Parser extracting metadata, rosters (with FPF player ids), period blocks, end markers and events with warnings for unknown icons. Verify: `tests/test_parser.py`.
- [x] 2.2 Reject non-FPF pages with a clear reason. Verify: `test_parser.py::test_rejects_non_fpf`.

## 3. Calculation (minutes-calculation)

- [x] 3.1 Duration model (N, S1, S2, T) and stamp → elapsed conversion. Verify: T = 87 and T = 93 scenarios in `tests/test_minutes.py`.
- [x] 3.2 Player minutes with state-based substitution attribution, half-time rule, dismissals. Verify: hand-computed match totals 1023 = 11 × 93; red-card scenario.
- [x] 3.3 Goals (increment-based, own goals, homonyms), yellow cards, double-yellow warning. Verify: `test_minutes.py` goal and card scenarios.
- [x] 3.4 Reconciliation (minutes, goals, roster counts) and duration override with impossible-timeline rejection. Verify: `test_minutes.py` correction scenarios.

## 4. Identity and metrics (player-identity, participation-metrics)

- [x] 4.1 Identity resolution (id → name, homonyms, audit list). Verify: `tests/test_identity.py`.
- [x] 4.2 Participation statuses, call-ups, appearances, both indicators with pooled aggregation and N/A rules. Verify: `tests/test_metrics.py` including a synthetic reproduction of the 95.6% / 24.1 min regression shape and the invariant 0 ≤ appearances ≤ call-ups ≤ matches.

## 5. Storage and ingestion service

- [x] 5.1 SQLite schema and repository; replace-on-reupload in one transaction; source file bytes + SHA-256 stored. Verify: `tests/test_ingest.py` (same match twice → one match; two "J2" → two matches).
- [x] 5.2 Ingestion service: side detection with aliases, "needs input" outcome, per-file outcomes. Verify: `test_ingest.py`.

## 6. Web app (stats-dashboard)

- [x] 6.1 Routes: overview, upload (multi-file), resolve side, club, league, global, matches, match audit, duration correction, identity audit. Verify: `tests/test_web.py` with FastAPI TestClient.
- [x] 6.2 pt-PT templates in the dark editorial style: heat-mapped league table, global summary, indicator block with numerator/denominator. Verify: render in a browser and screenshot inspection.
- [x] 6.3 JSON API under `/api` equal to page figures. Verify: `test_web.py::test_api_matches_pages`.
- [x] 6.4 Escaping of report-derived text. Verify: `test_web.py::test_hostile_name_is_escaped`.

## 7. Delivery

- [x] 7.1 README: run instructions, OpenSpec workflow, data/privacy note. Verify: fresh-clone run per README.
- [x] 7.2 Run the full test suite and `openspec validate --strict`. Verify: both pass.
- [ ] 7.3 Initial commit on `main`; remote connected when the user supplies a repository. Verify: `git log` shows the commit.

## Workflow follow-up

- Archive the change after review: `openspec archive add-fpf-match-ingestion-and-dashboard`.
- Next proposed changes: authentication, Excel export, identity merge UI, self-hosted fonts.
