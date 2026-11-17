"""SQLite storage. Facts only (matches, participation rows); totals are derived at read time."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..domain.metrics import MatchInfo, Row
from ..domain.models import norm

SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS club_aliases(
  club_id INTEGER NOT NULL REFERENCES clubs(id), alias TEXT NOT NULL, alias_norm TEXT NOT NULL,
  UNIQUE(club_id, alias_norm));
CREATE TABLE IF NOT EXISTS players(
  id INTEGER PRIMARY KEY, club_id INTEGER NOT NULL REFERENCES clubs(id),
  display_name TEXT NOT NULL, norm_name TEXT NOT NULL, fpf_id TEXT);
CREATE INDEX IF NOT EXISTS ix_players_club ON players(club_id, norm_name);
CREATE TABLE IF NOT EXISTS matches(
  id INTEGER PRIMARY KEY, club_id INTEGER NOT NULL REFERENCES clubs(id),
  fpf_match_id TEXT, competition TEXT NOT NULL, league TEXT NOT NULL, match_date TEXT NOT NULL,
  home TEXT NOT NULL, away TEXT NOT NULL, side TEXT NOT NULL, score_home INTEGER, score_away INTEGER,
  nominal INTEGER NOT NULL, s1 INTEGER NOT NULL, s2 INTEGER NOT NULL,
  pub_nominal INTEGER NOT NULL, pub_s1 INTEGER NOT NULL, pub_s2 INTEGER NOT NULL, override_json TEXT,
  goals_for INTEGER NOT NULL, goals_against INTEGER NOT NULL,
  expected_minutes INTEGER NOT NULL, actual_minutes INTEGER NOT NULL, dismissal_loss INTEGER NOT NULL,
  source_name TEXT NOT NULL, source_sha256 TEXT NOT NULL, source_path TEXT NOT NULL,
  uploaded_at TEXT NOT NULL, warnings_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS participations(
  id INTEGER PRIMARY KEY, match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES players(id), number TEXT, status TEXT NOT NULL,
  minutes INTEGER NOT NULL, minute_in INTEGER, minute_out INTEGER, goals INTEGER NOT NULL,
  own_goals INTEGER NOT NULL, yellows INTEGER NOT NULL, red INTEGER NOT NULL, goalkeeper INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ix_part_match ON participations(match_id);
CREATE TABLE IF NOT EXISTS identity_events(
  id INTEGER PRIMARY KEY, club_id INTEGER NOT NULL, match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL, action TEXT NOT NULL, note TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._keep: sqlite3.Connection | None = None
        if self.path == ":memory:":
            self._keep = sqlite3.connect(":memory:", check_same_thread=False)
            self._keep.row_factory = sqlite3.Row
        with self.connect() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = self._keep or sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:   # commit / rollback as one transaction
                yield conn
        finally:
            if self._keep is None:
                conn.close()

    # ---- clubs -----------------------------------------------------------------------------
    def get_or_create_club(self, name: str) -> int:
        name = " ".join(name.split())
        with self.connect() as c:
            row = c.execute("SELECT id FROM clubs WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
            if row:
                return row["id"]
            cur = c.execute("INSERT INTO clubs(name, created_at) VALUES (?, ?)", (name, now()))
            return cur.lastrowid

    def club_names(self, club_id: int) -> set[str]:
        with self.connect() as c:
            name = c.execute("SELECT name FROM clubs WHERE id = ?", (club_id,)).fetchone()
            aliases = c.execute("SELECT alias_norm FROM club_aliases WHERE club_id = ?", (club_id,)).fetchall()
        return ({norm(name["name"])} if name else set()) | {a["alias_norm"] for a in aliases}

    def add_alias(self, club_id: int, alias: str) -> None:
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO club_aliases(club_id, alias, alias_norm) VALUES (?,?,?)",
                      (club_id, alias, norm(alias)))

    def clubs(self) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("""
                SELECT c.id, c.name, COUNT(m.id) AS matches, MAX(m.uploaded_at) AS last_update,
                       COUNT(DISTINCT m.league) AS leagues
                FROM clubs c LEFT JOIN matches m ON m.club_id = c.id GROUP BY c.id ORDER BY c.name""").fetchall()
        return [dict(r) for r in rows]

    def club(self, club_id: int) -> dict | None:
        with self.connect() as c:
            r = c.execute("SELECT * FROM clubs WHERE id = ?", (club_id,)).fetchone()
        return dict(r) if r else None

    # ---- matches ---------------------------------------------------------------------------
    def find_match(self, club_id: int, fpf_match_id: str | None, competition: str, date: str,
                   home: str, away: str) -> dict | None:
        with self.connect() as c:
            if fpf_match_id:
                r = c.execute("SELECT * FROM matches WHERE club_id=? AND fpf_match_id=?", (club_id, fpf_match_id)).fetchone()
                if r:
                    return dict(r)
            r = c.execute("""SELECT * FROM matches WHERE club_id=? AND competition=? AND match_date=?
                             AND home=? AND away=?""", (club_id, competition, date, home, away)).fetchone()
        return dict(r) if r else None

    def match(self, match_id: int) -> dict | None:
        with self.connect() as c:
            r = c.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["warnings"] = json.loads(d.pop("warnings_json"))
        d["override"] = json.loads(d["override_json"]) if d["override_json"] else None
        return d

    def matches(self, club_id: int, league: str | None = None) -> list[dict]:
        q = "SELECT * FROM matches WHERE club_id = ?"
        args: list = [club_id]
        if league:
            q += " AND league = ?"
            args.append(league)
        with self.connect() as c:
            rows = c.execute(q + " ORDER BY match_date, id", args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["warnings"] = json.loads(d.pop("warnings_json"))
            d["opponent"] = d["away"] if d["side"] == "home" else d["home"]
            out.append(d)
        return out

    def leagues(self, club_id: int) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("""SELECT league, COUNT(*) AS matches, MIN(match_date) AS first, MAX(match_date) AS last
                                FROM matches WHERE club_id=? GROUP BY league ORDER BY league""", (club_id,)).fetchall()
        return [dict(r) for r in rows]

    def participations(self, match_id: int) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("""SELECT p.*, pl.display_name FROM participations p JOIN players pl ON pl.id = p.player_id
                                WHERE p.match_id = ? ORDER BY CASE p.status WHEN 'Titular' THEN 0 WHEN 'Suplente utilizado' THEN 1 ELSE 2 END,
                                CAST(p.number AS INTEGER)""", (match_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---- players / identity ------------------------------------------------------------------
    def club_players(self, club_id: int) -> list[dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,)).fetchall()]

    def identity_audit(self, club_id: int) -> dict:
        with self.connect() as c:
            groups = c.execute("""SELECT norm_name, COUNT(*) AS n FROM players WHERE club_id=? GROUP BY norm_name HAVING n > 1""",
                               (club_id,)).fetchall()
            homonyms = []
            for g in groups:
                ps = c.execute("SELECT id, display_name, fpf_id FROM players WHERE club_id=? AND norm_name=?",
                               (club_id, g["norm_name"])).fetchall()
                homonyms.append([dict(p) for p in ps])
            merges = c.execute("""SELECT e.action, e.note, pl.display_name, m.match_date, m.home, m.away
                                  FROM identity_events e JOIN players pl ON pl.id = e.player_id JOIN matches m ON m.id = e.match_id
                                  WHERE e.club_id=? AND e.action='by_name' ORDER BY m.match_date""", (club_id,)).fetchall()
            multi = c.execute("""SELECT pl.id, pl.display_name, GROUP_CONCAT(DISTINCT m.league) AS leagues
                                 FROM players pl JOIN participations p ON p.player_id = pl.id JOIN matches m ON m.id = p.match_id
                                 WHERE pl.club_id=? GROUP BY pl.id HAVING COUNT(DISTINCT m.league) > 1""", (club_id,)).fetchall()
        return {"homonyms": homonyms, "merged_by_name": [dict(r) for r in merges], "multi_league": [dict(r) for r in multi]}

    # ---- derived inputs for the pure metrics layer ----------------------------------------------
    def metric_rows(self, club_id: int, league: str | None = None) -> list[Row]:
        q = """SELECT p.player_id, pl.display_name, m.league, p.match_id, p.status, p.minutes, p.goals, p.yellows
               FROM participations p JOIN players pl ON pl.id = p.player_id JOIN matches m ON m.id = p.match_id
               WHERE m.club_id = ?"""
        args: list = [club_id]
        if league:
            q += " AND m.league = ?"
            args.append(league)
        with self.connect() as c:
            rows = c.execute(q, args).fetchall()
        return [Row(r["player_id"], r["display_name"], r["league"], r["match_id"], r["status"], r["minutes"], r["goals"], r["yellows"])
                for r in rows]

    def match_infos(self, club_id: int, league: str | None = None) -> list[MatchInfo]:
        return [MatchInfo(m["id"], m["league"], m["match_date"], m["opponent"], m["nominal"] + m["s1"] + m["s2"])
                for m in self.matches(club_id, league)]
