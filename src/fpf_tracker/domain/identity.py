"""Player identity inside one club: FPF id first, normalised name second, homonyms kept apart."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import norm


@dataclass
class KnownPlayer:
    id: int
    display_name: str
    fpf_id: str | None

    @property
    def key(self) -> str:
        return norm(self.display_name)


@dataclass
class Resolution:
    action: str                      # by_id | by_name | new
    player_id: int | None = None     # existing player to reuse (None -> create)
    homonym_of: list[int] = field(default_factory=list)
    note: str = ""


def resolve_player(existing: list[KnownPlayer], name: str, fpf_id: str | None) -> Resolution:
    """Decide which stored player a roster entry is. Never merges players with conflicting ids."""
    if fpf_id:
        for p in existing:
            if p.fpf_id == fpf_id:
                note = "" if p.key == norm(name) else f"spelling differs from '{p.display_name}'"
                return Resolution("by_id", p.id, note=note)
    key = norm(name)
    same_name = [p for p in existing if p.key == key]
    if fpf_id:
        id_less = [p for p in same_name if p.fpf_id is None]
        conflicting = [p for p in same_name if p.fpf_id and p.fpf_id != fpf_id]
        if len(id_less) == 1:
            return Resolution("by_name", id_less[0].id, [p.id for p in conflicting],
                              "merged by name with a record that had no FPF id")
        return Resolution("new", None, [p.id for p in same_name],
                          "same name as another player with a different FPF id" if conflicting else "")
    if len(same_name) == 1:
        return Resolution("by_name", same_name[0].id, note="merged by name (no FPF id in this report)")
    if len(same_name) > 1:
        return Resolution("new", None, [p.id for p in same_name],
                          "name matches several players and the report has no FPF id; kept separate")
    return Resolution("new")
