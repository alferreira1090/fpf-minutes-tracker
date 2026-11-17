"""Builds FPF-like match pages with invented names.

The markup mirrors what the real report page uses (og:title / og:url meta tags, timeline blocks with
end markers, lineup panels with /Player/Logo/<id> photos). Real pages contain names of minors and are
kept out of the repository on purpose.
"""
from __future__ import annotations

from html import escape

ICON = {
    "goal": "icon-goal", "sub": "icon-substitution", "yellow": "icon-yellow-card",
    "double_yellow": "icon-double-yellow-card", "red": "icon-red-card",
}


def _event(ev) -> str:
    kind, stamp = ev[0], ev[1]
    if kind == "goal":
        inner = f'{ev[2]}                            <strong>{escape(ev[3])} </strong>'
        bottom = f'<span class="tag bottom-tag dark arrow">\n{inner}\n</span>'
    elif kind == "sub":
        bottom = (f'<span class="tag bottom-tag substitution-tag dark arrow"><span class="in">{escape(ev[2])}</span>'
                  f'<span class="out">{escape(ev[3])}</span></span>')
    elif kind == "mystery":
        bottom = f'<span class="tag bottom-tag dark arrow"><strong>{escape(ev[2])}</strong></span>'
    else:
        bottom = f'<span class="tag bottom-tag dark arrow"><strong>{escape(ev[2])} </strong></span>'
    icon = ev[4] if kind == "mystery" else ICON[kind]
    return f"""
            <div class="timeline-item" style="left: 50%">
                <span class="timeline-item-container">
                    <span class="tag top-tag dark arrow">{stamp.replace("'", "&#39;")} </span>
                    <span class="icon small-icon"><img src="/Images/{icon}.png" alt="" title="" /></span>
                    {bottom}
                </span>
            </div>"""


def _period(title: str, end: str, events) -> str:
    return f"""<div class="timeline-title col-md-12 text-center no-padding">{title}</div>
<div class="col-md-10 col-md-offset-1 no-padding">
    <div class="timeline-wrapper"><hr />
        <div class="timeline-item"><span class="tag top-tag start-game pipe">0&#39;</span>
            <span class="icon"><img src="/Images/icon-start.png" alt="" /></span></div>
        {''.join(_event(e) for e in events)}
        <div class="timeline-item" style="left: 100%">
            <span class="tag top-tag end-game pipe">
{end.replace("'", "&#39;")}            </span>
            <span class="icon"><img src="/Images/icon-end.png" alt="" /></span>
        </div>
    </div>
</div>"""


def _player(p) -> str:
    num, name, pid = p[0], p[1], p[2]
    gk = " (GR)" if len(p) > 3 and p[3] == "GR" else ""
    goals = p[4] if len(p) > 4 else 0
    gicon = f'<span class="icon icon-goal"><span>{goals}</span></span>' if goals else ""
    img = f'<img src="/Player/Logo/{pid}" title="" alt="" />' if pid else '<img src="/Images/blank.png" alt="" />'
    return f"""<div class="player col-md-4 col-sm-4 col-xs-4">
    <div class="photo">{img}<span class="icons">{gicon}</span></div>
    <strong>{num}</strong> {escape(name)}{gk}
</div>"""


def _lineup(title: str, home, away) -> str:
    return f"""<section class="col-md-12 col-sm-12 col-xs-12">
    <div class="title-bar"><div class="col-md-12">{title}</div></div>
    <div class="lineup-team home-team col-md-6"><div class="row"><div class="col-md-10">{''.join(_player(p) for p in home)}</div></div></div>
    <div class="lineup-team away-team col-md-6"><div class="row"><div class="col-md-10">{''.join(_player(p) for p in away)}</div></div></div>
</section>"""


def build_page(*, home, away, date="15/11/2026", competition="Campeonato Distrital Sub-16", score="0 - 0",
               match_id="900001", first_end="45'", second_end="90' + 3'", first_events=(), second_events=(),
               extra_periods=(), home_starters=(), home_subs=(), away_starters=(), away_subs=()) -> bytes:
    periods = _period("1&#170; parte", first_end, first_events) + _period("2&#170; parte", second_end, second_events)
    for title, end, evs in extra_periods:
        periods += _period(title, end, evs)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8" />
<title>FPF - Centro de Resultados</title>
<meta property='og:title' content='{escape(home)} vs {escape(away)} — {date} | Resultados FPF' />
<meta property='og:url' content='https://resultados.fpf.pt/Match/GetMatchInformation?matchId={match_id}' />
</head><body>
<section class="body"><div class="container">
<div class="current-competition col-md-12"><div class="row no-gutters"><div class="col-md-6 col-xs-6">{escape(competition)}</div>
<div class="col-md-6 text-right"><a href="#"></a></div></div></div>
<div class="section-title game-resume col-md-12"><div class="row">
<div class="col-md-3"><strong>{escape(home)}</strong></div>
<div class="col-md-4 text-center"><strong>{score}</strong></div>
<div class="col-md-3 text-right"><strong>{escape(away)}</strong></div></div></div>
<section class="col-md-12"><div class="title-bar"><div class="col-md-12">Eventos de jogo</div></div>
<div class="row no-gutters"><div class="col-md-12 timeline">{periods}</div></div></section>
{_lineup("Equipas Iniciais", home_starters, away_starters)}
{_lineup("Suplentes", home_subs, away_subs)}
<section class="col-md-12"><div class="title-bar"><div class="col-md-12">Treinadores</div></div>
<div class="lineup-team home-team"><div class="row"><div class="player"><div class="photo"><img src="/Player/Logo/1" /></div>
<span>Treinador Principal</span><span>Coach Name</span></div></div></div></section>
</div></section></body></html>""".encode("utf-8")


# --- A hand-checkable scenario: tracked club "Beta FC" is AWAY, T = 90 + 3 = 93, no first-half stoppage ---
def scenario_basic(match_id="900001", date="15/11/2026", competition="Campeonato Distrital Sub-16") -> bytes:
    home_starters = [(str(i), f"Alfa Jogador{i:02d}", 1000 + i, "GR" if i == 1 else "") for i in range(1, 12)]
    home_starters[6] = ("77", "Hugo Martins", 1077)                      # homonym of an away substitute
    home_subs = [("7", "Alfa Suplente07", 1107), ("17", "Alfa Suplente17", 1117)]
    away_starters = [
        ("1", "Beta Guarda", 2001, "GR"), ("2", "Beta Dois", 2002), ("3", "Beta Tres", 2003), ("5", "Beta Cinco", 2005),
        ("6", "Beta Seis", 2006), ("7", "Beta Sete", 2007), ("8", "Beta Oito", 2008), ("9", "Beta Nove", 2009, "", 1),
        ("10", "Beta Dez", 2010), ("11", "Beta Onze", 2011), ("15", "Beta Quinze", 2015, "", 1),
    ]
    away_subs = [
        ("4", "Hugo Martins", 2004, "", 1), ("12", "Beta Reserva12", 2012, "GR"), ("13", "Beta Reserva13", 2013),
        ("14", "Beta Reserva14", 2014, "", 1), ("16", "Beta Reserva16", 2016), ("18", "Beta Nunca", 2018),
    ]
    first = [
        ("goal", "30'", "0 - 1", "Beta Nove"),
        ("goal", "35'", "1 - 1", "Alfa Jogador05"),
        ("sub", "45'", "Beta Reserva12", "Beta Guarda"),
        ("sub", "45'", "Alfa Suplente07", "Hugo Martins"),
    ]
    second = [
        ("sub", "50'", "Beta Reserva13", "Beta Dez"),
        ("goal", "63'", "1 - 2", "Beta Quinze"),
        ("sub", "65'", "Beta Reserva16", "Beta Quinze"),
        ("sub", "75'", "Hugo Martins", "Beta Onze"),
        ("sub", "75'", "Beta Reserva14", "Beta Seis"),
        ("goal", "83'", "1 - 3", "Beta Reserva14"),
        ("goal", "87'", "1 - 4", "Hugo Martins"),
    ]
    return build_page(
        home="Alfa Clube", away="Beta FC", score="1 - 4", match_id=match_id, date=date, competition=competition,
        first_events=first, second_events=second, home_starters=home_starters, home_subs=home_subs,
        away_starters=away_starters, away_subs=away_subs,
    )
