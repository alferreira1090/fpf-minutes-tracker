# Spec Delta

## Purpose
Compute, for every player named in a match squad, the playing minutes, goals and yellow cards using the FPF skill's rules, and verify the result against the match.

## ADDED Requirements

### Requirement: Match duration with stoppage time
The system SHALL compute the actual team duration T as nominal duration N plus first-half stoppage S1 plus second-half stoppage S2, where N is taken from the second-half end marker and each stoppage from the "+ added" part of the corresponding end marker.

#### Scenario: Stoppage in both halves
- **WHEN** the first half ends "40' + 1'" and the second ends "80' + 6'"
- **THEN** T is 87 minutes

#### Scenario: No first-half stoppage
- **WHEN** the first half ends "45'" and the second ends "90' + 3'"
- **THEN** T is 93 minutes

### Requirement: Player minutes
The system SHALL give each starter who finishes the match T minutes, a player substituted off at elapsed time e exactly e minutes, and a substitute who enters at elapsed time e exactly T − e minutes (less any later departure). Second-half timeline stamps SHALL be converted to elapsed time by adding S1. Stamps are whole minutes and the system SHALL use that integer convention consistently.

#### Scenario: Substitution in the second half
- **WHEN** a match has T = 93, S1 = 0, and a starter is replaced at 75'
- **THEN** the starter has 75 minutes and the substitute has 18

#### Scenario: Substitution exactly at the half-time mark
- **WHEN** a substitution is stamped at the half-length minute inside the first-half block and first-half stoppage S1 is greater than 0
- **THEN** it is treated as happening at half-time (outgoing player H + S1) and a warning marks the ambiguity

#### Scenario: Substitute used twice or unknown player
- **WHEN** a substitution names a player who is not on the bench, or not on the pitch
- **THEN** it is not applied and a warning is stored

### Requirement: Dismissals
The system SHALL end a dismissed player's playing time at the elapsed time of a red card or double-yellow card and SHALL NOT replace that player on the pitch.

#### Scenario: Red card
- **WHEN** a player receives a red card at elapsed time 60 in a match with T = 90
- **THEN** that player has 60 minutes and the match reconciliation expects 30 fewer team minutes

### Requirement: Goals
The system SHALL decide which team scored from the increase in the running score, and SHALL credit a goal to a player only when that player's team scored in a normal goal. A goal credited by name to a player of the opposing team's roster is an own goal and SHALL be counted for the club that benefited and recorded separately for the player.

#### Scenario: Normal goal
- **WHEN** the club's score rises from 1 to 2 and the scorer is in the club's squad
- **THEN** that player is credited with one goal

#### Scenario: Same name in both squads
- **WHEN** the scorer's name appears in both squads
- **THEN** the goal is credited to the squad of the team whose score increased and a warning is stored

#### Scenario: Final score disagrees
- **WHEN** the last running score differs from the report's final score
- **THEN** a warning is stored and no goals are invented

### Requirement: Yellow cards
The system SHALL count one yellow card per recorded yellow-card event and SHALL record a second-yellow dismissal icon as a dismissal plus at most one additional yellow, always with a warning that the semantics are unclear.

#### Scenario: Plain yellow
- **WHEN** a player has one yellow-card event
- **THEN** the player has 1 yellow

#### Scenario: Double yellow icon
- **WHEN** a player has a yellow-card event followed by a double-yellow event
- **THEN** the player is dismissed, has 2 recorded yellows, and the match carries a warning

### Requirement: Match reconciliation
The system SHALL compare the club's total player minutes with 11 × T minus the minutes lost to dismissals, SHALL compare team goals and roster counts with the report, and SHALL show any difference as a warning instead of adjusting figures.

#### Scenario: Consistent match
- **WHEN** all eleven players are on the pitch throughout and substitutions pair up
- **THEN** total minutes equal 11 × T and the match shows as reconciled

#### Scenario: Inconsistent match
- **WHEN** total minutes differ from the expectation
- **THEN** the match shows the expected and actual totals and the difference

### Requirement: Duration correction
The system SHALL let a user override a match's nominal duration and stoppage times, SHALL keep the originally published values visible, and SHALL reject a correction under which any timeline event falls outside the corrected match.

#### Scenario: Valid correction
- **WHEN** a user corrects a match published as 90 minutes to 80 with no stoppage and all events occur within 80 minutes
- **THEN** minutes are recomputed with T = 80 and the original 90 stays visible as a note

#### Scenario: Impossible correction
- **WHEN** a correction would make a goal at 83' fall after the final whistle
- **THEN** the correction is rejected with a message naming the conflicting event and nothing changes
