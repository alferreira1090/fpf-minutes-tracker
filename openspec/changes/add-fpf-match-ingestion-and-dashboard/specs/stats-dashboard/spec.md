# Spec Delta

## Purpose
Show the club's statistics in the browser as the Excel tracker did: one view per league, a global summary and the utilization indicators, with an audit page for each match.

## ADDED Requirements

### Requirement: Club overview and navigation
The system SHALL list the registered clubs with their leagues, number of matches and last update, and SHALL lead from each club to its league views, global summary, matches list and upload page. The interface text SHALL be in European Portuguese.

#### Scenario: Empty state
- **WHEN** no match has been uploaded
- **THEN** the overview invites the user to upload the first match report

### Requirement: League view
The system SHALL show, for a league, players as rows and matches as columns (labelled with opponent and date, in date order), with total minutes, percentage of possible minutes, goals, yellow cards, appearances and call-ups per player. Cells SHALL show minutes, and SHALL distinguish "not called up" from "called up, 0 minutes".

#### Scenario: Colour scale per match
- **WHEN** a match lasted T minutes
- **THEN** a cell is coloured red at 0 minutes, amber at T/2 and green at T, interpolated between, and total minutes use a scale based on total possible minutes

#### Scenario: Unused substitute vs. not called up
- **WHEN** a player was an unused substitute in one match and absent from another
- **THEN** the first cell shows 0 with an "unused substitute" marker and the second shows a dash

#### Scenario: Sorting
- **WHEN** the user clicks a column header
- **THEN** the rows are sorted by that column

### Requirement: Global summary
The system SHALL show one row per verified player with minutes per league and combined, goals, yellow cards, appearances and call-ups, and SHALL flag multi-league players.

#### Scenario: Totals agree with league views
- **WHEN** the global summary is shown
- **THEN** each player's combined minutes equal the sum of that player's minutes in the league views

### Requirement: Club indicator block
The system SHALL show both club utilization indicators for a selected scope (all leagues or one league) with result, numerator, denominator and a short definition, stating that unused substitutes are included.

#### Scenario: Scope switch
- **WHEN** the user selects a single league
- **THEN** both indicators are recomputed for that league only

### Requirement: Match audit page
The system SHALL show for each match the header data, duration breakdown (nominal, stoppage, total, and any correction), per-player minutes with status and entry/exit times, the reconciliation result, all warnings, and a form to correct the duration.

#### Scenario: Warnings visible
- **WHEN** a match was imported with warnings
- **THEN** the match list marks it and the audit page lists every warning

### Requirement: Machine-readable access
The system SHALL expose the league view, global summary and indicators as JSON under an `/api` path with the same figures as the pages.

#### Scenario: API matches page
- **WHEN** the JSON for a league is requested
- **THEN** every total equals the value shown in the league view

### Requirement: Personal-data safeguards
The system SHALL by default accept connections only from the local machine, SHALL escape all report-derived text when rendering, and SHALL NOT load third-party analytics.

#### Scenario: Hostile content in a report
- **WHEN** a report contains markup or script in a player name
- **THEN** it is displayed as text and never executed
