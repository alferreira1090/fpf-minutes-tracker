from fpf_tracker.domain.metrics import SUB_UNUSED, SUB_USED, STARTER, MatchInfo, Row, check_invariants, global_summary, indicators, league_table


def R(pid, mid, status, minutes, league="L", goals=0, yellows=0):
    return Row(pid, f"P{pid}", league, mid, status, minutes, goals, yellows)


def test_indicator_one_counts_every_listing_and_indicator_two_only_bench():
    rows = [R(1, 1, STARTER, 90), R(2, 1, SUB_USED, 20), R(3, 1, SUB_UNUSED, 0), R(1, 2, STARTER, 45), R(2, 2, SUB_UNUSED, 0)]
    ind = indicators(rows)
    assert ind["with_minutes"] == {"numerator": 3, "denominator": 5, "value": 0.6}
    b = ind["bench_minutes"]
    assert (b["numerator"], b["denominator"], b["unused"]) == (20, 3, 2) and abs(b["value"] - 20 / 3) < 1e-9


def test_regression_shape_95_6_percent_and_24_1_minutes():
    # Same totals as the SC Braga J1-J6 control sample: 114 listings, 109 with minutes,
    # 48 bench listings (5 unused) adding up to 1,158 bench minutes.
    rows = [R(i, 1 + i % 6, STARTER, 80) for i in range(66)]
    used = [27] * 40 + [26] * 3                                       # 43 used substitutes, 1,158 minutes
    rows += [R(100 + i, 1 + i % 6, SUB_USED, m) for i, m in enumerate(used)]
    rows += [R(200 + i, 1 + i % 6, SUB_UNUSED, 0) for i in range(5)]
    ind = indicators(rows)
    assert (ind["with_minutes"]["numerator"], ind["with_minutes"]["denominator"]) == (109, 114)
    assert round(ind["with_minutes"]["value"] * 100, 1) == 95.6
    assert (ind["bench_minutes"]["numerator"], ind["bench_minutes"]["denominator"]) == (1158, 48)
    assert round(ind["bench_minutes"]["value"], 1) == 24.1


def test_na_when_denominators_are_zero_and_zero_when_bench_never_played():
    assert indicators([])["with_minutes"]["value"] is None and indicators([])["bench_minutes"]["value"] is None
    assert indicators([R(1, 1, STARTER, 90)])["bench_minutes"]["value"] is None
    assert indicators([R(2, 1, SUB_UNUSED, 0)])["bench_minutes"]["value"] == 0.0


def test_league_table_distinguishes_unused_from_not_called_and_uses_all_matches_as_possible_minutes():
    ms = [MatchInfo(1, "L", "2026-09-01", "X", 90), MatchInfo(2, "L", "2026-09-08", "Y", 80)]
    t = league_table([R(1, 1, STARTER, 90, goals=1, yellows=1), R(1, 2, SUB_UNUSED, 0)], ms)
    p = t["players"][0]
    assert p["possible"] == 170 and abs(p["pct"] - 90 / 170) < 1e-9
    assert (p["appearances"], p["callups"], p["goals"], p["yellows"]) == (1, 2, 1, 1)
    t2 = league_table([R(1, 1, STARTER, 90)], ms)
    assert 2 not in t2["players"][0]["cells"]            # not called up -> no cell at all
    assert t["players"][0]["cells"][2]["status"] == SUB_UNUSED


def test_global_summary_consolidates_multi_league_players_and_matches_league_sums():
    rows = [R(1, 1, STARTER, 90, "A"), R(1, 2, SUB_USED, 20, "B"), R(2, 1, STARTER, 90, "A")]
    g = global_summary(rows, ["A", "B"], {"A": 1, "B": 1})
    p1 = next(p for p in g["players"] if p["player_id"] == 1)
    assert p1["multi_league"] and p1["minutes"] == 110 and p1["minutes_by_league"] == {"A": 90, "B": 20}


def test_pooled_not_averaged():
    a = [R(i, 1, STARTER, 90, "A") for i in range(1, 11)]                 # league A: 10/10
    b = [R(20, 2, SUB_UNUSED, 0, "B")]                                    # league B: 0/1
    assert indicators(a + b)["with_minutes"]["value"] == 10 / 11          # not (1.0 + 0.0) / 2


def test_invariants():
    rows = [R(1, 1, STARTER, 90), R(1, 2, SUB_UNUSED, 0)]
    assert check_invariants(rows, {"L": 2}) == []
    assert check_invariants(rows, {"L": 1})                                # more call-ups than matches analysed
