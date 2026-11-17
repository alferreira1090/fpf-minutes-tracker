import pytest

from fpf_tracker.domain.models import MatchDataError
from fpf_tracker.domain.parser import parse_fpf_html, parse_stamp
from tests.fpf_fixture import build_page, scenario_basic


def test_metadata_comes_from_the_page_not_the_file_name():
    pm = parse_fpf_html(scenario_basic(), "J2.html")
    assert (pm.home, pm.away, pm.date, pm.score) == ("Alfa Clube", "Beta FC", "2026-11-15", (1, 4))
    assert pm.fpf_match_id == "900001"
    assert pm.competition == "Campeonato Distrital Sub-16"


def test_rosters_carry_fpf_ids_and_goalkeepers():
    pm = parse_fpf_html(scenario_basic())
    assert len(pm.starters["away"]) == 11 and len(pm.substitutes["away"]) == 6
    gk = pm.starters["away"][0]
    assert gk.goalkeeper and gk.name == "Beta Guarda" and gk.fpf_id == "2001"
    assert pm.starters["away"][7].roster_goals == 1


def test_period_end_markers_and_events():
    pm = parse_fpf_html(scenario_basic())
    assert [(p.end_base, p.end_added) for p in pm.periods] == [(45, 0), (90, 3)]
    kinds = [e.type for e in pm.events]
    assert kinds.count("goal") == 5 and kinds.count("substitution") == 6
    first_goal = pm.events[0]
    assert first_goal.running_score == (0, 1) and first_goal.scorer == "Beta Nove" and first_goal.period == 1
    sub = next(e for e in pm.events if e.type == "substitution")
    assert (sub.in_name, sub.out_name) == ("Beta Reserva12", "Beta Guarda")


@pytest.mark.parametrize("raw,expected", [("45'", (45, 0)), ("90' + 3'", (90, 3)), ("40'+1'", (40, 1)), ("x", None)])
def test_stamp(raw, expected):
    assert parse_stamp(raw) == expected


def test_unknown_event_icon_warns_and_is_not_counted():
    page = build_page(home="A", away="B", home_starters=[("1", "A Um", 1)], away_starters=[("1", "B Um", 2)],
                      first_events=[("mystery", "10'", "B Um", None, "icon-var-review")])
    pm = parse_fpf_html(page)
    assert any(w.code == "unknown_event" for w in pm.warnings)
    assert pm.events[0].type == "unknown"


def test_rejects_non_fpf_pages():
    with pytest.raises(MatchDataError):
        parse_fpf_html(b"<html><body><p>hello</p></body></html>")
    with pytest.raises(MatchDataError):
        parse_fpf_html(b"x" * (6 * 1024 * 1024))
