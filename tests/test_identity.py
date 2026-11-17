from fpf_tracker.domain.identity import KnownPlayer, resolve_player


def test_same_fpf_id_is_the_same_person_even_with_different_spelling():
    r = resolve_player([KnownPlayer(1, "João Ferreira", "55")], "Joao  Ferreira Jr", "55")
    assert (r.action, r.player_id) == ("by_id", 1) and "spelling" in r.note


def test_name_match_without_id_conflict_merges_and_is_flagged():
    r = resolve_player([KnownPlayer(1, "João Ferreira", None)], "joao ferreira", "55")
    assert (r.action, r.player_id) == ("by_name", 1)
    r = resolve_player([KnownPlayer(1, "João Ferreira", "55")], "Joao Ferreira", None)
    assert (r.action, r.player_id) == ("by_name", 1)


def test_same_name_different_ids_are_different_people():
    r = resolve_player([KnownPlayer(1, "Rui Silva", "10")], "Rui Silva", "11")
    assert r.action == "new" and r.homonym_of == [1]


def test_ambiguous_name_without_id_is_never_merged():
    r = resolve_player([KnownPlayer(1, "Rui Silva", "10"), KnownPlayer(2, "Rui Silva", "11")], "Rui Silva", None)
    assert r.action == "new" and r.homonym_of == [1, 2]


def test_unknown_player_is_new():
    assert resolve_player([], "Novo Nome", "1").action == "new"
