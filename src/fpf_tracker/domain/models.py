"""Plain data structures shared by the pure domain layer."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def norm(value: str) -> str:
    """Normalised comparison key: accents, case and spacing ignored."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", stripped).strip()


class MatchDataError(ValueError):
    """The report cannot be used (not an FPF page, incomplete timeline, impossible correction)."""


@dataclass(frozen=True)
class Warn:
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


@dataclass
class RosterPlayer:
    number: str
    name: str
    goalkeeper: bool
    fpf_id: str | None
    roster_goals: int = 0


@dataclass
class Event:
    period: int            # 1-based index of the timeline block
    base: int              # stamp minute, e.g. 75 in "75'" or 90 in "90' + 3'"
    added: int             # stoppage part, e.g. 3 in "90' + 3'"
    type: str              # goal | substitution | yellow | double_yellow | red | unknown
    icon: str
    label: str
    running_score: tuple[int, int] | None = None
    scorer: str | None = None
    player: str | None = None
    in_name: str | None = None
    out_name: str | None = None


@dataclass
class Period:
    title: str
    end_base: int | None
    end_added: int


@dataclass
class ParsedMatch:
    source_name: str
    fpf_match_id: str | None
    competition: str
    date: str              # ISO yyyy-mm-dd
    home: str
    away: str
    score: tuple[int, int] | None
    periods: list[Period]
    starters: dict[str, list[RosterPlayer]]      # side -> players
    substitutes: dict[str, list[RosterPlayer]]
    events: list[Event]
    warnings: list[Warn] = field(default_factory=list)
