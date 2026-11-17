#!/usr/bin/env python3
"""Récupère les séances AlloCiné de toutes les salles de cinemas.json.

Écrit un fichier par département : data/<dep>.json (films + séances des salles du département).
Seules les zones de ZONES sont récupérées, à un rythme raisonnable pour ne pas être bloqué par AlloCiné.
Usage : python3 fetch_seances.py [nb_jours]   (défaut : 3 jours à partir d'aujourd'hui)
"""
import json, os, re, sys, time, threading, datetime, urllib.error, urllib.request, concurrent.futures as cf

# Départements couverts (2 premiers chiffres du code postal) + Paris.
ZONES = {"22", "29", "35", "56",            # Bretagne
         "44", "33",                        # Nantes, Bordeaux
         "75", "92", "93", "94",            # Paris et petite couronne
         "69", "13", "31", "59", "34", "67", "06"}  # Lyon, Marseille, Toulouse, Lille, Montpellier, Strasbourg, Nice
RATE = 0.5          # requêtes par seconde, au maximum (au-delà, AlloCiné bloque)
_lock, _next = threading.Lock(), [0.0]


def _wait_turn():
    with _lock:
        now = time.time()
        t = max(now, _next[0])
        _next[0] = t + 1.0 / RATE
    time.sleep(max(0, t - now))

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def get(url, tries=4):
    for i in range(tries):
        _wait_turn()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429:  # trop de requêtes : tout le monde fait une pause
                with _lock:
                    _next[0] = max(_next[0], time.time() + 60)
                if i == tries - 1:
                    raise
                continue
            if i == tries - 1:
                raise
            time.sleep(2 + i * 3)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 + i * 3)


def person(p):
    return " ".join(x for x in (p.get("firstName"), p.get("lastName")) if x)


def movie_info(m):
    st = m.get("stats") or {}
    rel = (m.get("releases") or [{}])[0] or {}

    def score(k):
        v = st.get(k) or {}
        return (round(v["score"], 1) if v.get("score") else None), v.get("count")

    u, uc = score("userRating")
    p, pc = score("pressReview")
    return {
        "t": m.get("title"), "ot": m.get("originalTitle"),
        "p": (m.get("poster") or {}).get("path"), "rt": m.get("runtime"),
        "g": [g["translate"] for g in (m.get("genres") or [])][:3],
        "d": ", ".join(person(c["person"]) for c in (m.get("credits") or [])
                       if (c.get("position") or {}).get("name") == "DIRECTOR"),
        "c": [person(n["actor"]) for n in ((m.get("cast") or {}).get("nodes") or []) if n.get("actor")][:3],
        "s": re.sub(r"\s+", " ", m.get("synopsis") or "").strip(),
        "u": u, "uc": uc, "pr": p, "pc": pc,
        "rd": (rel.get("releaseDate") or {}).get("date"),
        "ce": (rel.get("certificate") or {}).get("label"),
    }


def day(cid, d):
    """[(movie_id, movie, [séances])] pour une salle et un jour."""
    out, page, total = [], 1, 1
    while page <= total:
        j = json.loads(get(f"https://www.allocine.fr/_/showtimes/theater-{cid}/d-{d}/p-{page}/"))
        total = (j.get("pagination") or {}).get("totalPages") or 1
        for r in j.get("results") or []:
            m = r.get("movie")
            if not m:
                continue
            seances = []
            for lst in (r.get("showtimes") or {}).values():
                for s in lst:
                    fx = [x for x in (s.get("projection") or []) if x != "DIGITAL"]
                    fx += (s.get("experience") or []) + (s.get("sound") or [])
                    e = {"h": s["startsAt"][11:16], "v": "VO" if s.get("diffusionVersion") == "ORIGINAL" else "VF"}
                    if fx:
                        e["fx"] = fx
                    seances.append(e)
            if seances:
                seances.sort(key=lambda x: x["h"])
                out.append((str(m.get("internalId")), m, seances))
        page += 1
    return out


def theater(c, days):
    sched, movies, ok = {}, {}, True
    for d in days:
        try:
            rows = day(c["id"], d)
        except Exception:
            ok = False
            continue
        for mid, m, ss in rows:
            sched.setdefault(d, {})[mid] = ss
            if mid not in movies:
                movies[mid] = movie_info(m)
    return c, sched, movies, ok


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=7, help="nombre de jours à récupérer à partir d'aujourd'hui")
    ap.add_argument("--toute-la-france", action="store_true", help="toutes les salles (très long : AlloCiné limite le rythme)")
    a = ap.parse_args()
    today = datetime.date.today()
    days = [(today + datetime.timedelta(i)).isoformat() for i in range(a.jours)]
    cinemas = json.load(open("cinemas.json", encoding="utf-8"))
    if not a.toute_la_france:
        cinemas = [c for c in cinemas if c["dep"] == "paris" or (c.get("cp") or "")[:2] in ZONES]
    print(f"{len(cinemas)} salles, {a.jours} jours", flush=True)
    t0 = time.time()
    old = {}  # dernières séances connues : gardées pour les jours non récupérés et si une salle ne répond pas
    for c in cinemas:
        p = f"data/{c['dep']}.json"
        if c["dep"] not in old:
            try:
                old[c["dep"]] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
            except Exception:
                old[c["dep"]] = None
    by_dep, failed = {}, 0
    with cf.ThreadPoolExecutor(2) as ex:
        for i, (c, sched, movies, ok) in enumerate(ex.map(lambda c: theater(c, days), cinemas), 1):
            if i % 100 == 0:
                print(f"  {i}/{len(cinemas)} salles ({round(time.time() - t0)} s)", flush=True)
            dep = by_dep.setdefault(c["dep"], {"movies": {}, "cinemas": {}})
            prev = old.get(c["dep"])
            if not ok:
                failed += 1
            if prev and c["id"] in prev["cinemas"]:
                # jours pas récupérés cette fois (ou salle muette) : on garde ce qu'on savait, sans le passé
                for d, v in prev["cinemas"][c["id"]].items():
                    if d >= days[0] and (d not in days or not ok) and d not in sched:
                        sched[d] = v
                        for mid in v:
                            if mid in prev["movies"]:
                                movies.setdefault(mid, prev["movies"][mid])
            if sched:
                dep["cinemas"][c["id"]] = dict(sorted(sched.items()))
                dep["movies"].update(movies)
    # départements non traités cette fois : on garde leur fichier tel quel
    if failed:
        print(f"{failed} salles n'ont pas répondu en entier : leurs dernières séances connues sont gardées")
    os.makedirs("data", exist_ok=True)
    updated = datetime.datetime.now().isoformat(timespec="minutes")
    n_ses = 0
    for dep, v in by_dep.items():
        n_ses += sum(len(ss) for sch in v["cinemas"].values() for d in sch.values() for ss in d.values())
        all_days = sorted({d for sch in v["cinemas"].values() for d in sch})
        with open(f"data/{dep}.json", "w", encoding="utf-8") as f:
            json.dump({"updated": updated, "days": all_days, **v}, f, ensure_ascii=False, separators=(",", ":"))
    known = {c["dep"] for c in json.load(open("cinemas.json", encoding="utf-8"))}
    for name in os.listdir("data"):  # départements qui n'existent plus dans cinemas.json
        if name.endswith(".json") and name[:-5] not in known:
            os.remove(os.path.join("data", name))
    n_cin = sum(len(v["cinemas"]) for v in by_dep.values())
    n_mov = len({m for v in by_dep.values() for m in v["movies"]})
    print(f"{n_cin} cinémas avec séances sur {len(cinemas)}, {n_mov} films, {n_ses} séances, "
          f"{a.jours} jours -> data/ ({round(time.time() - t0)} s)")


if __name__ == "__main__":
    main()
