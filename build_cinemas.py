#!/usr/bin/env python3
"""Construit cinemas.json : toutes les salles AlloCiné de France, avec adresse et coordonnées.

À relancer de temps en temps (nouvelles salles, fermetures) :  python3 build_cinemas.py
Coordonnées : Base Adresse Nationale (api-adresse.data.gouv.fr).
"""
import json, re, html, time, urllib.parse, urllib.request, concurrent.futures as cf

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 + i * 3)


def departments():
    h = get("https://www.allocine.fr/salle/")
    seen, out = set(), []
    for did, name in re.findall(r'href="/salle/cinema/departement-(\d+)/"[^>]*>\s*([^<]+?)\s*<', h):
        if did not in seen:
            seen.add(did)
            out.append((did, html.unescape(name)))
    return out


def theaters_of(did, kind="departement"):
    res, page, last = [], 1, 1
    while True:
        h = get(f"https://www.allocine.fr/salle/cinema/{kind}-{did}/" + (f"?page={page}" if page > 1 else ""))
        cards = h.split('class="theater-card')[1:]
        for c in cards:
            m = re.search(r'data-theater="([^"]+)"', c)
            if not m:
                continue
            t = json.loads(html.unescape(m.group(1)))
            txt = html.unescape(re.sub(r"<[^>]+>", "|", c[:5000]))
            parts = [p.strip() for p in txt.split("|") if p.strip()]
            addr = ""
            for i, p in enumerate(parts):
                if p == t["name"].strip() and i + 1 < len(parts):
                    addr = re.sub(r"\s+", " ", parts[i + 1])
                    break
            res.append({"id": t["id"], "name": t["name"].strip(), "address": addr})
        last = max([last] + [int(x) for x in re.findall(r"\?page=(\d+)", h)])
        if not cards or page >= last:
            break
        page += 1
    return res


def geocode(addr):
    """Coordonnées via la Base Adresse Nationale ; si l'adresse exacte échoue, on se replie sur code postal + ville."""
    def ask(q, extra=""):
        for i in range(4):
            try:
                j = json.loads(get(f"https://api-adresse.data.gouv.fr/search/?q={urllib.parse.quote(q)}&limit=1{extra}"))
                return (j.get("features") or [None])[0]
            except Exception:
                time.sleep(1 + i * 2)
        return None
    f = ask(addr) if addr else None
    if not f:
        m = re.search(r"(\d{5})\s+(.+)$", addr or "")
        if m:
            f = ask(f"{m.group(2)} {m.group(1)}", "&type=municipality")
    if not f:
        return None
    lng, lat = f["geometry"]["coordinates"]
    p = f["properties"]
    return {"lat": round(lat, 5), "lng": round(lng, 5), "town": p.get("city", ""), "cp": p.get("postcode", ""),
            "score": round(p.get("score", 0), 2)}


PARIS = ("115755", "paris")  # Paris n'est pas listée comme département sur AlloCiné


def finish(ths):
    with cf.ThreadPoolExecutor(4) as ex:  # la BAN limite le nombre d'appels par seconde
        for t, g in zip(ths, ex.map(lambda t: geocode(t["address"]), ths)):
            if g:
                t.update(g)
    return [{"id": t["id"], "name": t["name"], "addr": t["address"], "town": t.get("town", ""), "cp": t.get("cp", ""),
             "dep": t["dep"], "lat": t["lat"], "lng": t["lng"]} for t in ths if "lat" in t]


def add_paris():
    cur = json.load(open("cinemas.json", encoding="utf-8"))
    cur = [c for c in cur if c["dep"] != "paris"]
    known = {c["id"] for c in cur}
    ts = [dict(t, dep="paris") for t in theaters_of(PARIS[0], "ville") if t["id"] not in known]
    new = finish(ts)
    print(len(new), "salles à Paris")
    with open("cinemas.json", "w", encoding="utf-8") as f:
        json.dump(cur + new, f, ensure_ascii=False, separators=(",", ":"))


def main():
    import sys
    if "--paris" in sys.argv:
        return add_paris()
    deps = departments()
    print(len(deps), "départements")
    allt = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for (did, dname), ts in zip(deps, ex.map(lambda d: theaters_of(d[0]), deps)):
            for t in ts:
                t["dep"] = did
                t["depName"] = dname
                allt.setdefault(t["id"], t)
    for t in theaters_of(PARIS[0], "ville"):
        allt.setdefault(t["id"], dict(t, dep="paris"))
    print(len(allt), "salles")
    out = sorted(finish(list(allt.values())), key=lambda t: (t["dep"], t["name"]))
    print(len(out), "salles géolocalisées")
    with open("cinemas.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
