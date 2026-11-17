import pytest

from fpf_tracker.domain.minutes import SUB_UNUSED, SUB_USED, STARTER, compute_match
from fpf_tracker.domain.models import MatchDataError
from fpf_tracker.domain.parser import parse_fpf_html
from tests.fpf_fixture import build_page, scenario_basic


def squad(prefix, n_starters=11, subs=3, base=0):
    starters = [(str(i), f"{prefix} S{i:02d}", base + i) for i in range(1, n_starters + 1)]
    bench = [(str(20 + i), f"{prefix} B{i:02d}", base + 20 + i) for i in range(1, subs + 1)]
    return starters, bench


def page(first_end="45'", second_end="90' + 3'", first=(), second=(), score="0 - 0", **kw):
    hs, hb = squad("Casa", base=100)
    as_, ab = squad("Fora", base=200)
    return parse_fpf_html(build_page(home="Casa FC", away="Fora FC", score=score, first_end=first_end, second_end=second_end,
                                     first_events=first, second_events=second, home_starters=hs, home_subs=hb,
                                     away_starters=as_, away_subs=ab, **kw))


def by_name(comp):
    return {p.name: p for p in comp.players}


def test_hand_checked_scenario_sums_to_11_times_T():
    comp = compute_match(parse_fpf_html(scenario_basic()), "away")
    assert comp.duration.total == 93
    assert comp.actual_minutes == comp.expected_minutes == 11 * 93 == 1023 and comp.reconciled
    p = by_name(comp)
    assert p["Beta Dois"].minutes == 93 and p["Beta Dois"].status == STARTER
    assert p["Beta Seis"].minutes == 75 and p["Beta Reserva14"].minutes == 18          # 75' substitution, T=93
    assert p["Beta Reserva12"].minutes == 48 and p["Beta Guarda"].minutes == 45
    assert p["Beta Nunca"].status == SUB_UNUSED and p["Beta Nunca"].minutes == 0
    assert p["Beta Reserva16"].status == SUB_USED


def test_homonym_in_both_squads_is_attributed_by_state_and_score():
    comp = compute_match(parse_fpf_html(scenario_basic()), "away")
    hugo = by_name(comp)["Hugo Martins"]
    assert (hugo.status, hugo.minutes, hugo.goals) == (SUB_USED, 18, 1)
    assert comp.goals_for == 4 and comp.goals_against == 1
    assert any(w.code == "homonym_goal" for w in comp.warnings)
    # the same name in the home squad is a different, unrelated player
    home = compute_match(parse_fpf_html(scenario_basic()), "home")
    assert by_name(home)["Hugo Martins"].minutes == 45 and by_name(home)["Hugo Martins"].goals == 0


def test_duration_with_stoppage_in_both_halves_is_87():
    comp = compute_match(page(first_end="40' + 1'", second_end="80' + 6'"), "away")
    assert comp.duration.total == 87 and comp.duration.half == 40
    assert by_name(comp)["Fora S01"].minutes == 87


def test_second_half_stamps_add_first_half_stoppage():
    sub = ("sub", "60'", "Fora B01", "Fora S02")
    comp = compute_match(page(first_end="45' + 2'", second_end="90' + 1'", second=[sub]), "away")
    p = by_name(comp)
    assert comp.duration.total == 93
    assert p["Fora S02"].minutes == 62 and p["Fora B01"].minutes == 93 - 62       # 60 + S1(2) = 62


def test_substitution_at_half_time_mark_with_stoppage_is_treated_as_half_time_and_warned():
    sub = ("sub", "45'", "Fora B01", "Fora S02")
    comp = compute_match(page(first_end="45' + 2'", second_end="90'", first=[sub]), "away")
    assert by_name(comp)["Fora S02"].minutes == 47
    assert any(w.code == "halftime_substitution_ambiguous" for w in comp.warnings)


def test_red_card_ends_playing_time_and_lowers_expected_minutes():
    comp = compute_match(page(second_end="90'", second=[("red", "60'", "Fora S03")]), "away")
    p = by_name(comp)["Fora S03"]
    assert p.minutes == 60 and p.red
    assert comp.dismissal_loss == 30 and comp.expected_minutes == 11 * 90 - 30 == comp.actual_minutes


def test_double_yellow_counts_one_yellow_dismisses_and_warns():
    comp = compute_match(page(second_end="90'", first=[("yellow", "20'", "Fora S04")],
                              second=[("double_yellow", "70'", "Fora S04")]), "away")
    p = by_name(comp)["Fora S04"]
    assert p.yellows == 2 and p.red and p.minutes == 70
    assert any(w.code == "double_yellow_semantics" for w in comp.warnings)


def test_yellow_card_counted_once_per_event():
    comp = compute_match(page(first=[("yellow", "20'", "Fora S04")]), "away")
    assert by_name(comp)["Fora S04"].yellows == 1 and not by_name(comp)["Fora S04"].red


def test_own_goal_counts_for_the_beneficiary_not_the_scorer():
    comp = compute_match(page(score="1 - 0", first=[("goal", "30'", "1 - 0", "Fora S05")]), "away")
    assert comp.goals_for == 0 and comp.goals_against == 1
    assert by_name(comp)["Fora S05"].goals == 0 and by_name(comp)["Fora S05"].own_goals == 1


def test_score_mismatch_is_a_warning_not_an_invented_goal():
    comp = compute_match(page(score="3 - 0", first=[("goal", "30'", "1 - 0", "Casa S09")]), "away")
    assert comp.goals_against == 1 and any(w.code == "score_mismatch" for w in comp.warnings)


def test_unmatched_substitution_breaks_reconciliation_visibly():
    comp = compute_match(page(second=[("sub", "60'", "Nobody Known", "Fora S02")]), "away")
    assert any(w.code == "substitution_unmatched" for w in comp.warnings)


def test_extra_period_block_is_warned_and_not_treated_as_extra_time():
    comp = compute_match(page(second_end="90' + 3'", extra_periods=[("Prolongamento", "93'", [("yellow", "83'", "Fora S06")])]), "away")
    assert comp.duration.total == 93 and any(w.code == "extra_period_blocks" for w in comp.warnings)


def test_valid_duration_correction_recomputes_and_keeps_published_values():
    pm = page(first_end="40'", second_end="80'", second=[("sub", "70'", "Fora B01", "Fora S02")])
    pub = compute_match(pm, "away")
    fixed = compute_match(pm, "away", {"nominal": 80, "s1": 0, "s2": 0})
    assert pub.duration.total == 80 and not fixed.corrected
    pm90 = page(second_end="90' + 3'", second=[("sub", "70'", "Fora B01", "Fora S02")])
    c = compute_match(pm90, "away", {"nominal": 80, "s1": 0, "s2": 0})
    assert c.corrected and c.duration.total == 80 and c.published.total == 93
    assert by_name(c)["Fora S02"].minutes == 70 and by_name(c)["Fora B01"].minutes == 10


def test_impossible_correction_is_rejected():
    pm = page(second_end="90'", second=[("goal", "83'", "0 - 1", "Fora S09")])
    with pytest.raises(MatchDataError) as err:
        compute_match(pm, "away", {"nominal": 80, "s1": 0, "s2": 0})
    assert "83" in str(err.value)


def test_missing_end_markers_reject_the_match():
    pm = parse_fpf_html(build_page(home="A", away="B", home_starters=[("1", "A Um", 1)], away_starters=[("1", "B Um", 2)],
                                   first_end="?", second_end="?"))
    with pytest.raises(MatchDataError):
        compute_match(pm, "away")
