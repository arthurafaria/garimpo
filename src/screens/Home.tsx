import { PixelSprite } from "../art/PixelSprite.tsx";
import { LOGO, MINERALS, TOOLS } from "../art/sprites.ts";
import type { Dataset } from "../game/types.ts";
import { prettyDate, todayKey } from "../game/rng.ts";
import { MAX_DEPTH, TIERS } from "../game/score.ts";
import type { Store } from "../game/storage.ts";

type Props = {
  dataset: Dataset;
  store: Store;
  onDaily: () => void;
  onUnlimited: () => void;
  onLog: () => void;
  onMethod: () => void;
};

const STEPS = [
  {
    n: "1",
    title: "Responda rápido",
    body: "Sete perguntas sobre o Brasil e o mundo. Cada uma tem 25 segundos e aceita muitas respostas certas.",
  },
  {
    n: "2",
    title: "A raridade é medida",
    body: "Acessos na Wikipédia, em quantas línguas o verbete existe e a frequência no português dizem o quão óbvia ela é.",
  },
  {
    n: "3",
    title: "Quanto mais rara, mais fundo",
    body: `Cada raridade tem uma ferramenta e uma profundidade fixa: a resposta óbvia cava ${TIERS[0].meters}\u00a0m com a pá, a mais rara explode ${TIERS[TIERS.length - 1].meters}\u00a0m com dinamite. Sete respostas perfeitas chegam a ${MAX_DEPTH}\u00a0m.`,
  },
];

export function Home({ dataset, store, onDaily, onUnlimited, onLog, onMethod }: Props) {
  const today = todayKey();
  const done = store.dailyDone[today];
  const record = store.dives.reduce((best, dive) => Math.max(best, dive.depth), 0);
  const streak = store.streak.count;

  return (
    <div className="home">
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-logo">
          <PixelSprite sprite={LOGO} scale={4} title="Capacete de mineiro com pá" />
        </div>
        <h1 id="hero-title" className="hero-title">
          Garimpo
        </h1>
        <p className="hero-sub">Sete respostas. Uma mina.</p>
        <p className="hero-lede">
          Quanto mais rara a sua resposta, maior a máquina e mais fundo o poço. E a raridade é{" "}
          <strong>medida em dados</strong>, não em opinião.
        </p>

        <div className="hero-cta">
          <button type="button" className="btn btn-big" onClick={onDaily}>
            {done ? "Descer de novo" : "Descer"}
            <span className="btn-meta">{done ? `hoje: ${done.depth} m` : "poço do dia"}</span>
          </button>
          <button type="button" className="btn btn-ghost btn-tall" onClick={onUnlimited}>
            Ilimitado
          </button>
        </div>

        <ul className="hero-stats" aria-label="seus números">
          <li>
            <b>{record ? `${record} m` : "—"}</b>
            <span>recorde</span>
          </li>
          <li>
            <b>{streak > 0 ? streak : "—"}</b>
            <span>{streak === 1 ? "dia seguido" : "dias seguidos"}</span>
          </li>
          <li>
            <b>{store.dives.length}</b>
            <span>{store.dives.length === 1 ? "poço aberto" : "poços abertos"}</span>
          </li>
        </ul>
      </section>

      <section className="panel howto" aria-labelledby="howto-title">
        <h2 id="howto-title" className="section-title">
          Como funciona
        </h2>
        <ol className="howto-steps">
          {STEPS.map((step) => (
            <li key={step.n}>
              <span className="howto-n">{step.n}</span>
              <div>
                <b>{step.title}</b>
                <p>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="howto-kicker">Cada raridade, uma ferramenta, uma distância fixa</p>
        <ol className="tool-row" aria-label="Ferramentas, da resposta mais óbvia à mais rara">
          {TIERS.map((tier) => (
            <li key={tier.id} data-tier={tier.id}>
              <span className="tool-art">
                <PixelSprite sprite={TOOLS[tier.tool].frames[0]} scale={2} />
              </span>
              <b>{tier.toolName}</b>
              <span className="tool-label">{tier.label}</span>
              <span className="tool-m">{tier.meters} m</span>
              <span className="tool-find">
                <PixelSprite sprite={MINERALS[tier.find].sprite} scale={1} /> {tier.findName}
              </span>
            </li>
          ))}
        </ol>
        <p className="tool-rule">
          Sem curva, sem sorteio: cada resposta cava exatamente os metros da sua faixa. Teto:{" "}
          {MAX_DEPTH} m.
        </p>
      </section>

      <section className="entry-grid" aria-label="modos de jogo">
        <button type="button" className="panel entry" onClick={onDaily}>
          <span className="entry-kicker">diário · {prettyDate(today)}</span>
          <b>O poço do dia</b>
          <span>As mesmas sete perguntas para todo mundo, até a meia-noite.</span>
          <span className="entry-go">{done ? `você desceu ${done.depth} m` : "descer →"}</span>
        </button>
        <button type="button" className="panel entry" onClick={onUnlimited}>
          <span className="entry-kicker">ilimitado</span>
          <b>Semente sorteada</b>
          <span>
            Fora do poço do dia, com um número de 1 a 9999. Qual é a mina você só descobre no fim.
          </span>
          <span className="entry-go">descer →</span>
        </button>
        <button type="button" className="panel entry" onClick={onLog}>
          <span className="entry-kicker">arquivo</span>
          <b>Seus poços</b>
          <span>Cada descida fica guardada com a profundidade e as sete respostas.</span>
          <span className="entry-go">
            {store.dives.length ? `${store.dives.length} no arquivo →` : "ainda vazio"}
          </span>
        </button>
        <button type="button" className="panel entry" onClick={onMethod}>
          <span className="entry-kicker">como medimos</span>
          <b>A régua</b>
          <span>
            {dataset.stats.prompts} perguntas e{" "}
            {dataset.stats.uniqueAnswers.toLocaleString("pt-BR")} respostas medidas com dados
            públicos.
          </span>
          <span className="entry-go">ver a conta →</span>
        </button>
      </section>

      <p className="home-foot">pt.wikipedia · wikidata · wordfreq · régua de 0 a 700 m</p>
    </div>
  );
}
