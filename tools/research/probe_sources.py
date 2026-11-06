"""Testa se fontes alternativas contêm as respostas que faltam no pool (ver miss_rate.py)."""
import json, time, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GarimpoResearch/1.0 (educational trivia game; research script)"}
def get(url):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(2)
    return {"_error": str(err)}
q = urllib.parse.quote
BRANDS = ["Kuat","Toddy","Toddynho","Trakinas","Club Social","Passatempo","Negresco","Guaravita","Xereta","Frisante","Teem","H2OH","Schin","São Geraldo","Sazón","Maggi","Omo","Fanta","Pakera","Itubaína"]
WORDS = ["cafezinho","café com leite","pistola","hater","mungunzá","macaxeira","churros","brownie","lacrar","tankar","cringe","biscoiteiro","gado","mitar","flopar","sextou"]
WD = ["Kuat","Toddy","Trakinas","Guaravita","Xereta","Teem","H2OH!","Schin","Toddynho","Club Social","Negresco","Passatempo","cafezinho","mungunzá","Sazón"]
NAMES = ["gil","zeze","pablo","anitta","ivete","xuxa"]
res = {"off": {}, "wikt": {}, "wd": {}, "ibge": {}}
for b in BRANDS:
    tag = urllib.parse.quote(b.lower().replace(" ", "-").replace("ã","a").replace("ç","c").replace("ó","o").replace("í","i"))
    d = get(f"https://world.openfoodfacts.org/api/v2/search?brands_tags={tag}&countries_tags_en=brazil&fields=product_name,brands&page_size=3")
    res["off"][b] = {"count": d.get("count"), "ex": [p.get("product_name") for p in d.get("products", [])][:3], "err": d.get("_error")}
    print("OFF", b, res["off"][b]["count"], res["off"][b]["ex"]); time.sleep(1)
for w in WORDS:
    d = get(f"https://pt.wiktionary.org/w/api.php?action=query&format=json&redirects=1&prop=categories&cllimit=50&titles={q(w)}")
    page = next(iter(d.get("query", {}).get("pages", {}).values()), {})
    cats = [c["title"].split(":",1)[1] for c in page.get("categories", [])]
    res["wikt"][w] = {"exists": "missing" not in page and bool(page), "cats": [c for c in cats if any(k in c.lower() for k in ("gíria","coloquial","regionalismo","brasil","culinária","bebida","informal"))][:6]}
    print("WIKT", w, res["wikt"][w]); time.sleep(0.5)
for w in WD:
    d = get(f"https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=pt&uselang=pt&limit=3&search={q(w)}")
    res["wd"][w] = [(s["id"], s.get("description","")) for s in d.get("search", [])]
    print("WD", w, res["wd"][w]); time.sleep(0.5)
for n in NAMES:
    d = get(f"https://servicodados.ibge.gov.br/api/v2/censos/nomes/{n}")
    tot = sum(x["frequencia"] for x in d[0]["res"]) if isinstance(d, list) and d else None
    res["ibge"][n] = tot; print("IBGE", n, tot)
Path(__file__).with_name("probe_sources.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
