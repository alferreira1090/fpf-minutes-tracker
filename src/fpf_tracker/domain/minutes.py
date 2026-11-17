"""Playing minutes, goals and cards for one match, following the FPF skill rules.

Time model (integer minutes): first-half stamps -> base + added; second-half stamps -> base + added + S1.
Actual duration T = N + S1 + S2. Substitutions, cards and goals are attributed by simulating both squads,
never by name alone (opposing squads can contain the same name).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Event, MatchDataError, ParsedMatch, RosterPlayer, Warn, norm

STARTER = "Titular"
SUB_USED = "Suplente utilizado"
SUB_UNUSED = "Suplente não utilizado"


@dataclass(frozen=True)
class Duration:
    nominal: int
    s1: int
    s2: int

    @property
    def half(self) -> int:
        return self.nominal // 2

    @property
    def total(self) -> int:
        return self.nominal + self.s1 + self.s2

    def to_dict(self) -> dict:
        return {"nominal": self.nominal, "s1": self.s1, "s2": self.s2, "total": self.total}


@dataclass
class PlayerResult:
    number: str
    name: str
    fpf_id: str | None
    goalkeeper: bool
    status: str
    minutes: int = 0
    minute_in: int | None = None
    minute_out: int | None = None
    goals: int = 0
    own_goals: int = 0
    yellows: int = 0
    red: bool = False
    roster_goals: int = 0


@dataclass
class MatchComputation:
    side: str
    opponent: str
    published: Duration
    duration: Duration
    corrected: bool
    players: list[PlayerResult]
    goals_for: int
    goals_against: int
    expected_minutes: int
    actual_minutes: int
    dismissal_loss: int
    warnings: list[Warn] = field(default_factory=list)

    @property
    def reconciled(self) -> bool:
        return self.expected_minutes == self.actual_minutes


class _Team:
    def __init__(self, starters: list[RosterPlayer], subs: list[RosterPlayer]):
        self.on: dict[str, PlayerResult] = {}
        self.bench: dict[str, PlayerResult] = {}
        self.gone: dict[str, PlayerResult] = {}
        self.all: dict[str, PlayerResult] = {}
        self.order: list[PlayerResult] = []
        for rp, status, target in [(p, STARTER, self.on) for p in starters] + [(p, SUB_UNUSED, self.bench) for p in subs]:
            res = PlayerResult(rp.number, rp.name, rp.fpf_id, rp.goalkeeper, status, roster_goals=rp.roster_goals)
            if status == STARTER:
                res.minute_in = 0
            key = norm(rp.name)
            self.order.append(res)
            if key in self.all:
                continue  # duplicate name inside one squad: first wins; warned by caller
            self.all[key] = res
            target[key] = res


def _published_duration(parsed: ParsedMatch, warnings: list[Warn]) -> Duration:
    ends = parsed.periods
    if len(ends) < 2 or ends[0].end_base is None or ends[1].end_base is None:
        raise MatchDataError("Timeline incomplete: end markers of both halves are required to compute minutes.")
    half, s1 = ends[0].end_base, ends[0].end_added
    n, s2 = ends[1].end_base, ends[1].end_added
    if ends[1].end_added == 0 and n > 2 * half:
        s2 = n - 2 * half
        n = 2 * half
        warnings.append(Warn("end_marker_format", f"Second-half end shown as {n + s2}'; read as {n}' + {s2}'."))
    if 2 * half != n:
        warnings.append(Warn("half_length_mismatch", f"First half ends at {half}' but nominal duration is {n}'; using {n}'."))
    if len(ends) > 2:
        warnings.append(Warn(
            "extra_period_blocks",
            f"{len(ends)} timeline blocks found; blocks after the second are read as second-half time. "
            "Verify (the page may contain an erroneous extra-time block)."))
    if n % 2:
        warnings.append(Warn("odd_nominal_duration", f"Nominal duration {n}' is odd; half length rounded down."))
    return Duration(n, s1, s2)


def _elapsed(ev: Event, d: Duration, warnings: list[Warn]) -> int:
    if ev.period == 1:
        e = ev.base + ev.added
        if ev.type == "substitution" and ev.base == d.half and ev.added == 0 and d.s1 > 0:
            warnings.append(Warn(
                "halftime_substitution_ambiguous",
                f"Substitution at {ev.base}' ({ev.in_name} for {ev.out_name}) may have happened before the "
                f"{d.s1}' of first-half stoppage or at half-time; treated as half-time. Check manually."))
            return d.half + d.s1
        return e
    return ev.base + ev.added + d.s1


def _check_bounds(ev: Event, e: int, d: Duration, strict: bool, warnings: list[Warn]) -> None:
    lo, hi = (0, d.half + d.s1) if ev.period == 1 else (d.half + d.s1, d.total)
    if lo <= e <= hi:
        return
    stamp = f"{ev.base}'" + (f" + {ev.added}'" if ev.added else "")
    desc = f"{ev.type} at {stamp} ({ev.label or ev.in_name or ev.player})"
    if strict:
        raise MatchDataError(
            f"Duration correction rejected: {desc} falls outside the corrected match "
            f"(T = {d.total} min, first half {d.half}' + {d.s1}')."
        )
    warnings.append(Warn("event_outside_match", f"{desc} lies outside the match timeline (T = {d.total})."))


def compute_match(
    parsed: ParsedMatch, side: str, override: dict | None = None
) -> MatchComputation:
    """Compute the tracked club's statistics. `side` is 'home' or 'away'.

    `override` may carry nominal / s1 / s2 integers replacing the published values.
    """
    if side not in ("home", "away"):
        raise ValueError("side must be 'home' or 'away'")
    warnings: list[Warn] = list(parsed.warnings)
    published = _published_duration(parsed, warnings)
    d = published
    corrected = False
    if override:
        d = Duration(
            int(override.get("nominal") if override.get("nominal") is not None else published.nominal),
            int(override.get("s1") if override.get("s1") is not None else published.s1),
            int(override.get("s2") if override.get("s2") is not None else published.s2),
        )
        corrected = d != published
        if d.nominal <= 0 or d.s1 < 0 or d.s2 < 0:
            raise MatchDataError("Duration correction rejected: values must be positive.")
    strict = corrected

    other = "away" if side == "home" else "home"
    teams = {
        side: _Team(parsed.starters[side], parsed.substitutes[side]),
        other: _Team(parsed.starters[other], parsed.substitutes[other]),
    }
    for s, t in teams.items():
        if len(t.all) != len(t.order):
            warnings.append(Warn("duplicate_name_in_squad", f"Two players share the same name in the {s} squad; events are attributed to the first."))
    if len(parsed.starters[side]) != 11:
        warnings.append(Warn("starters_count", f"{len(parsed.starters[side])} starters listed for the club (expected 11)."))

    score = (0, 0)
    goals_for = {"home": 0, "away": 0}
    dq_loss = 0

    def holders(name: str, want_on_pitch: bool):
        k = norm(name)
        out = []
        for s, t in teams.items():
            pool = t.on if want_on_pitch else t.all
            if k in pool:
                out.append((s, t, pool[k]))
        return out

    for ev in parsed.events:
        e = _elapsed(ev, d, warnings)
        _check_bounds(ev, e, d, strict, warnings)

        if ev.type == "substitution":
            kin, kout = norm(ev.in_name or ""), norm(ev.out_name or "")
            valid = [(s, t) for s, t in teams.items() if kin in t.bench and kout in t.on]
            if len(valid) == 1:
                s, t = valid[0]
                p_in, p_out = t.bench.pop(kin), t.on.pop(kout)
                p_in.status, p_in.minute_in = SUB_USED, e
                p_out.minute_out = e
                t.on[kin] = p_in
                t.gone[kout] = p_out
            elif len(valid) > 1:
                warnings.append(Warn("ambiguous_substitution", f"Substitution {ev.in_name} for {ev.out_name} fits both squads; not applied."))
            else:
                warnings.append(Warn("substitution_unmatched", f"Substitution {ev.in_name} for {ev.out_name} at {ev.base}' does not fit any squad state; not applied."))

        elif ev.type == "goal":
            if ev.running_score is None:
                warnings.append(Warn("goal_without_score", f"Goal at {ev.base}' has no running score; not counted."))
                continue
            dh, da = ev.running_score[0] - score[0], ev.running_score[1] - score[1]
            if (dh > 0) == (da > 0) or dh < 0 or da < 0:
                warnings.append(Warn("score_inconsistent", f"Running score {ev.running_score} after {score} at {ev.base}' is inconsistent; goal not counted."))
                continue
            score = ev.running_score
            scoring = "home" if dh > 0 else "away"
            goals_for[scoring] += max(dh, da)
            if max(dh, da) > 1:
                warnings.append(Warn("multiple_goals_one_event", f"Score jumps by {max(dh, da)} at {ev.base}'; one scorer credited."))
            k = norm(ev.scorer or "")
            opp = "away" if scoring == "home" else "home"
            in_scoring, in_other = k in teams[scoring].all, k in teams[opp].all
            if in_scoring:
                if in_other:
                    warnings.append(Warn("homonym_goal", f"'{ev.scorer}' is in both squads; goal credited to the team whose score increased."))
                teams[scoring].all[k].goals += 1
            elif in_other:
                teams[opp].all[k].own_goals += 1
                warnings.append(Warn("own_goal", f"{ev.scorer} scored an own goal at {ev.base}'."))
            else:
                warnings.append(Warn("scorer_not_in_squad", f"Scorer '{ev.scorer}' is in neither squad."))

        elif ev.type in ("yellow", "double_yellow", "red"):
            cands = holders(ev.player or "", want_on_pitch=True) or holders(ev.player or "", want_on_pitch=False)
            if len(cands) != 1:
                code = "ambiguous_card" if cands else "card_player_not_found"
                warnings.append(Warn(code, f"{ev.type} for '{ev.player}' at {ev.base}' could not be attributed to one player."))
                continue
            _, t, p = cands[0]
            if ev.type in ("yellow", "double_yellow"):
                p.yellows += 1
            if ev.type == "double_yellow":
                warnings.append(Warn("double_yellow_semantics", f"Double-yellow icon for {p.name} at {ev.base}': counted as dismissal plus one recorded yellow. Verify."))
            if ev.type in ("red", "double_yellow"):
                p.red = True
                k = norm(p.name)
                if k in t.on:
                    t.on.pop(k)
                    p.minute_out = e
                    t.gone[k] = p
                else:
                    warnings.append(Warn("bench_dismissal", f"{p.name} was dismissed from the bench at {ev.base}'."))

    mine = teams[side]
    for p in mine.on.values():
        p.minute_out = d.total
    for p in mine.order:
        if p.minute_in is not None:
            p.minutes = max(0, (p.minute_out if p.minute_out is not None else d.total) - p.minute_in)
        if p.red and p.minute_out is not None and p.minute_out < d.total and p.minute_in is not None:
            dq_loss += d.total - p.minute_out

    actual = sum(p.minutes for p in mine.order)
    expected = 11 * d.total - dq_loss
    if actual != expected:
        warnings.append(Warn("minutes_mismatch", f"Player minutes total {actual} but 11 × {d.total} − dismissals = {expected}."))

    gf, ga = goals_for[side], goals_for[other]
    if parsed.score is not None:
        pub = parsed.score
        if (side == "home" and (gf, ga) != pub) or (side == "away" and (ga, gf) != pub):
            warnings.append(Warn("score_mismatch", f"Goals from the timeline ({gf}–{ga} for/against) disagree with the published score {pub[0]}–{pub[1]}."))
    credited = sum(p.goals for p in mine.order)
    icons = sum(p.roster_goals for p in mine.order)
    if icons != credited and any(p.roster_goals for p in mine.order):
        warnings.append(Warn("roster_goal_icons_mismatch", f"Goal icons in the lineup add up to {icons} but {credited} goals were credited from events."))

    return MatchComputation(
        side=side, opponent=parsed.away if side == "home" else parsed.home,
        published=published, duration=d, corrected=corrected, players=mine.order,
        goals_for=gf, goals_against=ga, expected_minutes=expected, actual_minutes=actual,
        dismissal_loss=dq_loss, warnings=warnings,
    )
