# Spec Delta

## Purpose
Accept saved FPF match-report pages, extract their content safely and store it so that statistics stay current and every number can be traced to a source file.

## ADDED Requirements

### Requirement: Upload of FPF match reports
The system SHALL accept one or more saved FPF match-report HTML files for a chosen club and league label, and SHALL treat the file content strictly as data.

#### Scenario: Several files uploaded at once
- **WHEN** a user uploads three valid match pages for the same club
- **THEN** each match is imported independently and the response reports one outcome per file (imported, updated, needs input, or rejected)

#### Scenario: One bad file does not block the others
- **WHEN** one of several uploaded files is not an FPF match page
- **THEN** that file is rejected with a reason and the remaining files are still imported

### Requirement: Extraction of match content
The system SHALL extract from each report: competition name, match date, home and away clubs, final score, each half's end marker (including stoppage time), starting lineups, substitutes, and the timeline events (goals with running score, substitutions with the player entering and leaving, yellow cards, double-yellow cards, red cards).

#### Scenario: Date and clubs come from the report
- **WHEN** a report titled with two clubs and a date is imported
- **THEN** the stored match uses that date and those clubs, never the file name

#### Scenario: Unrecognised event icon
- **WHEN** the timeline contains an event type the system does not recognise
- **THEN** the event is not counted and a warning naming the event is stored with the match

### Requirement: Identifying the club's side
The system SHALL determine whether the tracked club is the home or away team by matching the club's registered names against the two clubs in the report, and SHALL NOT guess when neither matches.

#### Scenario: Name matches
- **WHEN** the club's registered name equals (ignoring case and accents) one of the two clubs in the report
- **THEN** that side is used

#### Scenario: Name does not match
- **WHEN** neither club in the report matches the registered names
- **THEN** the file is reported as "needs input", the user can pick the side, and may choose to remember the report's spelling as an alias for the club

### Requirement: Idempotent storage and replacement
The system SHALL identify a match by the FPF match identifier when present, otherwise by competition, date and both club names, and SHALL replace rather than duplicate a match that is uploaded again.

#### Scenario: Same match uploaded twice
- **WHEN** the same report is uploaded a second time
- **THEN** the match count does not change, the match is reported as updated, and all statistics derived from it are recomputed

#### Scenario: Different matches with the same file label
- **WHEN** two files both named "J2" describe different dates or clubs
- **THEN** they are stored as two matches

### Requirement: Source traceability
The system SHALL keep each uploaded file's original bytes with its SHA-256 hash and upload time, and SHALL record all parser warnings with the match.

#### Scenario: Audit of a match
- **WHEN** a user opens a match
- **THEN** the source file name, hash, upload time and all stored warnings are visible
