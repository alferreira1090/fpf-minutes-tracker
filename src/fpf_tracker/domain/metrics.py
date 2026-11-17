"""Aggregations over stored player-match participation records (pure functions).

Equivalent of the Excel SUMIF formulas: totals are always derived from the records, never stored.
"""
from __future__ import annotations

from dataclasses import dataclass

STARTER = "Titular"
SUB_USED = "Suplente utilizado"
SUB_UNUSED = "Suplente não utilizado"


@dataclass(frozen=True)
class Row:
    """One player in one match's official squad (so convocado is always 1)."""
    player_id: int
    player_name: str
    league: str
    match_id: int
    status: str
    minutes: int
    goals: int
    yellows: int

    @property
    def played(self) -> int:
        return 1 if self.minutes > 0 else 0


@dataclass(frozen=True)
class MatchInfo:
    id: int
    league: str
    date: str
    opponent: str
    duration: int


def indicators(rows: list[Row]) -> dict:
    callups = len(rows)
    appearances = sum(r.played for r in rows)
    bench = [r for r in rows if r.status in (SUB_USED, SUB_UNUSED)]
    bench_minutes = sum(r.minutes for r in bench)
    return {
        "with_minutes": {
            "numerator": appearances, "denominator": callups,
            "value": appearances / callups if callups else None,
        },
        "bench_minutes": {
            "numerator": bench_minutes, "denominator": len(bench),
            "value": bench_minutes / len(bench) if bench else None,
            "unused": sum(1 for r in bench if r.status == SUB_UNUSED),
        },
    }


def league_table(rows: list[Row], matches: list[MatchInfo]) -> dict:
    ms = sorted(matches, key=lambda m: (m.date, m.id))
    possible = sum(m.duration for m in ms)
    by_player: dict[int, list[Row]] = {}
    for r in rows:
        by_player.setdefault(r.player_id, []).append(r)
    players = []
    for pid, prs in by_player.items():
        cells = {r.match_id: {"minutes": r.minutes, "status": r.status} for r in prs}
        total = sum(r.minutes for r in prs)
        players.append({
            "player_id": pid, "name": prs[0].player_name, "cells": cells,
            "minutes": total, "possible": possible, "pct": total / possible if possible else None,
            "goals": sum(r.goals for r in prs), "yellows": sum(r.yellows for r in prs),
            "appearances": sum(r.played for r in prs), "callups": len(prs),
            "starts": sum(1 for r in prs if r.status == STARTER),
        })
    players.sort(key=lambda p: (-p["minutes"], p["name"].lower()))
    return {"matches": ms, "possible": possible, "players": players, "indicators": indicators(rows)}


def global_summary(rows: list[Row], leagues: list[str], matches_by_league: dict[str, int]) -> dict:
    by_player: dict[int, list[Row]] = {}
    for r in rows:
        by_player.setdefault(r.player_id, []).append(r)
    players = []
    for pid, prs in by_player.items():
        per = {lg: sum(r.minutes for r in prs if r.league == lg) for lg in leagues}
        in_leagues = sorted({r.league for r in prs})
        players.append({
            "player_id": pid, "name": prs[0].player_name, "minutes_by_league": per,
            "minutes": sum(r.minutes for r in prs), "goals": sum(r.goals for r in prs),
            "yellows": sum(r.yellows for r in prs), "appearances": sum(r.played for r in prs),
            "callups": len(prs), "leagues": in_leagues, "multi_league": len(in_leagues) > 1,
            "matches_analysed": sum(matches_by_league.get(lg, 0) for lg in leagues),
        })
    players.sort(key=lambda p: (-p["minutes"], p["name"].lower()))
    return {"leagues": leagues, "players": players, "indicators": indicators(rows)}


def check_invariants(rows: list[Row], matches_analysed_by_league: dict[str, int]) -> list[str]:
    """0 <= appearances <= call-ups <= matches analysed, per league and player."""
    problems = []
    per: dict[tuple[int, str], list[Row]] = {}
    for r in rows:
        per.setdefault((r.player_id, r.league), []).append(r)
    for (pid, lg), prs in per.items():
        app, calls = sum(r.played for r in prs), len(prs)
        if not (0 <= app <= calls <= matches_analysed_by_league.get(lg, 0)):
            problems.append(f"player {pid} in {lg}: appearances={app}, callups={calls}, matches={matches_analysed_by_league.get(lg, 0)}")
    return problems
