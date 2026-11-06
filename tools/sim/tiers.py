"""Calibrate the six tier cut points (src/game/score.ts TIERS.minRarity).

Player model: for each prompt the player names one catalogued answer, picked
with probability proportional to share**beta (share = the pipeline's softmax
popularity inside the prompt). beta > 1 means "goes for the famous one":

    casual  45 %  beta 1.6
    regular 40 %  beta 1.2
    expert  15 %  beta 0.8

Targets for the simulated typical player:
  * most answers (>= 70 %) dig 10-30 m (Óbvia, Comum, Boa);
  * about 1 in 7 (12-17 %) digs 60 m or more;
  * 100 m ("Lendária") is genuinely rare (<= 1.5 %);
  * the 3 most famous answers of every pool are always Óbvia.

    python3 tools/sim/tiers.py            (prints the grid winner and the table)
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "public" / "data" / "garimpo.json"
RNG = random.Random(20261105)  # noqa: S311 - simulation only
PLAYERS = [(0.45, 1.6), (0.40, 1.2), (0.15, 0.8)]
METERS = [10, 15, 30, 60, 85, 100]


def load_prompts() -> list[dict]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    out = []
    for p in data["prompts"]:
        answers = p.get("answers")
        if answers is None:
            answers = json.loads((DATA.parent / p["file"]).read_text(encoding="utf-8"))["answers"]
        out.append({"id": p["id"], "answers": answers})
    return out


def pick_distribution(prompts: list[dict]) -> list[tuple[float, float]]:
    """(rarity, weight) pairs: exact expectation, no sampling noise."""
    pairs: list[tuple[float, float]] = []
    for prompt in prompts:
        answers = prompt["answers"]
        for share_w, beta in PLAYERS:
            weights = [max(a.get("share") or 0.0, 1e-9) ** beta for a in answers]
            total = sum(weights)
            for a, w in zip(answers, weights):
                pairs.append((a["rarity"], share_w * w / total / len(prompts)))
    return pairs


def tier_of(rarity: float, cuts: list[float]) -> int:
    t = 0
    for i, c in enumerate(cuts):
        if rarity >= c:
            t = i
    return t


def make_cdf(pairs):
    import bisect
    pairs = sorted(pairs)
    xs = [r for r, _ in pairs]
    acc, run = [], 0.0
    for _, w in pairs:
        run += w
        acc.append(run)
    total = run

    def below(x: float) -> float:  # mass with rarity < x
        i = bisect.bisect_left(xs, x)
        return acc[i - 1] / total if i else 0.0
    return below


def evaluate(below, cuts) -> list[float]:
    edges = [*cuts[1:], 2.0]
    out, prev = [], 0.0
    for e in edges:
        v = below(e)
        out.append(v - prev)
        prev = v
    return out


def top_obvious_floor(prompts: list[dict], k: int = 3) -> float:
    """Comum cut must sit above the rarity of every pool's top-k answers."""
    worst = 0.0
    for p in prompts:
        ranked = sorted(p["answers"], key=lambda a: a["rarity"])[:k]
        worst = max(worst, max(a["rarity"] for a in ranked))
    return worst


def main() -> int:
    prompts = load_prompts()
    pairs = pick_distribution(prompts)
    below = make_cdf(pairs)
    floor = top_obvious_floor(prompts)
    best = None
    grid2 = [x / 100 for x in range(13, 50, 1)]
    grid3 = [x / 100 for x in range(30, 75, 1)]
    grid4 = [x / 100 for x in range(45, 90, 1)]
    grid5 = [x / 100 for x in range(70, 97, 1)]
    grid6 = [x / 1000 for x in range(950, 1000, 5)]
    for c2, c3, c4, c5, c6 in itertools.product(grid2, grid3, grid4, grid5, grid6):
        if not (floor < c2 < c3 < c4 < c5 < c6):
            continue
        cuts = [0.0, c2, c3, c4, c5, c6]
        m = evaluate(below, cuts)
        low = m[0] + m[1] + m[2]
        high = m[3] + m[4] + m[5]
        # loss: hit 1/7 at 60+, 100 m about 1 %, Óbvia the single biggest tier,
        # Comum and Boa both meaningful.
        loss = (abs(high - 1 / 7) * 4 + abs(m[5] - 0.01) * 6 + max(0, 0.70 - low) * 5
                + abs(m[0] - 0.40) + abs(m[1] - 0.25) * 0.8 + abs(m[2] - 0.20) * 0.8
                + abs(m[4] - 0.035) * 2)
        if best is None or loss < best[0]:
            best = (loss, cuts, m)
    assert best
    _, cuts, m = best
    print(f"top-3 floor (max rarity of any pool's 3 most famous): {floor:.3f}")
    print("cuts:", ", ".join(f"{c:.3f}" for c in cuts))
    print("| tier | metros | minRarity | % das respostas do jogador típico |")
    print("|---|---|---|---|")
    labels = ["Óbvia", "Comum", "Boa", "Rara", "Raríssima", "Lendária"]
    for label, meters, cut, share in zip(labels, METERS, cuts, m):
        print(f"| {label} | {meters} | {cut:.3f} | {share * 100:.1f} % |")
    print(f"10-30 m: {sum(m[:3]) * 100:.1f} %  ·  60 m+: {sum(m[3:]) * 100:.1f} % "
          f"(1 em {1 / max(sum(m[3:]), 1e-9):.1f})  ·  100 m: {m[5] * 100:.2f} %")
    mean = sum(w * METERS[i] for i, w in enumerate(m))
    print(f"mean metres per answer: {mean:.1f} (7 answers ≈ {mean * 7:.0f} m)")
    (ROOT / "tools" / "sim" / "tiers.json").write_text(
        json.dumps({"cuts": cuts, "mass": m, "top3Floor": floor}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
