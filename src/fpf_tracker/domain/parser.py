"""Extract structured data from a saved FPF match-report page.

All HTML selectors live in this module. The page is untrusted data: it is parsed, never executed.
Based on the approach of the FPF skill's extract_fpf_match.py, extended with FPF player ids, period
blocks per timeline event and typed warnings.
"""
from __future__ import annotations

import re

from lxml import html

from .models import Event, MatchDataError, ParsedMatch, Period, RosterPlayer, Warn

MAX_BYTES = 5 * 1024 * 1024

_KNOWN_ICONS = {
    "icon-goal": "goal",
    "icon-substitution": "substitution",
    "icon-yellow-card": "yellow",
    "icon-double-yellow-card": "double_yellow",
    "icon-red-card": "red",
}
_IGNORED_ICONS = {"icon-start", "icon-end"}
_STAMP = re.compile(r"^\s*(\d+)\s*'?\s*(?:\+\s*(\d+)\s*'?)?\s*$")


def _cls(value: str) -> str:
    return f'contains(concat(" ",normalize-space(@class)," ")," {value} ")'


def _text(el) -> str:
    return " ".join(" ".join(el.itertext()).split())


def parse_stamp(raw: str) -> tuple[int, int] | None:
    m = _STAMP.match(raw.replace("\xa0", " "))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 0)


def parse_fpf_html(data: bytes, source_name: str = "upload.html") -> ParsedMatch:
    if len(data) > MAX_BYTES:
        raise MatchDataError("File is larger than 5 MB; this is not an FPF match page.")
    try:
        doc = html.fromstring(data)
    except Exception as exc:  # lxml raises several error types
        raise MatchDataError(f"HTML could not be read: {exc}") from exc

    warnings: list[Warn] = []

    title = doc.xpath('//meta[@property="og:title"]/@content')
    m = re.match(r"(.+?)\s+vs\s+(.+?)\s+[—–-]\s+(\d{2})/(\d{2})/(\d{4})", title[0]) if title else None
    if not m:
        raise MatchDataError("Not an FPF match report: title with clubs and date not found.")
    home, away = m.group(1).strip(), m.group(2).strip()
    date = f"{m.group(5)}-{m.group(4)}-{m.group(3)}"

    url = doc.xpath('//meta[@property="og:url"]/@content')
    mid = re.search(r"matchId=(\d+)", url[0]) if url else None

    comp_el = doc.xpath(f'(//*[{_cls("current-competition")}]//div[{_cls("col-md-6")}])[1]')
    competition = _text(comp_el[0]) if comp_el else ""
    if not competition:
        warnings.append(Warn("competition_missing", "Competition name not found in the page."))

    score = None
    for strong in doc.xpath(f'//*[{_cls("game-resume")}]//strong'):
        sm = re.fullmatch(r"(\d+)\s*-\s*(\d+)", _text(strong))
        if sm:
            score = (int(sm.group(1)), int(sm.group(2)))
            break
    if score is None:
        warnings.append(Warn("score_missing", "Final score not found in the page."))

    starters = {"home": [], "away": []}
    substitutes = {"home": [], "away": []}
    found_lineups = False
    for heading in doc.xpath(f'//section/div[{_cls("title-bar")}]'):
        label = _text(heading)
        if label not in ("Equipas Iniciais", "Suplentes"):
            continue
        found_lineups = True
        target = starters if label == "Equipas Iniciais" else substitutes
        panels = heading.getparent().xpath(f'./div[{_cls("lineup-team")}]')
        for index, panel in enumerate(panels):
            if "home-team" in (panel.get("class") or "").split():
                side = "home"
            elif "away-team" in (panel.get("class") or "").split():
                side = "away"
            else:
                side = "home" if index == 0 else "away"
            for el in panel.xpath(f'.//div[{_cls("player")}]'):
                num = el.xpath("./strong")
                if not num:
                    continue
                raw_name = (num[0].tail or "").strip()
                name = re.sub(r"\s*\(GR\)\s*$", "", raw_name).strip()
                if not name:
                    continue
                src = (el.xpath('.//div[contains(@class,"photo")]/img/@src') or [""])[0]
                pid = re.search(r"/Player/Logo/(\d+)", src)
                goals = 0
                gtxt = el.xpath(f'.//*[{_cls("icon-goal")}]/span')
                if gtxt and _text(gtxt[0]).isdigit():
                    goals = int(_text(gtxt[0]))
                target[side].append(RosterPlayer(
                    number=_text(num[0]), name=name, goalkeeper="(GR)" in raw_name,
                    fpf_id=pid.group(1) if pid else None, roster_goals=goals,
                ))
    if not found_lineups or not (starters["home"] or starters["away"]):
        raise MatchDataError("Not an FPF match report: starting lineups ('Equipas Iniciais') not found.")

    periods: list[Period] = []
    events: list[Event] = []
    for pi, title_el in enumerate(doc.xpath(f'//*[{_cls("timeline-title")}]'), start=1):
        wrapper = title_el.getnext()
        if wrapper is None:
            continue
        end = wrapper.xpath(f'.//*[{_cls("end-game")}]')
        stamp = parse_stamp(_text(end[0])) if end else None
        periods.append(Period(_text(title_el), stamp[0] if stamp else None, stamp[1] if stamp else 0))
        if stamp is None:
            warnings.append(Warn("period_end_missing", f"End marker of block {pi} not readable."))
        for item in wrapper.xpath(f'.//*[{_cls("timeline-item")}]'):
            icons = [
                m2.group(1)
                for src in item.xpath(".//img/@src")
                if (m2 := re.search(r"/(icon-[a-z0-9\-]+)\.png", src))
            ]
            icons = [i for i in icons if i not in _IGNORED_ICONS]
            if not icons:
                continue
            icon = icons[0]
            top = item.xpath(f'.//*[{_cls("top-tag")}]')
            bottom = item.xpath(f'.//*[{_cls("bottom-tag")}]')
            st = parse_stamp(_text(top[0])) if top else None
            if st is None or not bottom:
                warnings.append(Warn("event_unreadable", f"Event with icon '{icon}' has no readable minute or participants."))
                continue
            etype = _KNOWN_ICONS.get(icon)
            if etype is None and "goal" in icon:
                etype = "goal"
                warnings.append(Warn(
                    "goal_icon_variant",
                    f"Icon '{icon}' treated as a goal; check penalty / own-goal attribution manually."))
            raw = _text(bottom[0])
            ev = Event(period=pi, base=st[0], added=st[1], type=etype or "unknown", icon=icon, label=raw)
            names = bottom[0].xpath(".//strong")
            if ev.type == "goal":
                rs = re.search(r"(\d+)\s*-\s*(\d+)", raw)
                ev.running_score = (int(rs.group(1)), int(rs.group(2))) if rs else None
                ev.scorer = _text(names[0]) if names else None
            elif ev.type == "substitution":
                i_el = bottom[0].xpath(f'.//*[{_cls("in")}]')
                o_el = bottom[0].xpath(f'.//*[{_cls("out")}]')
                ev.in_name = _text(i_el[0]) if i_el else None
                ev.out_name = _text(o_el[0]) if o_el else None
            elif ev.type in ("yellow", "double_yellow", "red"):
                ev.player = _text(names[0]) if names else raw
            else:
                warnings.append(Warn("unknown_event", f"Unrecognised event '{icon}' at {st[0]}': {raw}. Not counted."))
            events.append(ev)

    return ParsedMatch(
        source_name=source_name, fpf_match_id=mid.group(1) if mid else None,
        competition=competition, date=date, home=home, away=away, score=score,
        periods=periods, starters=starters, substitutes=substitutes, events=events, warnings=warnings,
    )
