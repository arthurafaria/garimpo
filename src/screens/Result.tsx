import { useEffect, useRef, useState } from "react";
import { PixelSprite } from "../art/PixelSprite.tsx";
import { MINERALS } from "../art/sprites.ts";
import { seedFromLabel } from "../game/rng.ts";
import { TIERS, dig, tierForDepth, tierForRarity } from "../game/score.ts";
import { STRATA, stratumForDepth } from "../game/strata.ts";
import type { Answer, Dataset, Dive } from "../game/types.ts";

type Props = {
  dive: Dive;
  dataset: Dataset;
  onHome: () => void;
  onAgain: () => void;
  onLog: () => void;
  onMethod: () => void;
};

const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1);

type Mark = Dive["rounds"][number] & { at: number };

function poolFor(dataset: Dataset, id: string, text: string): Answer[] {
  return (
    dataset.prompts.find((prompt) => prompt.id === id)?.answers ??
    dataset.prompts.find((prompt) => prompt.text === text)?.answers ??
    []
  );
}

/** The rank-1 answer of a prompt: what "the obvious one" would have dug. */
function obviousFor(dataset: Dataset, id: string, text: string): Answer | null {
  return poolFor(dataset, id, text).find((answer) => answer.rank === 1) ?? null;
}

function withDepths(dive: Dive): Mark[] {
  let cumulative = 0;
  return dive.rounds.map((round) => {
    cumulative += round.meters;
    return { ...round, at: Math.min(700, cumulative) };
  });
}

function ResultPlate({ dive, marks }: { dive: Dive; marks: Mark[] }) {
  const reached = Math.min(700, dive.depth);

  return (
    <div className="result-plate" aria-hidden="true">
      {STRATA.map((stratum) => {
        const top = (stratum.from / 700) * 100;
        const height = ((stratum.to - stratum.from) / 700) * 100;
        return (
          <div
            key={stratum.id}
            className="stratum"
            style={{
              top: `${top}%`,
              height: `${height}%`,
              ["--fill" as string]: stratum.fill,
              ["--hatch" as string]: stratum.hatch,
              opacity: stratum.from >= reached ? 0.45 : 1,
            }}
          />
        );
      })}

      <div className="shaft">
        <div className="shaft-fill" style={{ height: `${(reached / 700) * 100}%` }} />
        {marks.map((mark, index) => (
          <div key={mark.promptId} className="mark" style={{ top: `${(mark.at / 700) * 100}%` }}>
            <i />
            <b>{index + 1}</b>
          </div>
        ))}
      </div>

      <div className="depth-col">
        {[0, 100, 200, 300, 400, 500, 600, 700].map((metres) => (
          <b key={metres} style={{ top: `${(metres / 700) * 100}%` }}>
            {metres === 700 ? "700 m" : metres}
          </b>
        ))}
      </div>

      <div className="strata-names">
        {STRATA.map((stratum) => {
          const middle = ((stratum.from + stratum.to) / 2 / 700) * 100;
          const thin = ((stratum.to - stratum.from) / 700) * 100 < 6;
          if (thin) return null;
          const top = Math.min(94, Math.max(6, middle));
          return (
            <div key={stratum.id} style={{ top: `${top}%` }}>
              <b>{stratum.label}</b>
              {stratum.fact}
            </div>
          );
        })}
      </div>

      <div className="floor" />
    </div>
  );
}

export function Result({ dive, dataset, onHome, onAgain, onLog, onMethod }: Props) {
  const [copied, setCopied] = useState(false);
  const heading = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, []);
  const marks = withDepths(dive);
  const tier = tierForDepth(dive.depth);
  // A gem is what the shaft is cutting through at that depth, not a separate scale.
  const gems = marks.filter((mark) => stratumForDepth(Math.min(699, mark.at)).from >= 440).length;
  // What each answer turned up (the tier's mineral), counted for the summary.
  const finds = TIERS.map((item) => ({
    item,
    count: marks.filter(
      (mark) => mark.name && mark.p !== null && tierForRarity(mark.p).id === item.id,
    ).length,
  })).filter((entry) => entry.count > 0);
  const stratum = stratumForDepth(dive.depth);
  const obvious = marks.map((mark) => obviousFor(dataset, mark.promptId, mark.prompt));
  const obviousTotal = Math.min(
    700,
    obvious.reduce((sum, answer) => sum + (answer ? dig(answer.rarity) : 0), 0),
  );
  const gain = dive.depth - obviousTotal;
  // Unlimited mode never told the player which mine it dealt: this is the reveal.
  const seed = dive.mode === "unlimited" ? seedFromLabel(dive.label) : null;
  const shareLink =
    seed !== null ? `${window.location.origin}${window.location.pathname}#s=${seed}` : null;

  const share = async () => {
    const text = [
      `Garimpo · ${dive.label} · ${dive.depth} m`,
      ...dive.rounds.map(
        (round, index) =>
          `${index + 1}. ${round.prompt} — ${round.name ?? (round.guess || "—")} (${round.meters} m)`,
      ),
      shareLink ? `mesma mina: ${shareLink}` : null,
      "sete respostas, uma mina.",
    ]
      .filter(Boolean)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="result">
      <div className="result-body">
        <div className="panel result-main">
          <h1 ref={heading} tabIndex={-1} className="result-headline display">
            <small>
              {dive.mode === "daily" ? "diário" : "ilimitado"} · {dive.label}
            </small>
            {dive.depth >= 700 ? "Fundo do poço." : `${dive.depth} metros.`}
          </h1>
          <div
            className="tier-ticks"
            role="img"
            aria-label={`${stratum.label}, nível ${tier.id} de ${TIERS.length}`}
          >
            {TIERS.map((item) => (
              <i key={item.id} data-on={item.id <= tier.id} />
            ))}
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)", marginLeft: 6 }}>
              <PixelSprite sprite={MINERALS[stratum.id].sprite} scale={1} /> {stratum.label}
            </span>
          </div>

          <p style={{ color: "var(--ink-2)", marginTop: 18, maxWidth: "46ch" }}>
            {gems > 0
              ? `${gems} ${gems === 1 ? "camada nobre" : "camadas nobres"} no caminho. Você parou na camada de ${lower(stratum.label)}: ${stratum.fact}.`
              : `Nenhuma camada nobre no caminho. Você parou na camada de ${lower(stratum.label)}: ${stratum.fact}. As respostas óbvias descem pouco.`}
          </p>

          {seed !== null ? (
            <p className="result-seed">
              <span className="label">a semente era</span>
              <b>#{seed}</b>
              <span>
                mesma mina para quem você mandar esse número — #{seed} abre estas sete perguntas.
              </span>
            </p>
          ) : null}

          {finds.length ? (
            <ul className="result-finds" aria-label="o que você encontrou">
              {finds.map(({ item, count }) => (
                <li key={item.id} data-tier={item.id}>
                  <PixelSprite sprite={MINERALS[item.find].sprite} scale={2} />
                  <b>{count}×</b> {MINERALS[item.find].name.toLowerCase()}
                </li>
              ))}
            </ul>
          ) : null}

          <div className="result-actions">
            <button type="button" className="btn" onClick={onAgain}>
              Descer de novo
              <span className="btn-meta">
                {dive.mode === "unlimited" && seed !== null
                  ? `semente #${seed}`
                  : "mesmas perguntas"}
              </span>
            </button>
            <button type="button" className="btn btn-ghost" onClick={onLog}>
              Arquivo
            </button>
            <button type="button" className="btn btn-ghost" onClick={share}>
              {copied ? "Copiado" : "Copiar"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onMethod}>
              Como medimos
            </button>
            <button type="button" className="btn btn-ghost" onClick={onHome}>
              Início
            </button>
          </div>

          <p className="plate-title">o poço inteiro</p>
          <ResultPlate dive={dive} marks={marks} />
        </div>

        <i className="result-window" aria-hidden="true" />
        <div className="panel result-ledger">
          <p className="vs-summary">
            Só com as respostas mais óbvias, o poço teria <b>{obviousTotal} m</b>.{" "}
            {gain > 0
              ? `Você cavou ${gain} m a mais.`
              : gain < 0
                ? `Você ficou ${-gain} m acima disso.`
                : "Você empatou com o óbvio."}
          </p>
          <ol className="rounds">
            {marks.map((round, index) => {
              const base = obvious[index];
              const baseM = base ? dig(base.rarity) : null;
              const same = base && round.name === base.n;
              return (
                <li key={round.promptId} data-miss={!round.name}>
                  <span className="idx">{String(index + 1).padStart(2, "0")}</span>
                  <span className="said">
                    <span className="said-q">{round.prompt}</span>
                    <b>{round.name ?? (round.guess || "em branco")}</b>
                    {round.p !== null ? (
                      <span className="said-p">p {Math.round(round.p * 100)}</span>
                    ) : null}
                    {base ? (
                      <span className="vs">
                        {same ? (
                          "era a mais óbvia"
                        ) : (
                          <>
                            mais óbvia: <b>{base.n}</b> · {baseM} m
                          </>
                        )}
                      </span>
                    ) : null}
                  </span>
                  <span className="meters">
                    {round.meters} m{" "}
                    {round.name && round.p !== null ? (
                      <PixelSprite
                        sprite={MINERALS[tierForRarity(round.p).find].sprite}
                        scale={1}
                        title={tierForRarity(round.p).findName}
                      />
                    ) : null}
                    {baseM !== null && !same ? (
                      <small data-up={round.meters > baseM}>
                        {round.meters - baseM > 0 ? "+" : ""}
                        {round.meters - baseM} m
                      </small>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      <section className="overview" aria-label="o acervo de cada pergunta">
        <div className="overview-head">
          <h2>o acervo de cada pergunta</h2>
          <p>
            Todas as respostas aceitas de cada pergunta, da que mais desce para a mais óbvia. O que
            você respondeu aparece marcado.
          </p>
        </div>

        <div className="overview-grid">
          {marks.map((mark, index) => {
            const pool = poolFor(dataset, mark.promptId, mark.prompt);
            const rarest = [...pool].sort((a, b) => b.rarity - a.rarity).slice(0, 8);
            const obvious = pool.find((answer) => answer.rank === 1);
            const position = mark.rank ? mark.count - mark.rank + 1 : null;
            return (
              <details key={mark.promptId} className="ov" data-miss={!mark.name}>
                <summary>
                  <span className="ov-idx">{String(index + 1).padStart(2, "0")}</span>
                  <span className="ov-prompt">{mark.prompt}</span>
                  <span className="ov-you">
                    {mark.name ?? (mark.guess ? "fora do acervo" : "sem resposta")}
                  </span>
                  <span className="ov-meta">
                    {mark.meters} m · {mark.count} respostas
                  </span>
                </summary>
                <div className="ov-body">
                  <p className="ov-line">
                    <span>sua posição</span>
                    <b>
                      {position
                        ? `${position}º mais rara de ${mark.count}`
                        : mark.name
                          ? "sem posição"
                          : "não medida"}
                    </b>
                  </p>
                  <p className="ov-sub">as que mais descem</p>
                  <ul>
                    {rarest.map((answer) => (
                      <li key={answer.n} data-you={answer.n === mark.name}>
                        <span>{answer.n}</span>
                        <span className="mono">{dig(answer.rarity)} m</span>
                      </li>
                    ))}
                  </ul>
                  {obvious ? (
                    <p className="ov-line ov-obvious">
                      <span>a mais óbvia</span>
                      <b>
                        {obvious.n} · {dig(obvious.rarity)} m
                      </b>
                    </p>
                  ) : null}
                </div>
              </details>
            );
          })}
        </div>
      </section>
    </div>
  );
}
