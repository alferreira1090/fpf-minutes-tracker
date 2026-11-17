"""Orchestrates parse -> compute -> identity -> store for one uploaded FPF page."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.identity import KnownPlayer, resolve_player
from ..domain.minutes import MatchComputation, compute_match
from ..domain.models import MatchDataError, ParsedMatch, norm
from ..domain.parser import parse_fpf_html
from ..storage.db import Database, now


@dataclass
class Outcome:
    filename: str
    status: str                     # imported | updated | needs_side | rejected
    message: str = ""
    match_id: int | None = None
    sha: str | None = None
    warnings: int = 0
    home: str = ""
    away: str = ""
    league: str | None = None


class IngestService:
    def __init__(self, db: Database, upload_dir: str | Path):
        self.db = db
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # -- public API -------------------------------------------------------------------------------
    def import_file(self, club_id: int, filename: str, data: bytes, league_label: str | None = None,
                    side: str | None = None, remember_alias: bool = False) -> Outcome:
        sha = hashlib.sha256(data).hexdigest()
        try:
            parsed = parse_fpf_html(data, filename)
        except MatchDataError as exc:
            return Outcome(filename, "rejected", str(exc), sha=sha)

        chosen = side
        if chosen is None:
            names = self.db.club_names(club_id)
            in_home, in_away = norm(parsed.home) in names, norm(parsed.away) in names
            if in_home != in_away:
                chosen = "home" if in_home else "away"
        if chosen is None:
            self._store_source(sha, data)
            return Outcome(filename, "needs_side",
                           "Não foi possível saber qual das equipas é o clube. Escolha o lado.",
                           sha=sha, home=parsed.home, away=parsed.away, league=league_label)
        if remember_alias:
            self.db.add_alias(club_id, parsed.home if chosen == "home" else parsed.away)
        try:
            return self._store(club_id, parsed, chosen, data, sha, league_label)
        except MatchDataError as exc:
            return Outcome(filename, "rejected", str(exc), sha=sha)

    def resolve_side(self, club_id: int, sha: str, filename: str, side: str, remember_alias: bool,
                     league_label: str | None) -> Outcome:
        path = self.upload_dir / f"{sha}.html"
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            return Outcome(filename, "rejected", "Ficheiro original não encontrado; carregue-o novamente.", sha=sha)
        return self.import_file(club_id, filename, path.read_bytes(), league_label, side, remember_alias)

    def correct_duration(self, match_id: int, nominal: int | None, s1: int | None, s2: int | None) -> MatchComputation:
        """Re-run a stored match with a duration correction; raises MatchDataError and changes nothing if impossible."""
        m = self.db.match(match_id)
        if m is None:
            raise MatchDataError("Jogo não encontrado.")
        data = Path(m["source_path"]).read_bytes()
        parsed = parse_fpf_html(data, m["source_name"])
        override = {"nominal": nominal, "s1": s1, "s2": s2}
        comp = compute_match(parsed, m["side"], override)
        self._write(m["club_id"], parsed, comp, data, m["source_sha256"], m["league"], override if comp.corrected else None,
                    existing_id=m["id"])
        return comp

    def clear_correction(self, match_id: int) -> MatchComputation:
        m = self.db.match(match_id)
        if m is None:
            raise MatchDataError("Jogo não encontrado.")
        data = Path(m["source_path"]).read_bytes()
        parsed = parse_fpf_html(data, m["source_name"])
        comp = compute_match(parsed, m["side"])
        self._write(m["club_id"], parsed, comp, data, m["source_sha256"], m["league"], None, existing_id=m["id"])
        return comp

    # -- internals -----------------------------------------------------------------------------
    def _store_source(self, sha: str, data: bytes) -> Path:
        path = self.upload_dir / f"{sha}.html"
        if not path.exists():
            path.write_bytes(data)
        return path

    def _store(self, club_id, parsed: ParsedMatch, side: str, data: bytes, sha: str, league_label: str | None) -> Outcome:
        existing = self.db.find_match(club_id, parsed.fpf_match_id, parsed.competition, parsed.date, parsed.home, parsed.away)
        override = json.loads(existing["override_json"]) if existing and existing["override_json"] else None
        comp = compute_match(parsed, side, override)
        league = league_label or (existing["league"] if existing else None) or parsed.competition or "Sem competição"
        match_id = self._write(club_id, parsed, comp, data, sha, league, override if comp.corrected else None,
                               existing_id=existing["id"] if existing else None)
        return Outcome(parsed.source_name, "updated" if existing else "imported",
                       "Jogo atualizado." if existing else "Jogo importado.", match_id=match_id, sha=sha,
                       warnings=len(comp.warnings), home=parsed.home, away=parsed.away, league=league)

    def _write(self, club_id: int, parsed: ParsedMatch, comp: MatchComputation, data: bytes, sha: str,
               league: str, override: dict | None, existing_id: int | None) -> int:
        path = self._store_source(sha, data)
        with self.db.connect() as c:
            vals = (
                club_id, parsed.fpf_match_id, parsed.competition, league, parsed.date, parsed.home, parsed.away, comp.side,
                parsed.score[0] if parsed.score else None, parsed.score[1] if parsed.score else None,
                comp.duration.nominal, comp.duration.s1, comp.duration.s2,
                comp.published.nominal, comp.published.s1, comp.published.s2,
                json.dumps(override) if override else None, comp.goals_for, comp.goals_against,
                comp.expected_minutes, comp.actual_minutes, comp.dismissal_loss,
                parsed.source_name, sha, str(path), now(), json.dumps([w.to_dict() for w in comp.warnings]),
            )
            cols = ("club_id, fpf_match_id, competition, league, match_date, home, away, side, score_home, score_away, "
                    "nominal, s1, s2, pub_nominal, pub_s1, pub_s2, override_json, goals_for, goals_against, "
                    "expected_minutes, actual_minutes, dismissal_loss, source_name, source_sha256, source_path, uploaded_at, warnings_json")
            if existing_id:
                sets = ", ".join(f"{k.strip()} = ?" for k in cols.split(","))
                c.execute(f"UPDATE matches SET {sets} WHERE id = ?", (*vals, existing_id))
                c.execute("DELETE FROM participations WHERE match_id = ?", (existing_id,))
                c.execute("DELETE FROM identity_events WHERE match_id = ?", (existing_id,))
                match_id = existing_id
            else:
                marks = ",".join("?" * len(vals))
                match_id = c.execute(f"INSERT INTO matches({cols}) VALUES ({marks})", vals).lastrowid

            known = [KnownPlayer(r["id"], r["display_name"], r["fpf_id"]) for r in
                     c.execute("SELECT id, display_name, fpf_id FROM players WHERE club_id = ?", (club_id,)).fetchall()]
            seen: set[int] = set()
            for pr in comp.players:
                res = resolve_player(known, pr.name, pr.fpf_id)
                if res.player_id is None or res.player_id in seen:
                    # new player (or the same person listed twice in one squad, which would break the 1 row/match rule)
                    if res.player_id in seen:
                        continue
                    pid = c.execute("INSERT INTO players(club_id, display_name, norm_name, fpf_id) VALUES (?,?,?,?)",
                                    (club_id, pr.name, norm(pr.name), pr.fpf_id)).lastrowid
                    known.append(KnownPlayer(pid, pr.name, pr.fpf_id))
                else:
                    pid = res.player_id
                    c.execute("UPDATE players SET display_name = ?, norm_name = ?, fpf_id = COALESCE(fpf_id, ?) WHERE id = ?",
                              (pr.name, norm(pr.name), pr.fpf_id, pid))
                    for k in known:
                        if k.id == pid:
                            k.display_name, k.fpf_id = pr.name, k.fpf_id or pr.fpf_id
                if res.action != "by_id" or res.note or res.homonym_of:
                    note = res.note + (f" (homónimos: {res.homonym_of})" if res.homonym_of else "")
                    c.execute("INSERT INTO identity_events(club_id, match_id, player_id, action, note) VALUES (?,?,?,?,?)",
                              (club_id, match_id, pid, res.action, note.strip()))
                seen.add(pid)
                c.execute("""INSERT INTO participations(match_id, player_id, number, status, minutes, minute_in, minute_out,
                             goals, own_goals, yellows, red, goalkeeper) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (match_id, pid, pr.number, pr.status, pr.minutes, pr.minute_in, pr.minute_out,
                           pr.goals, pr.own_goals, pr.yellows, int(pr.red), int(pr.goalkeeper)))
        return match_id
