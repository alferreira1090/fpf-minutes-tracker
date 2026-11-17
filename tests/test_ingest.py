import pytest

from fpf_tracker.services.ingest import IngestService
from fpf_tracker.storage.db import Database
from tests.fpf_fixture import build_page, scenario_basic


@pytest.fixture
def env(tmp_path):
    db = Database(":memory:")
    return db, IngestService(db, tmp_path / "uploads"), db.get_or_create_club("Beta FC")


def test_import_then_reupload_replaces_instead_of_duplicating(env):
    db, sv, cid = env
    assert sv.import_file(cid, "J1.html", scenario_basic()).status == "imported"
    again = sv.import_file(cid, "J1-copy.html", scenario_basic())
    assert again.status == "updated" and len(db.matches(cid)) == 1
    assert len(db.participations(again.match_id)) == 17          # 11 starters + 6 bench, never doubled


def test_two_files_with_the_same_label_but_different_matches_are_two_matches(env):
    db, sv, cid = env
    sv.import_file(cid, "J2.html", scenario_basic(match_id="1", date="15/11/2026"))
    sv.import_file(cid, "J2.html", scenario_basic(match_id="2", date="22/11/2026"))
    assert len(db.matches(cid)) == 2


def test_side_is_detected_from_club_name_and_unknown_clubs_need_input(env):
    db, sv, cid = env
    other = db.get_or_create_club("Gama United")
    out = sv.import_file(other, "J1.html", scenario_basic())
    assert out.status == "needs_side" and out.home == "Alfa Clube" and out.away == "Beta FC"
    done = sv.resolve_side(other, out.sha, "J1.html", "away", remember_alias=True, league_label="Sub-16")
    assert done.status == "imported" and done.league == "Sub-16"
    assert db.matches(other)[0]["side"] == "away"
    # the remembered alias lets the next upload through without asking
    assert sv.import_file(other, "J1b.html", scenario_basic(match_id="5", date="01/12/2026")).status == "imported"


def test_bad_file_is_rejected_without_blocking_others(env):
    db, sv, cid = env
    bad = sv.import_file(cid, "x.html", b"<html>nope</html>")
    good = sv.import_file(cid, "ok.html", scenario_basic())
    assert bad.status == "rejected" and good.status == "imported"


def test_call_up_evidence_is_kept_for_unused_substitutes(env):
    db, sv, cid = env
    m = sv.import_file(cid, "J1.html", scenario_basic()).match_id
    nunca = next(p for p in db.participations(m) if p["display_name"] == "Beta Nunca")
    assert nunca["status"] == "Suplente não utilizado" and nunca["minutes"] == 0


def test_duration_correction_rejects_impossible_and_changes_nothing(env):
    from fpf_tracker.domain.models import MatchDataError
    db, sv, cid = env
    m = sv.import_file(cid, "J1.html", scenario_basic()).match_id
    before = db.match(m)["actual_minutes"]
    with pytest.raises(MatchDataError):
        sv.correct_duration(m, 80, 0, 0)                          # goals at 83' / 87' cannot happen in 80 minutes
    assert db.match(m)["actual_minutes"] == before and db.match(m)["nominal"] == 90


def test_valid_correction_is_stored_survives_reupload_and_can_be_cleared(env):
    db, sv, cid = env
    page = build_page(home="Alfa", away="Beta FC", home_starters=[(str(i), f"A{i}", i) for i in range(1, 12)],
                      away_starters=[(str(i), f"B{i}", 100 + i) for i in range(1, 12)], second_end="90' + 3'")
    m = sv.import_file(cid, "J.html", page).match_id
    assert db.match(m)["nominal"] + db.match(m)["s2"] == 93
    sv.correct_duration(m, 80, 0, 0)
    got = db.match(m)
    assert (got["nominal"], got["s1"], got["s2"], got["pub_nominal"], got["pub_s2"]) == (80, 0, 0, 90, 3)
    assert got["actual_minutes"] == 11 * 80
    sv.import_file(cid, "J.html", page)                            # re-upload keeps the correction
    assert db.match(m)["nominal"] == 80
    sv.clear_correction(m)
    assert db.match(m)["actual_minutes"] == 11 * 93
