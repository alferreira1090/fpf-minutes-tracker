"""Load a synthetic demo club (invented names) so the UI can be explored without real data.

Usage: python scripts/seed_demo.py [data_dir]      (default: data-demo, git-ignored via data*/ pattern in README)
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from fpf_tracker.services.ingest import IngestService  # noqa: E402
from fpf_tracker.storage.db import Database  # noqa: E402
from tests.fpf_fixture import build_page  # noqa: E402

POOL = [f"Jogador {n}" for n in ["Almeida", "Barros", "Cardoso", "Dias", "Esteves", "Faria", "Gomes", "Henriques", "Inácio",
        "Jordão", "Lopes", "Moreira", "Nogueira", "Oliveira", "Pacheco", "Quintela", "Ramos", "Sampaio", "Teixeira", "Ulisses"]]


def make_match(rng, idx, date, league, opponent, pool, nominal=90, s1=0, s2=3):
    names = rng.sample(pool, 17)
    starters, bench = names[:11], names[11:]
    pid = {n: 5000 + POOL.index(n) for n in names}
    starters_t = [(str(i + 1), n, pid[n], "GR" if i == 0 else "") for i, n in enumerate(starters)]
    bench_t = [(str(12 + i), n, pid[n]) for i, n in enumerate(bench)]
    half = nominal // 2
    subs = rng.sample(range(1, 11), rng.randint(2, 5))
    used = bench[: len(subs)]
    mins = sorted(rng.sample(range(half + 5, nominal - 3), len(subs)))
    second, goals_us, goals_them = [], 0, 0
    for m, out_i, inn in zip(mins, subs, used):
        second.append(("sub", f"{m}'", inn, starters[out_i]))
    events = []
    for _ in range(rng.randint(0, 4)):
        events.append((rng.choice([True, True, False]), rng.randint(5, nominal - 2)))
    first, second_goals = [], []
    for mine, minute in sorted(events, key=lambda x: x[1]):
        if mine:
            goals_us += 1
            scorer = rng.choice(starters[5:])
            ev = ("goal", f"{minute}'", None, scorer)
        else:
            goals_them += 1
            ev = ("goal", f"{minute}'", None, "Adversário Avançado")
        (first if minute <= half else second_goals).append((ev, mine))
    us, them = 0, 0
    first_ev, second_ev = [], []
    for ev, mine in first + second_goals:
        us, them = us + (1 if mine else 0), them + (0 if mine else 1)
        e = ("goal", ev[1], f"{them} - {us}", ev[3])          # tracked club is away: home - away
        (first_ev if (ev, mine) in first else second_ev).append(e)
    second_all = sorted(second + second_ev, key=lambda e: int(e[1].rstrip("'").split("'")[0]))
    if rng.random() < 0.4:
        second_all.insert(0, ("yellow", f"{half + 2}'", rng.choice(starters)))
    home_starters = [(str(i), f"Adv {opponent} {i}", 9000 + i, "GR" if i == 1 else "") for i in range(1, 12)]
    home_starters[8] = ("9", "Adversário Avançado", 9099)
    return build_page(
        home=opponent, away="Beta FC", date=date, competition=league, score=f"{them} - {us}", match_id=str(7000 + idx),
        first_end=f"{half}'" + (f" + {s1}'" if s1 else ""), second_end=f"{nominal}' + {s2}'",
        first_events=first_ev, second_events=second_all, home_starters=home_starters, home_subs=[("12", "Adv Suplente", 9100)],
        away_starters=starters_t, away_subs=bench_t,
    )


def main():
    data = Path(sys.argv[1] if len(sys.argv) > 1 else "data-demo")
    db = Database(data / "fpf.sqlite3")
    sv = IngestService(db, data / "uploads")
    cid = db.get_or_create_club("Beta FC")
    rng = random.Random(7)
    plan = [("Sub-15", "Clube A", "2026-09-20", 86), ("Sub-15", "Clube B", "2026-09-27", 90), ("Sub-15", "Clube C", "2026-10-04", 84),
            ("Sub-15", "Clube D", "2026-10-18", 87), ("Sub-16", "Clube E", "2026-10-25", 93), ("Sub-16", "Clube F", "2026-11-08", 93)]
    for i, (league, opp, date, total) in enumerate(plan, start=1):
        pool = POOL[:18] if league == "Sub-15" else POOL[3:20]       # overlap -> multi-league players
        y, mth, d = date.split("-")
        s2 = 3 if total >= 90 else 0
        nominal = total - s2
        page = make_match(rng, i, f"{d}/{mth}/{y}", league, opp, pool, nominal=nominal - nominal % 2, s2=s2 + nominal % 2)
        out = sv.import_file(cid, f"J{i}.html", page, league_label=league)
        print(out.status, out.league, out.home, "-", out.away, "warnings:", out.warnings)
    print("demo club id", cid, "in", data)


if __name__ == "__main__":
    main()
