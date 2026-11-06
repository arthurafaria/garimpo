# Garimpo

Sete perguntas sobre o Brasil, 25 segundos para cada uma, e um poço de 700 metros.
Quanto mais rara a resposta, mais fundo ela cava — e a raridade é **medida em dados**,
não estimada por opinião.

O jogo roda no navegador, sem back-end. O acervo é um arquivo JSON gerado por um
pipeline em Python a partir de fontes públicas.

## Como jogar

```bash
pnpm install
pnpm dev
```

- **Diário** — sete perguntas determinísticas pelo dia (mesmo dia, mesma mina).
- **Ilimitado** — um número de 1 a 9999 escolhe a mina; o mesmo número sempre traz
  as mesmas perguntas. Também dá para abrir direto por `#s=8842`.
- **Arquivo** — as descidas ficam no `localStorage`, com uma miniatura da placa.
- **Como medimos** — a conta inteira, as fontes e a validação.

Digite, Enter para cravar. Se a resposta não estiver no acervo, a rodada **não** termina:
o jogo avisa, limpa o campo e você tenta de novo com o relógio correndo. Se for só
erro de digitação ou apelido, ele mostra `“TV lobo” → TV Globo` e espera o segundo
envio para confirmar. No fim, a placa mostra onde cada resposta parou.

### Na rede local

O servidor de desenvolvimento sobe em `0.0.0.0:5173` (configurado em `vite.config.ts`),
então dá para jogar do celular ou de outra máquina na mesma rede:

```bash
pnpm dev
# Local:    http://localhost:5173/
# Rede:     http://<ip-da-máquina>:5173/   (ex.: http://192.168.1.5:5173/)
```

O IP aparece no próprio terminal ao subir o servidor. Para o build de produção:
`pnpm build && pnpm preview` (também em `0.0.0.0:4173`).

O servidor é de desenvolvimento, sem autenticação: quem estiver na mesma rede
acessa o projeto. Para fechar, encerre o processo na porta 5173.

## Como a raridade é medida

Cada resposta do acervo carrega três medições públicas, coletadas uma vez e
congeladas no JSON:

| sinal       | o que mede                                                               | peso |
| ----------- | ------------------------------------------------------------------------ | ---- |
| `pageviews` | média de acessos mensais ao verbete da pt.wikipedia nos últimos 12 meses | 50%  |
| `sitelinks` | em quantas línguas existe um verbete (Wikidata)                          | 25%  |
| `corpus`    | frequência da palavra em português (wordfreq, zipf)                      | 20%  |
| `gravidade` | população, quando a resposta é um lugar (Wikidata)                       | 5%   |

Dentro do acervo de cada pergunta, cada sinal vira um posto percentual; a
raridade é `1 − média ponderada dos postos`. Depois a raridade escolhe uma de
seis faixas fixas (cortes em `src/game/score.ts`, calibrados por `tools/dataset`):

| Faixa     | Ferramenta  | Metros | Encontra    |
| --------- | ----------- | ------ | ----------- |
| Óbvia     | Pá          | 10     | carvão      |
| Comum     | Aspirador   | 15     | ferro       |
| Boa       | Escavadeira | 30     | cobre       |
| Rara      | Broca       | 60     | ouro        |
| Raríssima | Broca ultra | 85     | um rubi     |
| Lendária  | Dinamite    | 100    | um diamante |

`poço = min(700, soma das 7)`: o fundo de 700 m exige sete respostas na faixa
mais rara.

Uma resposta válida que não está no acervo é **recusada**, e a tela diz isso. O
jogo não inventa raridade para o que não mediu.

## O acervo

40 pools, 154 perguntas, ~8,2 mil respostas catalogadas (mínimo de 12 por pergunta,
mediana de 25 e até 728 numa única pergunta). Cada pool vem de uma fonte
autoritativa:

- **Wikidata (SPARQL)** — estados, capitais, municípios por população, presidentes,
  jogadores da Seleção, clubes, rios, parques nacionais, estádios. Traz o número de
  sitelinks junto.
- **Wikidata, internacional** — países (com continente), capitais do mundo, cidades
  mais populosas, elementos químicos, videogames, animes e bandas. As perguntas
  internacionais cobrem continente e letra inicial.
- **Curadoria verificada** — frutas nativas, pratos, doces, novelas, filmes,
  cantores, escritores, atores, marcas, aves, mamíferos, folclore, festas, danças,
  instrumentos, palavras de origem tupi, gírias, BBB, TV Globinho, desenhos, além
  de Pokémon, super-heróis, comida do mundo e marcas globais. Cada item foi
  resolvido contra a pt.wikipedia antes de entrar; o que não resolve, fica fora.
- **pt.wikipedia** — títulos canônicos usados na coleta de pageviews.

O que cada pool contém e a fonte de cada um está em
`tools/dataset/curated/*.json` (campo `source`) e no relatório
`reports/dataset.md`.

## Reconstruir o acervo

O pipeline vive em `tools/` e usa um venv próprio (não é dependência do app):

```bash
python3 -m venv .venv-data
.venv-data/bin/pip install wordfreq requests
PYTHONPATH=tools .venv-data/bin/python -m dataset.build
```

Isso reescreve `public/data/garimpo.json` e `reports/dataset.md`. As respostas da
rede ficam em `.cache/dataset/` (SPARQL, API da Wikipédia, pageviews), então rodar
de novo é barato.

Coleta: cliente identificado no `User-Agent`, ~5 requisições por segundo, cache em
disco. Nada de raspar sites de emissoras; a validação contra multidão usa uma
amostra pequena e espaçada (~1 req/s) da API pública do Krillion.

Validação da régua:

```bash
PYTHONPATH=tools .venv-data/bin/python tools/validate_krillion.py
```

Compara a nossa raridade com o percentil real de jogadores numa pergunta genérica
(ex.: “Name any Pokémon”). Resultado atual: **Spearman ρ = 0,61** com 45 respostas
— ver `reports/validation.md`.

## Estrutura

```
src/
  game/        dataset, matching tolerante, curva de pontos, rng, storage
  components/  placa geológica, gema, contador, boca da mina
  screens/     home, rodada, revelação, resultado, arquivo, método, semente
  audio/       áudio procedural (Web Audio, sem arquivos)
tools/
  dataset/     pipeline: pools, features, métricas, montagem do JSON
  sim/         calibração da curva e simulação de jogadores
  validate_krillion.py
reports/       direção de arte, loop, dataset, validação, QA
```

## Limitações honestas

- A raridade é uma **estimativa relativa ao acervo**: uma resposta rara numa
  pergunta de 20 itens não é a mesma coisa que uma rara em 300.
- Pageviews medem atenção na Wikipédia, não intenção de jogo. É o proxy público
  mais próximo que existe sem dados de jogadores.
- O acervo não é completo. Perguntas com universo enumerável (estados, biomas)
  são completas; as culturais são uma amostra grande e verificada.
- A validação de ρ usa uma audiência anglófona; num acervo brasileiro a separação
  tende a ser melhor, mas isso não está provado.

## Créditos

Feito com Vite+ (React + TypeScript). Fontes: Fraunces, IBM Plex Sans e IBM Plex
Mono. Dados: Wikimedia (Wikidata, pt.wikipedia), wordfreq.
