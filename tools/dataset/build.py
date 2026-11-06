"""Build the playable dataset (acervo v2).

    PYTHONPATH=tools .venv-data/bin/python -m dataset.build

Reads pools (curated JSON + Wikidata + pt.wikipedia categories), attaches
empirical metrics, computes the rarity percentile inside each prompt, applies
the documented overrides (curated/overrides.json) and writes
public/data/garimpo.json plus reports/dataset.md.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .features import genders_for, positions_for, years_for
from .http import normalize, sparql, chunks
from .measure import composite, crawl_pageviews, uniform_rarity, zipf_map
from .question_bank import build as build_prompts
from .sources import CURATED, DROPPED_POOLS, city_key, load_all, merge
from .tagging import GLOBAL_ALIASES, aliases_for, apply_tags, positions_from_labels
from .wdpools import aliases_for_qids

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public" / "data" / "garimpo.json"
REPORT = ROOT / "reports" / "dataset.md"
AUDIT = ROOT / "tools" / "coverage" / "build_audit.json"

DISPLAY_STRIP = {
    "rio": ["Rio "],
    "parque": ["Parque Nacional da ", "Parque Nacional do ", "Parque Nacional de ",
               "Parque Nacional dos ", "Parque Nacional das ", "Parque Nacional "],
    "estadio": ["Estádio ", "Estadio "],
}
LEADING_PARTICLES = re.compile(r"^(do|da|de|dos|das)\s+", re.IGNORECASE)
PAREN = re.compile(r"\s*\([^)]*\)\s*$")

# Pools whose Wikidata pt/pt-br labels are safe extra aliases.
WD_ALIAS_POOLS = {
    "uf", "cidade", "cidades_historicas", "presidente", "politico", "rio", "parque", "estadio", "praias",
    "pontos_turisticos", "bairro_rio", "bairro_sp", "jogador", "jogadora", "time", "time_pt",
    "jogador_pt", "volei", "f1", "medalhista", "frutas_nativas", "pratos_tipicos", "doces",
    "bebidas", "cervejas", "prato_pt", "novelas", "filmes", "cantores", "bandas", "cantor_pt",
    "escritores", "escritor_pt", "atores", "apresentador", "humorista", "youtuber",
    "programas_tv", "bbb", "bbb_campeoes", "tv_globinho", "desenhos", "turma_monica",
    "escola_samba", "cientista", "aves", "mamiferos", "folclore", "festas", "dancas",
    "instrumentos", "marcas", "cidade_pt", "pais", "capital_mundo", "elemento", "cidade_mundo",
}
STOP = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "um", "uma"}
BAD_ALIAS = re.compile(r"^(q\d+|\d{1,2})$")


def key(value: str) -> str:
    """Same comparison key as src/game/match.ts key()."""
    return " ".join(t for t in normalize(value).replace("-", " ").split() if t not in STOP)


def display_name(pool: str, name: str) -> str:
    out = PAREN.sub("", name).strip() or name
    for prefix in DISPLAY_STRIP.get(pool, []):
        if out.startswith(prefix):
            out = out[len(prefix):]
            break
    if pool in ("parque", "estadio"):
        out = LEADING_PARTICLES.sub("", out)
    return out.strip()


def tidy(pools: dict[str, list[dict]]) -> None:
    for pool, entries in pools.items():
        for entry in entries:
            original = entry["name"]
            entry["name"] = display_name(pool, original)
            if entry["name"] != original:
                entry.setdefault("aliases", []).append(original)
        pools[pool] = merge(entries, keyfn=city_key if pool == "cidade" else None)


def foreign_novelas(entries: list[dict]) -> set[str]:
    """QIDs of telenovelas whose country of origin is set and is not Brazil."""
    qids = [e["qid"] for e in entries if e.get("qid")]
    foreign: set[str] = set()
    for batch in chunks(list(dict.fromkeys(qids)), 150):
        values = " ".join(f"wd:{q}" for q in batch)
        rows = sparql(f"""SELECT ?item (GROUP_CONCAT(STR(?c)) AS ?cs) WHERE {{
              VALUES ?item {{ {values} }} ?item wdt:P495 ?c . }} GROUP BY ?item""")
        for row in rows:
            countries = row.get("cs") or ""
            if "Q155" not in countries:
                foreign.add(row["item"].rsplit("/", 1)[-1])
    return foreign


def attach_features(pools: dict[str, list[dict]]) -> None:
    for pool in ("novelas", "filmes"):
        entries = pools.get(pool, [])
        years = years_for(entries)
        for entry in entries:
            year = years.get(entry.get("qid") or "")
            if year and not entry["attrs"].get("ano"):
                entry["attrs"]["ano"] = year
    if pools.get("novelas"):
        foreign = foreign_novelas(pools["novelas"])
        pools["novelas"] = [e for e in pools["novelas"] if e.get("qid") not in foreign]
    for pool in ("cantores", "atores", "escritores", "apresentador", "humorista", "youtuber",
                 "volei", "bbb"):
        entries = pools.get(pool, [])
        genders = genders_for([e for e in entries if not e["attrs"].get("genero")])
        for entry in entries:
            gender = genders.get(entry.get("qid") or "")
            if gender and not entry["attrs"].get("genero"):
                entry["attrs"]["genero"] = gender
    positions = positions_for(pools.get("jogador", []))
    for entry in pools.get("jogador", []):
        labels = positions.get(entry.get("qid") or "") or []
        tagged = positions_from_labels(labels)
        current = entry["attrs"].get("posicao")
        if current:
            extra = current if isinstance(current, list) else [current]
            tagged = list(dict.fromkeys([*extra, *tagged]))
        if tagged:
            entry["attrs"]["posicao"] = tagged


# A person pulled from Wikidata by a secondary occupation ("ator": Pelé, Roberto
# Carlos, Silvio Santos) is not what a player means. Non-curated entries of these
# pools are dropped when the same QID belongs to a pool of their main fame.
PRIMARY_FAME = {
    "atores": ("jogador", "cantores", "bandas", "politico", "apresentador", "youtuber"),
    "apresentador": ("jogador", "cantores", "politico"),
    "humorista": ("jogador", "cantores", "politico"),
    "politico": ("jogador", "cantores"),
    "escritores": ("politico",),
}  # acyclic on purpose: an entry is never dropped from both sides


def drop_secondary_fame(pools: dict[str, list[dict]]) -> dict[str, int]:
    qids = {pool: {e["qid"] for e in pools.get(pool, []) if e.get("qid")} for pool in
            {p for others in PRIMARY_FAME.values() for p in others}}
    dropped: dict[str, int] = {}
    for pool, others in PRIMARY_FAME.items():
        keep = []
        for entry in pools.get(pool, []):
            q = entry.get("qid")
            if not entry.get("curated") and q and any(q in qids[o] for o in others):
                dropped[pool] = dropped.get(pool, 0) + 1
                continue
            keep.append(entry)
        pools[pool] = keep
    return dropped


def attach_wd_aliases(pools: dict[str, list[dict]]) -> None:
    qids = [e["qid"] for pool in WD_ALIAS_POOLS for e in pools.get(pool, []) if e.get("qid")]
    labels = aliases_for_qids(qids)
    for pool in WD_ALIAS_POOLS:
        for entry in pools.get(pool, []):
            found = labels.get(entry.get("qid") or "") or []
            entry["wd_aliases"] = [display_name(pool, a) for a in found
                                   if len(key(a).split()) <= 4][:12]


PEOPLE_POOLS = {
    "presidente", "politico", "cientista", "jogador", "jogadora", "jogador_pt", "volei", "f1",
    "medalhista", "cantores", "cantor_pt", "escritores", "escritor_pt", "atores",
    "apresentador", "humorista", "youtuber", "bbb", "bbb_campeoes",
}
SHORT_MIN_SL = 12


def short_form_owners(pools: dict[str, list[dict]]) -> dict[str, dict[str, set[str]]]:
    """Per people pool: surname key -> names that carry it (to keep only unambiguous ones)."""
    out: dict[str, dict[str, set[str]]] = {}
    for pool in PEOPLE_POOLS:
        owners: dict[str, set[str]] = {}
        for entry in pools.get(pool, []):
            toks = key(entry["name"]).split()
            if len(toks) >= 2:
                owners.setdefault(toks[-1], set()).add(entry["name"])
            for alias in [*(entry.get("aliases") or []), *(entry.get("wd_aliases") or [])]:
                k = key(alias)
                if k and len(k.split()) == 1:
                    owners.setdefault(k, set()).add(entry["name"])
        out[pool] = owners
    return out


def clean_aliases(prompt: dict, *, global_names: dict[str, set[str]] | None = None,
                  surnames: dict[str, set[str]] | None = None) -> None:
    """Keep aliases that point to one answer only and do not equal another
    answer's name; drop junk. Adds unambiguous surnames for well-known people."""
    global_names = global_names or {}
    owners: dict[str, set[int]] = {}
    names = {key(a["name"]): i for i, a in enumerate(prompt["answers"])}
    candidates: list[list[str]] = []
    trusted: list[set[str]] = []
    for i, answer in enumerate(prompt["answers"]):
        raw = aliases_for(answer, prompt["cat"])
        trusted.append({key(a) for a in (answer.get("aliases") or [])}
                       | {key(a) for a in GLOBAL_ALIASES.get((prompt["cat"], normalize(answer["name"])), [])})
        toks = key(answer["name"]).split()
        if (surnames is not None and len(toks) >= 2 and (answer.get("sl") or 0) >= SHORT_MIN_SL
                and len(toks[-1]) >= 4 and len(surnames.get(toks[-1], ())) == 1
                and not (global_names.get(toks[-1], set()) - {answer["name"]})):
            raw = [*raw, answer["name"].split()[-1]]
        mine: list[str] = []
        seen = {key(answer["name"])}
        for alias in raw:
            alias = alias.strip()
            k = key(alias)
            if not k or k in seen or len(alias) > 60 or BAD_ALIAS.match(k):
                continue
            if len(k) < 2 or any(ord(c) > 0x24F and c.isalpha() for c in alias):
                continue
            seen.add(k)
            mine.append(alias)
            owners.setdefault(k, set()).add(i)
        candidates.append(mine)
    for i, answer in enumerate(prompt["answers"]):
        keep = []
        for alias in candidates[i]:
            k = key(alias)
            if len(owners.get(k, ())) > 1:
                continue
            if k in names and names[k] != i:
                continue
            # A one-word alias that is the full name of something else in the
            # catalogue ("Barcelona", "Grêmio", "Ronaldo") is not safe.
            if (len(k.split()) == 1 and k not in trusted[i]
                    and global_names.get(k, set()) - {answer["name"]}):
                continue
            keep.append(alias)
        answer["clean_aliases"] = keep[:14]


def load_overrides() -> list[dict]:
    path = CURATED / "overrides.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("overrides", [])


def apply_overrides(prompt: dict, ranked: list[dict], overrides: list[dict]) -> list[str]:
    """Clamp the measured rarity of named answers (documented, one reason each)."""
    applied = []
    for rule in overrides:
        scope = rule.get("prompts") or []
        pools = rule.get("pools") or []
        if scope and prompt["id"] not in scope:
            continue
        if pools and prompt["cat"] not in pools:
            continue
        if not scope and not pools:
            continue
        target = key(rule["name"])
        for answer in ranked:
            if key(answer["n"]) != target:
                continue
            rarity = answer["rarity"]
            if "max_rarity" in rule:
                rarity = min(rarity, rule["max_rarity"])
            if "min_rarity" in rule:
                rarity = max(rarity, rule["min_rarity"])
            if rarity != answer["rarity"]:
                answer["rarity"] = round(rarity, 4)
                answer["popPercentile"] = round(1 - rarity, 4)
                answer["points"] = round(1 + 9 * (rarity ** 1.15))
                applied.append(f"{prompt['id']}: {answer['n']} -> {rarity:.2f}")
    return applied


def main() -> int:
    pools = load_all()
    tidy(pools)
    apply_tags(pools)
    print("secondary-fame dropped:", drop_secondary_fame(pools))
    attach_features(pools)
    attach_wd_aliases(pools)
    prompts = build_prompts(pools)
    print(f"pools={len(pools)} prompts={len(prompts)} dropped={getattr(build_prompts, 'dropped', [])}")

    articles = sorted({a["article"] for p in prompts for a in p["answers"] if a.get("article")})
    pageviews = crawl_pageviews(articles, workers=4)

    # Verification guard: a non-curated answer with no pt.wikipedia attention and
    # no Wikidata sitelink was never confirmed to exist, so it does not ship.
    dropped = 0
    for prompt in prompts:
        usable = []
        for answer in prompt["answers"]:
            article = answer.get("article") or ""
            views = pageviews.get(article)
            if not answer.get("curated") and (views is None or views == 0) and not (answer.get("sl") or 0):
                dropped += 1
                continue
            usable.append(answer)
        prompt["answers"] = usable
    prompts = [prompt for prompt in prompts if len(prompt["answers"]) >= (9 if prompt["id"] == "pais-lusofono" else 12)]
    print(f"unverified answers dropped={dropped} prompts after guard={len(prompts)}")

    names = list(dict.fromkeys(a["name"] for p in prompts for a in p["answers"]))
    zipfs = zipf_map(names)
    overrides = load_overrides()
    applied_overrides: list[str] = []

    total_answers = 0
    unique_answers: set[str] = set()
    audit: dict[str, dict] = {}
    global_names: dict[str, set[str]] = {}
    for prompt in prompts:
        for answer in prompt["answers"]:
            global_names.setdefault(key(answer["name"]), set()).add(answer["name"])
    surname_index = short_form_owners(pools)
    for prompt in prompts:
        clean_aliases(prompt, global_names=global_names,
                      surnames=surname_index.get(prompt["cat"]) if prompt["cat"] in PEOPLE_POOLS else None)
        prepared = []
        for answer in prompt["answers"]:
            article = answer.get("article")
            prepared.append({
                "n": answer["name"],
                "a": answer["clean_aliases"],
                "qid": answer.get("qid"),
                "pv": pageviews.get(article) if article else None,
                "sl": answer.get("sl") or 0,
                "wf": zipfs.get(answer["name"], 0.0),
                "g": answer.get("gravity"),
                "an": answer.get("attrs", {}).get("ano"),
            })
        ranked = composite(prepared)
        # The composite decides the *order*; the flat percentile is what the game
        # reads. It also replaces the old TOP_OBVIOUS clamp: with a percentile by
        # rank, the most famous answer of every pool is 0.0 by construction.
        ranked = uniform_rarity(ranked)
        applied_overrides += apply_overrides(prompt, ranked, overrides)
        ranked.sort(key=lambda a: a["popPercentile"], reverse=True)
        for rank, answer in enumerate(ranked, start=1):
            answer["rank"] = rank
            if answer.get("an") is None:
                answer.pop("an", None)
            if answer.get("qid") is None:
                answer.pop("qid", None)
        prompt["answers"] = ranked
        total_answers += len(ranked)
        unique_answers.update(a["n"] for a in ranked)
        audit[prompt["id"]] = {
            "text": prompt["text"], "n": len(ranked),
            "obvious": [a["n"] for a in ranked[:5]],
            "rarest": [a["n"] for a in ranked[-5:]],
        }

    payload = {
        "builtAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "method": {
            "version": 2,
            "weights": {"pageviews_pt": 0.50, "wikidata_sitelinks": 0.25,
                        "wordfreq_zipf_pt": 0.20, "gravity": 0.05},
            "pageviewsWindow": "last 60 days (pt.wikipedia action API prop=pageviews), scaled to a monthly mean",
            "pointsFormula": "k = clamp(round(1 + 9 * rarity^1.15), 1, 10)",
            "rarityDefinition": "percentile of the answer inside its prompt's measured order "
                                "(order = 1 - weighted mean of within-prompt percentile ranks of "
                                "pageviews, sitelinks, wordfreq and gravity; documented manual "
                                "clamps in tools/dataset/curated/overrides.json)",
            "shareFormula": "softmax of weighted z-scores within the prompt pool",
            "depthPerPoint": 10,
            "sources": [
                {"name": "Wikidata Query Service", "url": "https://query.wikidata.org/"},
                {"name": "Wikimedia Pageviews API (pt.wikipedia)",
                 "url": "https://wikimedia.org/api/rest_v1/metrics/pageviews/"},
                {"name": "wordfreq 3.x, Portuguese", "url": "https://github.com/rspeer/wordfreq"},
                {"name": "pt.wikipedia API (categorias e listas)", "url": "https://pt.wikipedia.org/w/api.php"},
                {"name": "Curadoria verificada (tools/dataset/curated)", "url": "https://pt.wikipedia.org/"},
            ],
        },
        "stats": {
            "prompts": len(prompts),
            "answers": total_answers,
            "uniqueAnswers": len(unique_answers),
            "withPageviews": sum(1 for p in prompts for a in p["answers"] if a["pv"]),
            "pools": {k: len(v) for k, v in pools.items() if v},
        },
        "prompts": [
            {"id": p["id"], "text": p["text"], "cat": p["cat"], "answers": p["answers"]}
            for p in prompts
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps({"overrides": applied_overrides, "prompts": audit,
                                 "droppedPrompts": getattr(build_prompts, "dropped", []),
                                 "droppedPools": DROPPED_POOLS},
                                ensure_ascii=False, indent=1), encoding="utf-8")

    tiers = [(0.40, "Óbvia"), (0.65, "Comum"), (0.82, "Boa"), (0.95, "Rara"), (1.01, "Raríssima")]
    lines = ["# Dataset do Garimpo", "",
             f"Gerado em {payload['builtAt']}.", "",
             f"- perguntas: **{len(prompts)}**",
             f"- respostas catalogadas: **{total_answers}**",
             f"- respostas únicas: **{len(unique_answers)}**",
             f"- respostas com pageviews: **{payload['stats']['withPageviews']}**", "",
             "| pergunta | pool | respostas | Óbvia | Comum | Boa | Rara | Raríssima |",
             "|---|---|---|---|---|---|---|---|"]
    for p in payload["prompts"]:
        counts = [0] * len(tiers)
        for a in p["answers"]:
            for i, (edge, _) in enumerate(tiers):
                if a["rarity"] < edge:
                    counts[i] += 1
                    break
        lines.append(f"| {p['text']} | {p['cat']} | {len(p['answers'])} | "
                     + " | ".join(str(c) for c in counts) + " |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
