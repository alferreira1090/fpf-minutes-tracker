"""FastAPI application: server-rendered pt-PT pages plus a JSON API under /api."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..domain import metrics
from ..domain.models import MatchDataError
from ..services.ingest import IngestService
from ..storage.db import Database

HERE = Path(__file__).parent
MAX_FILES = 50

WARNING_TITLES = {
    "homonym_goal": "Nome repetido nas duas equipas (golo)",
    "own_goal": "Autogolo",
    "scorer_not_in_squad": "Marcador fora dos plantéis",
    "score_mismatch": "Resultado não coincide com os golos",
    "score_inconsistent": "Marcador inconsistente",
    "roster_goal_icons_mismatch": "Ícones de golo ≠ golos dos eventos",
    "halftime_substitution_ambiguous": "Substituição ao intervalo ambígua",
    "substitution_unmatched": "Substituição não aplicada",
    "ambiguous_substitution": "Substituição ambígua",
    "double_yellow_semantics": "Duplo amarelo (verificar)",
    "ambiguous_card": "Cartão ambíguo",
    "card_player_not_found": "Cartão sem jogador",
    "bench_dismissal": "Expulsão no banco",
    "minutes_mismatch": "Minutos não reconciliam",
    "extra_period_blocks": "Blocos de tempo a mais",
    "end_marker_format": "Formato do fim da 2.ª parte",
    "half_length_mismatch": "Duração da parte ≠ metade",
    "event_outside_match": "Evento fora do jogo",
    "unknown_event": "Evento desconhecido",
    "goal_icon_variant": "Variante do ícone de golo",
    "starters_count": "N.º de titulares",
    "duplicate_name_in_squad": "Nome repetido no plantel",
    "event_unreadable": "Evento ilegível",
    "period_end_missing": "Fim de parte ilegível",
    "competition_missing": "Competição em falta",
    "score_missing": "Resultado em falta",
    "multiple_goals_one_event": "Vários golos num evento",
    "goal_without_score": "Golo sem marcador",
    "odd_nominal_duration": "Duração ímpar",
}


def heat(value: float | None, full: float | None) -> str:
    """Red at 0, amber at half, green at the full duration (translucent so it works on the dark theme)."""
    if value is None or not full:
        return "transparent"
    x = max(0.0, min(1.0, value / full))
    red, amber, green = (224, 82, 82), (232, 176, 60), (56, 189, 120)
    a, b, t = (red, amber, x * 2) if x < 0.5 else (amber, green, (x - 0.5) * 2)
    r, g, bl = (round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"rgba({r},{g},{bl},0.42)"


def pct(v: float | None) -> str:
    return "N/D" if v is None else f"{v * 100:.1f}".replace(".", ",") + " %"


def mins(v: float | None) -> str:
    return "N/D" if v is None else f"{v:.1f}".replace(".", ",") + " min"


def dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    data = Path(data_dir or os.environ.get("FPF_DATA_DIR", "data"))
    db = Database(data / "fpf.sqlite3")
    ingest = IngestService(db, data / "uploads")
    app = FastAPI(title="FPF Minutos", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")   # autoescape is on for .html
    templates.env.filters.update(pct=pct, mins=mins, dmy=dmy, heat=heat)
    templates.env.globals.update(WARNING_TITLES=WARNING_TITLES)
    app.state.db, app.state.ingest = db, ingest

    def render(request: Request, name: str, **ctx):
        return templates.TemplateResponse(request, name, ctx)

    def need_club(club_id: int) -> dict:
        club = db.club(club_id)
        if not club:
            raise HTTPException(404, "Clube não encontrado")
        return club

    def scope_rows(club_id: int, scope: str | None):
        rows = db.metric_rows(club_id, scope or None)
        return rows

    # ---------------------------------------------------------------- pages
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render(request, "index.html", clubs=db.clubs())

    @app.post("/clubs")
    def create_club(name: str = Form(...)):
        name = " ".join(name.split())
        if not name or len(name) > 120:
            raise HTTPException(422, "Nome de clube inválido")
        return RedirectResponse(f"/clubs/{db.get_or_create_club(name)}", status_code=303)

    @app.get("/clubs/{club_id}", response_class=HTMLResponse)
    def club_page(request: Request, club_id: int):
        club = need_club(club_id)
        leagues = db.leagues(club_id)
        ind_all = metrics.indicators(db.metric_rows(club_id))
        per_league = {lg["league"]: metrics.indicators(db.metric_rows(club_id, lg["league"])) for lg in leagues}
        return render(request, "club.html", club=club, leagues=leagues, ind=ind_all, per_league=per_league)

    @app.get("/clubs/{club_id}/upload", response_class=HTMLResponse)
    def upload_form(request: Request, club_id: int):
        return render(request, "upload.html", club=need_club(club_id), leagues=db.leagues(club_id), outcomes=None)

    @app.post("/clubs/{club_id}/upload", response_class=HTMLResponse)
    async def upload(request: Request, club_id: int, files: list[UploadFile] = File(...), league_label: str = Form("")):
        club = need_club(club_id)
        if len(files) > MAX_FILES:
            raise HTTPException(422, f"No máximo {MAX_FILES} ficheiros de cada vez")
        outcomes = []
        for f in files:
            data_bytes = await f.read()
            outcomes.append(ingest.import_file(club_id, f.filename or "ficheiro.html", data_bytes,
                                               " ".join(league_label.split()) or None))
        return render(request, "upload.html", club=club, leagues=db.leagues(club_id), outcomes=outcomes)

    @app.post("/clubs/{club_id}/resolve", response_class=HTMLResponse)
    def resolve(request: Request, club_id: int, sha: str = Form(...), filename: str = Form(...), side: str = Form(...),
                remember: str = Form(""), league_label: str = Form("")):
        club = need_club(club_id)
        if side not in ("home", "away") or len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha):
            raise HTTPException(422, "Pedido inválido")
        out = ingest.resolve_side(club_id, sha, filename, side, bool(remember), league_label or None)
        return render(request, "upload.html", club=club, leagues=db.leagues(club_id), outcomes=[out])

    def league_ctx(club_id: int, name: str):
        ms = db.match_infos(club_id, name)
        if not ms:
            raise HTTPException(404, "Liga sem jogos")
        return metrics.league_table(db.metric_rows(club_id, name), ms)

    @app.get("/clubs/{club_id}/league", response_class=HTMLResponse)
    def league_page(request: Request, club_id: int, name: str):
        club = need_club(club_id)
        table = league_ctx(club_id, name)
        problems = metrics.check_invariants(db.metric_rows(club_id, name), {name: len(table["matches"])})
        return render(request, "league.html", club=club, leagues=db.leagues(club_id), league=name, t=table, problems=problems)

    @app.get("/clubs/{club_id}/global", response_class=HTMLResponse)
    def global_page(request: Request, club_id: int, scope: str = ""):
        club = need_club(club_id)
        leagues = db.leagues(club_id)
        names = [lg["league"] for lg in leagues]
        summary = metrics.global_summary(db.metric_rows(club_id), names, {lg["league"]: lg["matches"] for lg in leagues})
        scoped = metrics.indicators(scope_rows(club_id, scope if scope in names else None))
        return render(request, "global.html", club=club, leagues=leagues, g=summary, ind=scoped, scope=scope if scope in names else "")

    @app.get("/clubs/{club_id}/matches", response_class=HTMLResponse)
    def matches_page(request: Request, club_id: int):
        return render(request, "matches.html", club=need_club(club_id), matches=db.matches(club_id), leagues=db.leagues(club_id))

    @app.get("/clubs/{club_id}/identity", response_class=HTMLResponse)
    def identity_page(request: Request, club_id: int):
        return render(request, "identity.html", club=need_club(club_id), audit=db.identity_audit(club_id), leagues=db.leagues(club_id))

    def match_ctx(match_id: int):
        m = db.match(match_id)
        if not m:
            raise HTTPException(404, "Jogo não encontrado")
        return m, db.participations(match_id)

    @app.get("/matches/{match_id}", response_class=HTMLResponse)
    def match_page(request: Request, match_id: int, error: str = ""):
        m, parts = match_ctx(match_id)
        return render(request, "match.html", club=need_club(m["club_id"]), leagues=db.leagues(m["club_id"]), m=m, parts=parts, error=error)

    @app.post("/matches/{match_id}/duration")
    def correct(match_id: int, nominal: int = Form(...), s1: int = Form(0), s2: int = Form(0)):
        try:
            ingest.correct_duration(match_id, nominal, s1, s2)
        except MatchDataError as exc:
            from urllib.parse import quote
            return RedirectResponse(f"/matches/{match_id}?error={quote(str(exc))}", status_code=303)
        return RedirectResponse(f"/matches/{match_id}", status_code=303)

    @app.post("/matches/{match_id}/duration/clear")
    def clear(match_id: int):
        try:
            ingest.clear_correction(match_id)
        except MatchDataError as exc:
            raise HTTPException(422, str(exc))
        return RedirectResponse(f"/matches/{match_id}", status_code=303)

    # ---------------------------------------------------------------- JSON API
    @app.get("/api/clubs")
    def api_clubs():
        return db.clubs()

    @app.get("/api/clubs/{club_id}/league")
    def api_league(club_id: int, name: str):
        need_club(club_id)
        t = league_ctx(club_id, name)
        t["matches"] = [asdict(m) for m in t["matches"]]
        return t

    @app.get("/api/clubs/{club_id}/summary")
    def api_summary(club_id: int):
        need_club(club_id)
        leagues = db.leagues(club_id)
        return metrics.global_summary(db.metric_rows(club_id), [lg["league"] for lg in leagues],
                                      {lg["league"]: lg["matches"] for lg in leagues})

    @app.get("/api/clubs/{club_id}/indicators")
    def api_indicators(club_id: int, league: str | None = None):
        need_club(club_id)
        return metrics.indicators(db.metric_rows(club_id, league or None))

    return app


def run() -> None:  # console script: fpf-tracker
    host = os.environ.get("FPF_HOST", "127.0.0.1")   # localhost by default: data includes minors' names
    uvicorn.run(create_app(), host=host, port=int(os.environ.get("FPF_PORT", "8000")))

