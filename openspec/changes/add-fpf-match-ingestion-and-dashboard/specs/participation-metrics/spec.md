# Spec Delta

## Purpose
Define call-ups, appearances and the club utilization indicators so every figure is reproducible from stored player-match records.

## ADDED Requirements

### Requirement: Player-match participation record
The system SHALL store one record for every player named in a match's official starting lineup or bench, with status Titular, Suplente utilizado or Suplente não utilizado taken from the official lists, never inferred from minutes or shirt number.

#### Scenario: Unused substitute
- **WHEN** a bench player never enters the pitch
- **THEN** the record exists with status "Suplente não utilizado" and 0 minutes

#### Scenario: Not in the squad
- **WHEN** a known player is not named in a match
- **THEN** no record exists for that match and the player counts as not called up, distinct from an unused substitute

### Requirement: Call-ups and appearances
The system SHALL count a call-up for each participation record and an appearance for each record with more than 0 minutes, so that for every player 0 ≤ appearances ≤ call-ups ≤ matches analysed.

#### Scenario: Counts per player
- **WHEN** a player is a starter in two matches, an unused substitute in one and absent from one
- **THEN** the player has 3 call-ups, 2 appearances, out of 4 matches analysed

### Requirement: Convocados que tiveram minutos
The system SHALL compute the share of squad listings that resulted in positive playing time as total appearances divided by total call-ups, pooled over all analysed matches of the selected scope, and SHALL show numerator and denominator.

#### Scenario: Regression sample
- **WHEN** the SC Braga J1–J6 matches are analysed
- **THEN** the result is 109 / 114 = 95.6%

#### Scenario: No listings
- **WHEN** the scope has no call-ups
- **THEN** the result shows N/A

### Requirement: Minutos médios por suplente convocado
The system SHALL compute the average on-pitch minutes per bench listing as the sum of minutes of all records with status Suplente utilizado or Suplente não utilizado divided by the number of such records, SHALL include unused substitutes with 0 minutes, and SHALL exclude every starter, including those later substituted off. The value is expressed in minutes and SHALL NOT be shown as a percentage.

#### Scenario: Regression sample
- **WHEN** the SC Braga J1–J6 matches are analysed
- **THEN** the result is 1,158 / 48 = 24.1 minutes, with five unused listings in the denominator

#### Scenario: Bench listed but nobody played
- **WHEN** bench players are listed and none enters
- **THEN** the result is 0.0 minutes

#### Scenario: No bench listings
- **WHEN** the scope has no bench listings
- **THEN** the result shows N/A, not 0

### Requirement: Pooled aggregation
The system SHALL compute indicators for a scope (one league or all leagues of the club) from pooled numerators and denominators, counting each player-match record once, and never by averaging percentages of matches or leagues.

#### Scenario: Two leagues of different size
- **WHEN** a club is analysed over two leagues with different numbers of listings
- **THEN** the global indicator equals total numerators divided by total denominators
