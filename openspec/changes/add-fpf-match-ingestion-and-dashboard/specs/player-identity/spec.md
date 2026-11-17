# Spec Delta

## Purpose
Recognise the same person across matches and leagues of a club so that totals are consolidated correctly and different people are never merged silently.

## ADDED Requirements

### Requirement: Identity by stable identifier, then by name
The system SHALL identify a player within a club by the FPF player identifier when the report provides one, and otherwise by normalised full name (case, accents and spacing ignored), while keeping the spelling displayed in the report.

#### Scenario: Same identifier, spelling differs
- **WHEN** two reports show the same FPF identifier with slightly different spelling
- **THEN** they are one player and the most recent spelling is displayed

#### Scenario: Same name, no identifier conflict
- **WHEN** a name matches exactly one existing player who has no conflicting identifier
- **THEN** the records are merged, and the merge is listed as "merged by name" in the identity audit

### Requirement: Homonyms are kept apart
The system SHALL treat two records with the same normalised name but different FPF identifiers as different players, and SHALL flag them in the identity audit.

#### Scenario: Two people, one name
- **WHEN** the same name appears with two different FPF identifiers within one club
- **THEN** two players exist and both are listed under "homonyms"

### Requirement: Multi-league players
The system SHALL show which players have records in more than one league of the club.

#### Scenario: Player in two leagues
- **WHEN** one player appears in matches of Sub-15 and Sub-16
- **THEN** the global summary lists one row for that player, with minutes per league and combined, and marks the player as multi-league
