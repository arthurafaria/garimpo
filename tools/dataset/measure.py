"""Empirical popularity metrics for each answer.

Three independent measurements, all reproducible:

  pv  monthly page views on pt.wikipedia (Wikimedia REST, 12-month mean)
  sl  number of Wikipedia language editions with an article (Wikidata sitelinks)
  wf  wordfreq Zipf frequency for Portuguese (bundled multi-corpus frequency)

The composite is a weighted mean of within-pool percentile ranks, so the
rarity of an answer is always *relative to the other answers of that prompt*.
"""
from __future__ import annotations

import json
import math
import threading
import time
from datetime import date
from importlib import import_module
from urllib.parse import quote

from .http import CACHE, _session, read_json

PV_PATH = CACHE / "pageviews.json"
PV_URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
          "pt.wikipedia/all-access/user/{article}/monthly/{start}/{end}")

# Wikimedia refuses bursts. One global gate, ~5 requests/second, is plenty.
MIN_INTERVAL = 0.18
_gate = threading.Lock()
_last_call = [0.0]


def _throttle() -> None:
    with _gate:
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()

WEIGHTS = {"pv": 0.50, "sl": 0.25, "wf": 0.20, "gravity": 0.05}


def _months() -> tuple[str, str]:
    today = date.today()
    end = date(today.year, today.month, 1)
    start_month = today.month - 12
    start_year = today.year
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = date(start_year, start_month, 1)
    return start.strftime("%Y%m%d00"), end.strftime("%Y%m%d00")


def _fetch_one(article: str, start: str, end: str) -> int | None:
    url = PV_URL.format(article=quote(article.replace(" ", "_"), safe=""), start=start, end=end)
    for attempt in range(4):
        _throttle()
        try:
            r = _session.get(url, timeout=25)
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 429:
            wait = r.headers.get("Retry-After")
            time.sleep(min(float(wait), 60) if wait and wait.isdigit() else 8 * (attempt + 1))
            continue
        if r.status_code == 404:
            return 0
        try:
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
            continue
        if not items:
            return 0
        return int(round(sum(i["views"] for i in items) / len(items)))
    return None


def _save(memo: dict[str, int | None]) -> None:
    """Merge with whatever another build process already wrote, then dump."""
    disk = read_json(PV_PATH, {}) or {}
    disk.update(memo)
    PV_PATH.write_text(json.dumps(disk, ensure_ascii=False), encoding="utf-8")


def crawl_pageviews(articles: list[str], workers: int = 4) -> dict[str, int | None]:
    """Mean monthly views (last 60 days x 30) per pt.wikipedia article.

    Uses the action API (prop=pageviews), 50 titles per request: ~300 polite
    requests for the whole acervo instead of one REST call per article, which
    Wikimedia's edge rate-limits. Cached on disk by the HTTP layer.
    """
    from .http import chunks, wp_api
    memo: dict[str, int | None] = {}
    todo = [a for a in dict.fromkeys(articles) if a]
    print(f"[pageviews] {len(todo)} articles, {len(todo) // 50 + 1} batched requests")
    for i, batch in enumerate(chunks(todo, 50)):
        params = {"titles": "|".join(batch), "prop": "pageviews", "pvipdays": "60"}
        seen: dict[str, dict] = {}
        for _ in range(5):
            data = wp_api(**params)
            for page in data.get("query", {}).get("pages", []):
                views = page.get("pageviews") or {}
                seen.setdefault(page["title"], {}).update(views)
            cont = data.get("continue")
            if not cont:
                break
            params = {**params, **cont}
        normalized = {n["from"]: n["to"] for n in data.get("query", {}).get("normalized", [])}
        for title in batch:
            views = seen.get(normalized.get(title, title))
            if views is None:
                memo[title] = None
                continue
            days = [v for v in views.values() if v is not None]
            memo[title] = int(round(sum(days) / max(len(views), 1) * 30)) if views else 0
        if i % 50 == 0:
            print(f"  {i * 50}/{len(todo)}")
    _save(memo)
    return memo


def zipf(name: str) -> float:
    # Imported lazily: wordfreq lives only in the dataset build env (.venv-data).
    zipf_frequency = import_module("wordfreq").zipf_frequency
    best = 0.0
    for candidate in {name, name.replace("-", " ")}:
        best = max(best, zipf_frequency(candidate, "pt"))
    return round(best, 3)


def zipf_map(names: list[str]) -> dict[str, float]:
    return {n: zipf(n) for n in names}


def _ranks(values: list[float]) -> list[float]:
    """Midrank percentile in [0,1]; ties share the average rank."""
    n = len(values)
    if n <= 1:
        return [0.5] * n
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2
        for k in range(i, j + 1):
            ranks[order[k]] = avg / (n - 1)
        i = j + 1
    return ranks


def composite(answers: list[dict]) -> list[dict]:
    """Add `rarity` (percentile), `share` (estimated answer share) and `points`.

    Each answer needs raw {pv, sl, wf, gravity}. Missing metrics are dropped for
    that answer and the remaining weights renormalised.
    """

    def metric(a: dict) -> dict[str, float]:
        out = {}
        if a.get("pv") is not None:
            out["pv"] = math.log10(1 + a["pv"])
        if a.get("sl"):
            out["sl"] = math.log10(1 + a["sl"])
        if a.get("wf"):
            out["wf"] = a["wf"]
        gravity = a.get("g", a.get("gravity"))
        if gravity:
            out["gravity"] = math.log10(1 + gravity)
        return out

    rows = [metric(a) for a in answers]
    pct: dict[str, list[float]] = {}
    for key in ("pv", "sl", "wf", "gravity"):
        vals = [r.get(key) for r in rows]
        present = [(i, v) for i, v in enumerate(vals) if v is not None]
        col = [0.0] * len(rows)
        if present:
            ranks = _ranks([v for _, v in present])
            for (i, _), rk in zip(present, ranks, strict=True):
                col[i] = rk
        pct[key] = col

    comp = []
    for idx, row in enumerate(rows):
        num = den = 0.0
        for key, weight in WEIGHTS.items():
            if key in row:
                num += weight * pct[key][idx]
                den += weight
        comp.append(num / den if den else 0.5)

    # Estimated answer share: softmax over a weighted z-score of the same signals.
    zs = []
    for key in ("pv", "sl", "wf", "gravity"):
        vals = [r[key] for r in rows if key in r]
        if len(vals) < 2:
            zs.append([0.0] * len(rows))
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        sd = math.sqrt(var) or 1.0
        zs.append([(r[key] - mean) / sd if key in r else 0.0 for r in rows])
    score = []
    for idx in range(len(rows)):
        s = 0.0
        for key, z in zip(("pv", "sl", "wf", "gravity"), zs, strict=True):
            if key in rows[idx]:
                s += WEIGHTS[key] * z[idx]
        score.append(s)
    mx = max(score) if score else 0.0
    exps = [math.exp(s - mx) for s in score]
    total = sum(exps) or 1.0
    shares = [e / total for e in exps]

    for i, answer in enumerate(answers):
        answer["popPercentile"] = round(comp[i], 4)
        answer["rarity"] = round(1 - comp[i], 4)
        answer["share"] = round(shares[i], 5)
        answer["oneIn"] = max(2, int(round(1 / shares[i]))) if shares[i] > 0 else None
        answer["points"] = round(1 + 9 * (answer["rarity"] ** 1.15))
    return answers


def uniform_rarity(
    answers: list[dict], order_key: str = "popPercentile", descending: bool = True
) -> list[dict]:
    """Replace the composite percentile by a flat one over the measured order.

    `composite` is a weighted mean of four percentile ranks, so its own
    distribution is bell-shaped: the middle is crowded (40% of the acervo sat in
    one 0.20 band) and the tails are nearly empty. That broke the top of the game —
    on a 27-item pool the rarest answer stops near 0.94, so the last band was
    unreachable, while a 1,800-item pool put a dozen answers in it. Same rarity,
    wildly different meaning.

    The game only consumes the *order*, so the order is what gets a percentile:
    index / (n - 1). Every pool then offers the same six bands, the last answer of
    any pool is a real 1.0, and the meter ladder means the same thing everywhere.
    """
    ordered = sorted(answers, key=lambda a: a[order_key], reverse=descending)
    n = len(ordered)
    for i, answer in enumerate(ordered):
        rarity = 0.0 if n <= 1 else i / (n - 1)
        answer["popPercentile"] = round(1 - rarity, 4)
        answer["rarity"] = round(rarity, 4)
        answer["points"] = round(1 + 9 * (rarity ** 1.15))
    return answers
