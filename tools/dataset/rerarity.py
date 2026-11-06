"""Re-derive `rarity` in the shipped acervo from the measured order.

    PYTHONPATH=tools .venv-data/bin/python -m dataset.rerarity [--check]

The build now writes a flat within-prompt percentile (`measure.uniform_rarity`)
instead of the bell-shaped composite one, which left the last band unreachable on
small pools. This patches public/data/garimpo.json in place and offline: the
measurements are untouched, only the percentile laid on top of the order moves, so
the shipped acervo does not need to crawl Wikipedia again.

Writes compact JSON like build.py; run `vp check --fix` afterwards to put the file
back in the formatted style the repo commits.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from .measure import uniform_rarity

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public" / "data" / "garimpo.json"

DEFINITION = (
    "percentile of the answer inside its prompt's measured order "
    "(order = 1 - weighted mean of within-prompt percentile ranks of pageviews, "
    "sitelinks, wordfreq and gravity; documented manual clamps in "
    "tools/dataset/curated/overrides.json)"
)

# Mirrors src/game/score.ts TIERS: the lower rarity edge of each band, in metres.
BANDS = [(0.0, 25), (0.10, 40), (0.30, 55), (0.50, 70), (0.70, 85), (0.90, 100)]


def band(rarity: float) -> int:
    metres = BANDS[0][1]
    for edge, value in BANDS:
        if rarity >= edge:
            metres = value
    return metres


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    try:
        payload = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as cause:
        print(f"nao consegui ler {OUT}: {cause}", file=sys.stderr)
        return 1
    prompts = payload["prompts"]

    for prompt in prompts:
        uniform_rarity(prompt["answers"], order_key="rank", descending=False)

    # Verification: the order the game reads must match the order the build measured.
    for prompt in prompts:
        by_rank = sorted(prompt["answers"], key=lambda a: a["rank"])
        rarities = [a["rarity"] for a in by_rank]
        if rarities != sorted(rarities):
            raise SystemExit(f"raridade fora de ordem em {prompt['id']}")
        if abs(rarities[0]) > 1e-9 or abs(rarities[-1] - 1.0) > 1e-9:
            raise SystemExit(f"faixa incompleta em {prompt['id']}: {rarities[0]}..{rarities[-1]}")

    counts = Counter(band(a["rarity"]) for p in prompts for a in p["answers"])
    total = sum(counts.values())
    print(f"respostas: {total}")
    for _, metres in BANDS:
        share = 100 * counts[metres] / total
        print(f"  {metres:3d} m  {counts[metres]:6d}  {share:5.1f}%")
    deepest = [max(band(a["rarity"]) for a in p["answers"]) for p in prompts]
    print(f"perguntas que oferecem 100 m: {sum(1 for m in deepest if m == 100)}/{len(prompts)}")

    if check_only:
        print("--check: nada escrito")
        return 0

    payload["method"]["rarityDefinition"] = DEFINITION
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
