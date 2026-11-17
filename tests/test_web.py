import pytest
from fastapi.testclient import TestClient

from fpf_tracker.web.app import create_app
from tests.fpf_fixture import build_page, scenario_basic


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path))


def make_club(client, name="Beta FC") -> int:
    r = client.post("/clubs", data={"name": name}, follow_redirects=False)
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def upload(client, cid, *pages, league=""):
    files = [("files", (f"J{i}.html", p, "text/html")) for i, p in enumerate(pages, start=1)]
    return client.post(f"/clubs/{cid}/upload", files=files, data={"league_label": league})


def test_empty_state_and_navigation(client):
    assert "Ainda não há clubes" in client.get("/").text
    cid = make_club(client)
    assert "Ainda não há jogos" in client.get(f"/clubs/{cid}").text


def test_upload_league_global_and_match_pages_render(client):
    cid = make_club(client)
    r = upload(client, cid, scenario_basic(), scenario_basic(match_id="2", date="22/11/2026"), league="Sub-16")
    assert r.status_code == 200 and r.text.count("Importado") == 2
    league = client.get(f"/clubs/{cid}/league", params={"name": "Sub-16"}).text
    assert "Beta Dois" in league and "Hugo Martins" in league and "vs Alfa Clube" in league
    assert 'title="Suplente não utilizado"' in league
    assert "Convocados que tiveram minutos" in league
    g = client.get(f"/clubs/{cid}/global").text
    assert "Resumo global" in g and "Beta Quinze" in g
    m = client.get("/matches/1").text
    assert "Reconciliado" in m and "1023" in m
    assert client.get(f"/clubs/{cid}/matches").status_code == 200
    assert client.get(f"/clubs/{cid}/identity").status_code == 200


def test_api_matches_pages(client):
    cid = make_club(client)
    upload(client, cid, scenario_basic(), league="Sub-16")
    api = client.get(f"/api/clubs/{cid}/league", params={"name": "Sub-16"}).json()
    quinze = next(p for p in api["players"] if p["name"] == "Beta Quinze")
    assert quinze["minutes"] == 65 and quinze["goals"] == 1 and quinze["callups"] == 1
    assert f">{quinze['minutes']}<" in client.get(f"/clubs/{cid}/league", params={"name": "Sub-16"}).text.replace("<b>", ">").replace("</b>", "<")
    ind = client.get(f"/api/clubs/{cid}/indicators").json()
    assert ind["with_minutes"]["numerator"] == 16 and ind["with_minutes"]["denominator"] == 17
    assert ind["bench_minutes"]["numerator"] == 155 and ind["bench_minutes"]["denominator"] == 6
    assert api["indicators"] == ind
    summ = client.get(f"/api/clubs/{cid}/summary").json()
    assert sum(p["minutes"] for p in summ["players"]) == 1023


def test_unknown_club_needs_input_then_resolves(client):
    cid = make_club(client, "Gama United")
    r = upload(client, cid, scenario_basic())
    assert "Precisa de confirmação" in r.text
    sha = r.text.split('name="sha" value="')[1].split('"')[0]
    r2 = client.post(f"/clubs/{cid}/resolve", data={"sha": sha, "filename": "J1.html", "side": "away", "remember": "1"})
    assert "Importado" in r2.text


def test_rejected_file_reports_reason(client):
    cid = make_club(client)
    r = upload(client, cid, b"<html>not fpf</html>", scenario_basic())
    assert "Rejeitado" in r.text and "Importado" in r.text


def test_duration_correction_flow_and_rejection(client):
    cid = make_club(client)
    upload(client, cid, scenario_basic())
    bad = client.post("/matches/1/duration", data={"nominal": 80, "s1": 0, "s2": 0}, follow_redirects=True)
    assert "Correção rejeitada" in bad.text and "90" in client.get("/matches/1").text
    ok = client.post("/matches/1/duration", data={"nominal": 90, "s1": 0, "s2": 5}, follow_redirects=True)
    assert "Corrigida pelo utilizador" in ok.text and "11 × 95" in ok.text
    back = client.post("/matches/1/duration/clear", follow_redirects=True)
    assert "Corrigida pelo utilizador" not in back.text


def test_hostile_name_is_escaped(client):
    cid = make_club(client)
    evil = '<script>alert(1)</script>'
    starters = [(str(i), f"Beta {i}", 300 + i) for i in range(1, 11)] + [("11", evil, 311)]
    page = build_page(home="Alfa", away="Beta FC", home_starters=[(str(i), f"Alfa {i}", i) for i in range(1, 12)], away_starters=starters)
    upload(client, cid, page, league="X")
    for url in (f"/clubs/{cid}/league?name=X", f"/clubs/{cid}/global", "/matches/1"):
        body = client.get(url).text
        assert "<script>alert(1)</script>" not in body and "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_404s(client):
    assert client.get("/clubs/99").status_code == 404 and client.get("/matches/99").status_code == 404
