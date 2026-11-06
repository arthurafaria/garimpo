import { useEffect, useRef } from "react";
import { PixelSprite } from "../art/PixelSprite.tsx";
import { MINERALS, TOOLS } from "../art/sprites.ts";
import { Counter } from "../components/Counter.tsx";
import { TIERS, styleScale, tierForRarity, type Tier } from "../game/score.ts";
import type { Answer, Prompt, Round as RoundResult } from "../game/types.ts";

type Props = {
  prompt: Prompt;
  round: RoundResult;
  depthBefore: number;
  depthAfter: number;
  onNext: () => void;
  isLast: boolean;
  /** The find already burst out in the shaft: the panel settles instead of popping again. */
  landed?: boolean;
};

/** Reads the measured rarity defensively: the field is what the build writes. */
function rarityOf(answer: Answer | null | undefined): number {
  if (!answer || !("rarity" in answer)) return 0;
  return Number(answer.rarity);
}

function formatViews(views: number | null): string {
  if (views === null) return "sem artigo";
  if (views <= 0) return "0/mês";
  if (views >= 1_000_000)
    return `${(views / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} M/mês`;
  if (views >= 1000)
    return `${(views / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil/mês`;
  return `${views.toLocaleString("pt-BR")}/mês`;
}

/** Sparkle count per tier: none for coal, iron and copper, growing from gold to diamond. */
const SPARKLES: Record<number, number> = { 4: 5, 5: 9, 6: 16 };

/** Deterministic sparkle positions around the mineral (percent of the art box). */
function sparkles(count: number) {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2 + (i % 2 ? 0.4 : 0);
    const radius = 38 + ((i * 37) % 17);
    return {
      x: 50 + Math.cos(angle) * radius,
      y: 50 + Math.sin(angle) * radius,
      delay: (i * 173) % 900,
      big: i % 3 === 0,
    };
  });
}

/** "Você encontrou …": the big line under each answer, with the mineral it turned up. */
function Find({ tier, meters, landed }: { tier: Tier | null; meters: number; landed: boolean }) {
  if (!tier) {
    return (
      <div className="find" data-tier="0">
        <p className="find-line">Nada encontrado</p>
        <p className="find-meta">o poço não desceu nesta pergunta</p>
      </div>
    );
  }
  const count = SPARKLES[tier.id] ?? 0;
  const exclaim = tier.id >= 4 ? "!" : "";
  return (
    <div className="find" data-tier={tier.id} data-landed={landed}>
      <span className="find-art" aria-hidden="true">
        <PixelSprite sprite={MINERALS[tier.find].sprite} scale={4} />
        {sparkles(count).map((spark, i) => (
          <i
            key={i}
            data-big={spark.big}
            style={{
              left: `${spark.x}%`,
              top: `${spark.y}%`,
              animationDelay: `${spark.delay}ms`,
            }}
          />
        ))}
      </span>
      <div>
        <p className="find-line">
          Você encontrou <b>{tier.findName + exclaim}</b>
        </p>
        <p className="find-meta">
          +{meters} m com {tier.tool === "aspirador" ? "o" : "a"} {tier.toolName.toLowerCase()}
        </p>
      </div>
    </div>
  );
}

function normalizer(prompt: Prompt, pick: (answer: Answer) => number) {
  const values = prompt.answers.map(pick);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (answer: Answer) => {
    if (max === min) return 0.5;
    return Math.min(1, Math.max(0.04, (pick(answer) - min) / (max - min)));
  };
}

export function Reveal({
  prompt,
  round,
  depthBefore,
  depthAfter,
  onNext,
  isLast,
  landed = false,
}: Props) {
  const matched = round.matched;
  const matchedRarity = rarityOf(matched);
  const tier = tierForRarity(matchedRarity);
  const nextButton = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    nextButton.current?.focus({ preventScroll: true });
  }, []);
  const popularityBars = normalizer(prompt, (answer) => Math.log10(1 + (answer.pv ?? 0)));
  const sitelinkBars = normalizer(prompt, (answer) => Math.log10(1 + answer.sl));
  const corpusBars = normalizer(prompt, (answer) => answer.wf);

  const signals = matched
    ? [
        { name: "atenção", value: formatViews(matched.pv), width: popularityBars(matched) },
        {
          name: "sitelinks",
          value: `${matched.sl} ${matched.sl === 1 ? "wiki" : "wikis"}`,
          width: sitelinkBars(matched),
        },
        { name: "corpus", value: `${matched.wf.toFixed(1)} zipf`, width: corpusBars(matched) },
      ]
    : [];

  return (
    <div className="round reveal panel">
      {matched ? (
        <div className="sheet">
          <p className="who">{round.timedOut ? "o tempo acabou" : "você"}</p>
          <p className="answer">{round.guess || "—"}</p>
          <p className="canonical">
            {matched.n !== round.guess ? `no acervo: ${matched.n}` : "no acervo"}
          </p>

          <Find tier={tier} meters={round.meters} landed={landed} />

          <hr />

          <div className="tier">
            <PixelSprite sprite={TOOLS[tier.tool].frames[0]} scale={2} title={tier.toolName} />
            <div>
              <h2>{tier.label}</h2>
              <p className="tier-layer">
                {tier.toolName} · faixa {tier.id} de {TIERS.length} · {tier.meters} m
              </p>
            </div>
            <div
              className="pval"
              title="p é o posto de raridade no acervo; a linha de baixo estima quantos jogadores dariam essa resposta."
            >
              <b>p {Math.round(matchedRarity * 100)}</b>
              <em>posto no acervo</em>
              <span>≈ {styleScale(matched.oneIn)}</span>
            </div>
          </div>

          <div className="signals" aria-label="sinais medidos">
            {signals.map((signal) => (
              <div className="signal" key={signal.name}>
                <em>{signal.name}</em>
                <span className="bar">
                  <i style={{ width: `${Math.round(signal.width * 100)}%` }} />
                </span>
                <span>{signal.value}</span>
              </div>
            ))}
          </div>

          <div className="tier-caps" aria-hidden="true">
            {TIERS.map((item) => (
              <i key={item.id} data-on={item.id <= tier.id} />
            ))}
          </div>
        </div>
      ) : (
        <div className="sheet">
          <p className="who">{round.timedOut ? "o tempo acabou" : "você"}</p>
          <p className="answer">{round.guess || "—"}</p>
          <p className="canonical">
            {round.timedOut ? "sem resposta" : "não está no acervo desta pergunta"}
          </p>
          <Find tier={null} meters={0} landed={false} />
          <hr />
          <p className="compare" style={{ marginTop: 0 }}>
            {round.timedOut ? (
              <>
                O tempo acabou antes da sua resposta. Sem uma resposta do acervo, não há raridade
                para medir.
              </>
            ) : (
              <>
                O acervo cobre <b>{prompt.answers.length}</b> respostas possíveis. A sua ficou fora
                dele, então não dá para medir a raridade — e o jogo não inventa um número.
              </>
            )}
          </p>
        </div>
      )}

      <div className="reveal-foot">
        <div>
          <p className="label" style={{ color: "var(--iron)" }}>
            profundidade
          </p>
          <p
            className="display reveal-depth"
            style={{ fontSize: "var(--fs-h1)", color: "var(--lamp)" }}
          >
            {depthAfter !== depthBefore ? (
              <>
                <Counter value={depthBefore} />
                <span
                  className="mono"
                  style={{ fontSize: 24, color: "var(--ink-2)", margin: "0 6px" }}
                >
                  →
                </span>
              </>
            ) : null}
            <Counter key={depthAfter} value={depthAfter} />
            <span style={{ fontSize: 24 }}> m</span>
          </p>
        </div>
        <button
          ref={nextButton}
          type="button"
          className="btn"
          onClick={onNext}
          style={{ width: 240 }}
        >
          {isLast ? "Ver o poço" : "Próxima"}
          <span className="btn-meta">{isLast ? "resultado" : "enter"}</span>
        </button>
      </div>
    </div>
  );
}
