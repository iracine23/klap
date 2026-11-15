#!/usr/bin/env python3
"""Récupère les séances AlloCiné des cinémas suivis et écrit seances.json.

Usage : python3 fetch_seances.py [nb_jours]   (défaut : 4 jours à partir d'aujourd'hui)
"""
import json, re, sys, html, base64, datetime, urllib.request, concurrent.futures as cf

# id AlloCiné -> (ville affichée, lat, lng, adresse)
CINEMAS = {
    "P0091": ("Rennes", 48.10915, -1.68390, "12 quai Duguay-Trouin"),
    "P0084": ("Rennes", 48.10370, -1.67270, "11 rue de Châtillon"),
    "P0102": ("Rennes", 48.10600, -1.67120, "1 rue Saint-Hélier"),
    "P4093": ("Rennes", 48.21500, -1.74200, "ZAC Cap Malo, La Mézière"),
    "P0328": ("Lannion", 48.73120, -3.45870, "34 avenue du Général de Gaulle"),
    "W3321": ("Langon", 44.55250, -0.24930, "Langon"),
    "P0280": ("Saint-Malo", 48.64530, -2.00780, "Saint-Malo"),
}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8")


def name_of(cid):
    t = re.search(r"<title>([^<]*)", get(f"https://www.allocine.fr/seance/salle_gen_csalle={cid}.html"))
    t = html.unescape(t.group(1)) if t else cid
    m = re.match(r"Cinéma (.*?) à (.*?) \((\d{5})", t)
    return (m.group(1).strip(), m.group(2).strip(), m.group(3)) if m else (t, "", "")


def poster_data(path):
    """Affiche miniature en data URI (le visualiseur bloque les images externes)."""
    if not path:
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://fr.web.img6.acsta.net/c_160_213" + path, headers=UA), timeout=30) as r:
            return "data:image/jpeg;base64," + base64.b64encode(r.read()).decode()
    except Exception:
        return None


def person(p):
    return " ".join(x for x in (p.get("firstName"), p.get("lastName")) if x)


def movie_info(m):
    st = m.get("stats") or {}
    rel = (m.get("releases") or [{}])[0] or {}
    def score(k):
        v = (st.get(k) or {})
        return (round(v["score"], 1) if v.get("score") else None), v.get("count")
    u, uc = score("userRating")
    p, pc = score("pressReview")
    poster = (m.get("poster") or {}).get("path")
    return {
        "t": m.get("title"), "ot": m.get("originalTitle"),
        "p": poster, "rt": m.get("runtime"),
        "g": [g["translate"] for g in (m.get("genres") or [])][:3],
        "d": ", ".join(person(c["person"]) for c in (m.get("credits") or [])
                       if (c.get("position") or {}).get("name") == "DIRECTOR"),
        "c": [person(n["actor"]) for n in ((m.get("cast") or {}).get("nodes") or []) if n.get("actor")][:3],
        "s": re.sub(r"\s+", " ", m.get("synopsis") or "").strip(),
        "u": u, "uc": uc, "pr": p, "pc": pc,
        "rd": ((rel.get("releaseDate") or {}).get("date")),
        "ce": ((rel.get("certificate") or {}).get("label")),
        "id": m.get("internalId"),
    }


def day(cid, d):
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
                    seances.append({"h": s["startsAt"][11:16],
                                    "v": "VO" if s.get("diffusionVersion") == "ORIGINAL" else "VF",
                                    "fx": fx})
            seances.sort(key=lambda x: x["h"])
            out.append((movie_info(m), seances))
        page += 1
    return out


def main():
    ndays = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    today = datetime.date.today()
    days = [(today + datetime.timedelta(i)).isoformat() for i in range(ndays)]
    movies, cinemas = {}, []
    with cf.ThreadPoolExecutor(8) as ex:
        names = dict(zip(CINEMAS, ex.map(name_of, CINEMAS)))
        jobs = {(c, d): ex.submit(day, c, d) for c in CINEMAS for d in days}
    for cid, (city, lat, lng, addr) in CINEMAS.items():
        nm, town, cp = names[cid]
        sched = {}
        for d in days:
            for info, seances in jobs[(cid, d)].result():
                movies.setdefault(str(info["id"]), info)
                if seances:
                    sched.setdefault(d, {})[str(info["id"])] = seances
        cinemas.append({"id": cid, "name": nm, "town": town, "cp": cp, "city": city,
                        "lat": lat, "lng": lng, "addr": addr, "days": sched})
    data = {"updated": datetime.datetime.now().isoformat(timespec="minutes"),
            "days": days, "movies": movies, "cinemas": cinemas}
    with open("seances.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n = sum(len(v) for c in cinemas for d in c["days"].values() for v in d.values())
    print(f"{len(cinemas)} cinémas, {len(movies)} films, {n} séances -> seances.json")
    for c in cinemas:
        print(" ", c["id"], c["name"], "-", c["town"], c["cp"], "| jours:", list(c["days"]))


if __name__ == "__main__":
    main()
