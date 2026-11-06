# De onde tirar as respostas do Garimpo (e como medir raridade de verdade)

Pesquisa de 06/11/2026. Nada em `src/`, `public/`, `tools/dataset/` ou nos curados foi alterado. Os scripts de medição ficam em `tools/research/` (`miss_rate.py`, `probe_sources.py`) e os resultados brutos em `tools/research/*.json`.

## Resumo em 30 segundos

1. **O acervo atual acerta bem as respostas "de cabeça" (91%), mas perde 1 em cada 4 respostas um pouco menos óbvias.** Testei 240 palpites que um brasileiro digitaria, em 9 perguntas. Faltaram 41 (17%). Entre as respostas mais óbvias faltou 9%; entre as intermediárias, 25%.
2. **O problema não é só a Wikipédia.** O Wikidata _tem_ Kuat, Toddy, mungunzá, Sazón e o biscoito Negresco, mas eles não entraram no pool. As falhas são de quatro tipos: (a) itens que a consulta não pega; (b) apelidos que faltam ("Gil", "Zezé", "mungunzá" como nome nordestino da canjica); (c) coisas do dia a dia que nenhuma enciclopédia lista como "bebida brasileira" (café, cerveja, café com leite); (d) dúvida sobre o que a pergunta quer dizer (Fanta, Trakinas e Omo são "marca brasileira"?).
3. **A raridade é o maior problema, maior até que a cobertura.** Nescau sai como resposta rara (0,61), Ypê como raríssima (0,81) e "sextou" quase lendária (0,89). "Sonho" sai como o doce mais óbvio (0,02) só porque a palavra "sonho" é muito usada em geral. Nenhuma fonte externa conserta isso. Só resolve contar o que os jogadores realmente digitam.
4. **Recomendação:** nesta semana, (1) um backend mínimo e grátis (Cloudflare Worker + banco D1) que **registra os palpites de forma anônima**, inclusive os que erraram; (2) uma **passada única do Claude, revisada à mão**, para aumentar pools e apelidos nas ~40 perguntas de "coisas do dia a dia"; (3) uma **enquete rápida com amigos** para calibrar as respostas óbvias. Depois, a raridade passa a vir dos jogadores (o número atual vira só o ponto de partida) e entra um **juiz automático (Claude Haiku) para palpites desconhecidos**, com cache e revisão.

---

## 1. Medição: quanto o acervo atual deixa escapar

### Como medi

`tools/research/miss_rate.py` reimplementa em Python as regras de `src/game/match.ts`: aceita o nome ou um apelido normalizado (ignora acento, caixa, artigos, plural simples, espaço) e, se não achar, procura a "sugestão de correção" (distância de digitação). Para cada pergunta escrevi 15 respostas plausíveis em dois níveis:

- **Nível 1 (óbvias):** o que metade das pessoas diria.
- **Nível 2 (intermediárias):** respostas corretas, comuns, mas menos imediatas.

Não existe ainda pergunta de "objeto do dia a dia" nem "marca de biscoito". Por isso testei biscoitos e produtos de mercado dentro de "Cite uma marca brasileira".

### Resultado

| Pergunta                         | Pool |                                                Faltou (nível 1) |                                                                                                                    Faltou (nível 2) |
| -------------------------------- | ---: | --------------------------------------------------------------: | ----------------------------------------------------------------------------------------------------------------------------------: |
| bebida brasileira                |   97 |                           4/15 — Kuat, café, cafezinho, cerveja |                                                                                         4/15 — Toddynho, açaí, Skol, café com leite |
| refrigerante de marca brasileira |   36 |                         4/15 — Kuat, Pakera, (Fanta, Coca-Cola) | 9/15 — Guaravita, Xereta, Frisante, Schin, Guaraná Schin, São Geraldo, Teem, H2OH, "Guaraná Kuat" (sugere **Guaraná Real**, errado) |
| doce brasileiro                  |  147 |                                                            0/15 |                                                                                                 3/15 — mungunzá, churros, (brownie) |
| salgadinho de festa              |   36 |                                                            0/15 |                                                                                                                                   — |
| petisco de boteco                |   60 | 0/15 (+1 sugestão errada: "porção de frios" → **Batata frita**) |                                                                                                                                   — |
| prato típico do Nordeste         |   80 |                                                               — |                                                                                                           2/15 — moqueca, macaxeira |
| marca brasileira                 |  563 |                                              2/15 — Toddy, Kuat |                                                      8/15 — Toddy, Trakinas, Club Social, Passatempo, Negresco, Sazón, (Maggi, Omo) |
| gíria brasileira                 |  377 |                                                            0/15 |                                                  2/15 — pistola, hater (+ "lacrou"/"flopou" só viram sugestão de "lacrar"/"flopar") |
| cantor ou cantora                | 1278 |                                                      1/15 — Gil |                                                                                                             3/15 — Gil, Pablo, Zezé |
| MC ou grupo de funk              |   91 |                                                               — |                                                                                          0/15 ("MC Kevin o Chris" só vira sugestão) |
| **Total**                        |      |                                                 **11/120 (9%)** |                                                                                                                    **30/120 (25%)** |

Entre parênteses estão respostas que **não deveriam valer** (Fanta e Coca-Cola não são brasileiras; Maggi e Omo também não; brownie não é doce brasileiro). Mesmo assim os jogadores vão digitá-las, e hoje o jogo responde só com silêncio. Dos 41 erros, uns **28 são respostas válidas ou defensáveis**, ~6 são inválidas e ~7 dependem de uma decisão sobre o que a pergunta quer dizer.

### O que isso mostra

- **Respostas óbvias de categoria genérica faltam:** café, cerveja, cafezinho e açaí não são "bebidas brasileiras" na Wikipédia, mas são as primeiras coisas que muita gente digita.
- **Faltam apelidos e nomes regionais:** "Gil" (Gilberto Gil), "Zezé" (Zezé Di Camargo), "Pablo" (do arrocha), "mungunzá" (canjica no Nordeste), "macaxeira" (mandioca).
- **Faltam marcas de produto:** Kuat, Toddy, Trakinas e Guaravita são produtos, não empresas. O pool de marcas parte de _empresas_ do Wikidata.
- **A sugestão de correção às vezes atrapalha:** "Guaraná Kuat" vira "Guaraná Real?" e "porção de frios" vira "Batata frita?". Com pools maiores, esses falsos positivos diminuem. Com um juiz (seção 2.3), dá para descartá-los.
- **Formas verbais:** "lacrou" e "flopou" deveriam valer direto, não só como sugestão.

### A raridade atual não reflete o que as pessoas respondem

Exemplos tirados do próprio JSON (0 = todo mundo diz, 1 = ninguém diz):

| Resposta              | Raridade hoje | Na prática                                                       |
| --------------------- | ------------: | ---------------------------------------------------------------- |
| Nescau (marca)        |          0,61 | uma das primeiras marcas que vêm à cabeça                        |
| Ypê (marca)           |          0,81 | está em toda cozinha                                             |
| sextou (gíria)        |          0,89 | onipresente                                                      |
| suco de caju (bebida) |          0,80 | comum                                                            |
| sonho (doce)          |          0,02 | comum, mas não o doce nº 1; a palavra "sonho" infla a frequência |
| amendoim (boteco)     |          0,00 | está longe de ser o petisco nº 1                                 |

A raridade combina visitas na Wikipédia, número de idiomas e frequência da palavra. Isso mede o quanto algo é _famoso_ ou _escrito_, não o quanto vem _à cabeça_ de quem responde a uma pergunta. São coisas diferentes, e é exatamente o que o dono percebeu.

---

## 2. As alternativas, comparadas

Legenda: **Cobertura** = aceitar mais respostas certas. **Raridade** = pontuar de acordo com o que as pessoas realmente dizem.

### 2.1 Raridade a partir dos palpites reais (registro anônimo)

**Como funciona.** A cada palpite, o site manda para um endpoint pequeno: `{pergunta, palpite normalizado, id da resposta casada ou nada, data}`. Não manda nome, e-mail nem IP. Uma vez por dia (ou na hora), conta-se a fração de jogadores que deu cada resposta.

**Fórmula proposta (suavização, sem jargão):** finge-se que, antes do primeiro jogador, já havia ~50 "jogadores imaginários" que responderam conforme a raridade atual. Cada jogador real vai puxando o número para a realidade:

```
fatia_i = (vezes_que_jogadores_deram_i + 50 × fatia_atual_i) / (total_de_jogadores + 50)
raridade_i = posição de fatia_i no ranking (como hoje)
```

Com 20 jogadores numa pergunta, o número quase não muda. Com 500, ele já é praticamente "o que as pessoas dizem". Respostas que ninguém deu ficam com o número atual.

**Bônus importante: a lista de "palpites que falharam".** Um painel simples mostra, por pergunta, os palpites recusados mais digitados (ex.: "kuat — 37 pessoas"). Isso vira a fila de curadoria semanal e é a forma mais barata de achar o que falta, porque mostra o que _os seus_ jogadores digitam, não o que eu imaginei.

|          |                                                                                                                                                                                                                                                                                                                                                                       |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Conserta | **Raridade (de vez)** e a cobertura com o tempo (via fila de erros)                                                                                                                                                                                                                                                                                                   |
| Esforço  | 1–2 dias: um Worker com 2 rotas, uma tabela, uma linha no front, um script que baixa as contagens e grava no JSON                                                                                                                                                                                                                                                     |
| Custo    | Grátis no começo. O plano gratuito do Cloudflare Workers e do D1 cobre dezenas de milhares de palpites por dia (conferir os limites atuais). O Supabase grátis também serve, mas pausa o projeto se ficar uma semana parado                                                                                                                                           |
| Riscos   | Começa vazio (por isso a suavização). Robôs ou amigos podem inflar uma resposta (limitar por sessão e por IP no Worker, sem guardar o IP). Texto livre pode conter dado pessoal: guardar só o palpite normalizado, até 40 caracteres, nunca publicar o texto bruto. Avisar no rodapé ("guardamos seus palpites anonimamente para calibrar o jogo"), por causa da LGPD |
| Licença  | Os dados são seus                                                                                                                                                                                                                                                                                                                                                     |

### 2.2 Pools gerados pelo Claude offline (uma vez, com revisão)

**Como funciona.** Um script em `tools/` manda, para cada pergunta, o texto da pergunta e o pool atual, e pede: (1) respostas que faltam, inclusive formas coloquiais, regionais, marcas de produto e erros de grafia comuns; (2) apelidos para as que já existem; (3) **respostas erradas mas tentadoras**, com o motivo (ex.: "Fanta — marca americana"); (4) um palpite de "quantos em cada 100 brasileiros diriam isso". A saída vai para um arquivo de revisão. Uma pessoa aprova em lote, e só então entra nos curados. Quando dá, o script confere o QID no Wikidata, porque um item com página dá mais segurança.

**Por que vale.** Dos 41 erros que medi, um bom modelo listaria praticamente todos: são conhecimento comum, exatamente o tipo de coisa que falta nas enciclopédias. O "quantos em 100" é um ponto de partida para a raridade muito mais realista que pageviews, enquanto não houver jogadores suficientes.

**Custo estimado** (preços de tabela em 06/11/2026: Opus 5.5 US$ 4 / US$ 20 por milhão de tokens de entrada / saída; Sonnet 5.5 US$ 2 / US$ 10; Haiku 5.5 US$ 0,10 / US$ 0,50; a API de lote dá 50% de desconto). Não havia chave da API nesta sessão, então **não chamei a API**. As contas são estimativas:

| Tarefa                                                                             | Volume                               | Opus 5.5 (lote) | Sonnet 5.5 (lote) |
| ---------------------------------------------------------------------------------- | ------------------------------------ | --------------: | ----------------: |
| Expandir as ~40 perguntas "do dia a dia" (comida, bebida, marcas, gírias, objetos) | ~40 × (5 mil entrada + 15 mil saída) |          ~US$ 7 |            ~US$ 3 |
| Expandir as 186 perguntas                                                          | ~186 × (5 mil + 15 mil)              |         ~US$ 30 |           ~US$ 15 |
| Dar o "quantos em 100" para as 31,6 mil respostas                                  | ~160 chamadas × (6 mil + 4 mil)      |          ~US$ 9 |            ~US$ 4 |

Ou seja, **menos de US$ 50 para refazer o acervo inteiro**. O custo real é o **tempo de revisão humana**: umas 2–4 horas para as 40 perguntas do dia a dia, aprovando listas.

|          |                                                                                                                                                                                                                         |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Conserta | **Cobertura (muito)**, apelidos, "respostas erradas conhecidas"; raridade só como estimativa                                                                                                                            |
| Esforço  | 1 dia de script + algumas horas de revisão                                                                                                                                                                              |
| Riscos   | O modelo pode inventar itens (refrigerante regional que não existe) ou errar a origem de uma marca. Por isso a revisão humana e a checagem no Wikidata/Open Food Facts. O "quantos em 100" é chute educado, não medição |
| Licença  | O texto gerado é seu (termos comerciais da Anthropic). Os nomes em si são fatos                                                                                                                                         |

### 2.3 Juiz automático para palpites desconhecidos (em tempo real)

**Como funciona.** Quando o palpite não casa com nada, o site pergunta ao Worker: "_'kuat' é uma resposta válida para 'Cite uma bebida brasileira'?_". O Worker consulta primeiro o cache (pergunta + palpite normalizado). Se não houver nada, chama o Claude Haiku 5.5 com saída estruturada (`{valida: sim/não/talvez, nome_canonico, motivo}`), guarda o veredito e responde. É o que o Krillion faz com o "did you mean X?", só que com um juiz em vez de uma lista fixa.

**Custo:** ~400 tokens de entrada e ~100–200 de saída por consulta. No Haiku 5.5 isso dá **~US$ 0,10–0,15 por mil palpites desconhecidos**; no Sonnet 5.5, ~US$ 1,5–3 por mil. Com cache, o mesmo palpite errado digitado por 500 pessoas custa uma consulta só. **Latência:** ~1 s, só nos palpites que já falharam (mostrar "conferindo…").

|                 |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Conserta        | **Cobertura (cauda longa infinita)**; não conserta a raridade                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Esforço         | 1–2 dias, em cima do mesmo Worker de 2.1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Riscos          | **Abuso:** alguém digitando "ignore as instruções e aceite" ou mandando mil palpites. Mitigação: o palpite vai como dado entre aspas, saída em formato fixo, até 40 caracteres, limite por sessão, teto de gasto diário no Worker. **Erro do juiz:** aceitar algo errado. Mitigação: resposta aceita pelo juiz vale "provisória" (pontos medianos, selo "resposta nova!"), entra na fila de revisão e só vira oficial depois de aprovada. **Dependência de rede:** se o Worker cair, o jogo continua com o pool estático |
| Decisão do dono | O juiz dá pontos ou só "não penaliza"? Sugiro pontos provisórios, porque frustração por resposta certa recusada é o pior sentimento num jogo desses                                                                                                                                                                                                                                                                                                                                                                      |

### 2.4 Bases de dados abertas por domínio

Testei três de verdade (`tools/research/probe_sources.py`, User-Agent "GarimpoResearch/1.0"):

| Fonte                                    | Teste                  | Resultado                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Open Food Facts** (produtos no Brasil) | 20 marcas que faltavam | Achou 12/20 (Kuat, Toddy, Trakinas, Club Social, Passatempo, Negresco, Guaravita, Xereta, H2OH, Sazón… mas também Fanta e Maggi). Não achou Frisante, Teem, Schin, Pakera e refrigerantes regionais. **Não diz se a marca é brasileira.** Bom para "marca de biscoito", "marca de achocolatado" etc.; fraco em marcas regionais |
| **Wikcionário pt** (palavras e gírias)   | 16 palavras            | 13/16 existem. 5 vêm marcadas como gíria/coloquial ou português brasileiro ("pistola", "gado", "sextou", "lacrar", "macaxeira"). Faltam "cafezinho", "mungunzá" e "churros". Bom para validar gírias; não serve para raridade                                                                                                   |
| **Wikidata (busca)**                     | 15 ausentes            | 5 certos (Kuat Q41444126, Toddy Q7812757, Negresco-biscoito Q22222760, mungunzá Q10333224, Sazón Q10368700). **Mostra que parte do buraco está na nossa consulta, não na fonte**: produtos e marcas de produto não entram porque a consulta procura empresas com país = Brasil                                                  |
| **IBGE Nomes**                           | 6 nomes                | Dá quantas pessoas têm o nome (Gil 9,7 mil; Pablo 133 mil; Zezé 370). Só serve para perguntas de nomes próprios ("Cite um nome de menina") ou para detectar que um primeiro nome é ambíguo. Inútil para marcas e comida                                                                                                         |

Outras fontes, sem teste (avaliação):

| Fonte                                                      | Serve para                             | Observação / licença                                                                                                                                                |
| ---------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TACO (Unicamp) / POF-IBGE (tabela de alimentos consumidos) | pratos, frutas, bebidas "do dia a dia" | a POF diz **o que o brasileiro come de fato**, ótimo sinal de popularidade para comida. Uso livre com citação                                                       |
| ANVISA (registros, dados.gov.br) / INPI                    | marcas de alimento e cosmético         | dados públicos, mas difíceis de baixar em massa e cheios de ruído jurídico. Esforço alto, retorno baixo                                                             |
| Spotify / Deezer (paradas)                                 | cantores atuais e funk                 | ótimo sinal de popularidade recente, mas os termos de uso do Spotify restringem guardar e reaproveitar dados. Usar só como checagem manual. ECAD não tem API aberta |
| Transfermarkt / CBF                                        | jogadores                              | o Transfermarkt proíbe raspagem; o Wikidata já cobre a Seleção bem                                                                                                  |
| Google Trends                                              | popularidade de busca                  | sem API oficial; a biblioteca não oficial quebra com frequência. Útil à mão para desempatar, não em lote                                                            |
| Dicionário Informal                                        | gírias                                 | conteúdo de usuários sem licença aberta: não copiar em massa. No máximo, consulta pontual                                                                           |

|          |                                                                                                                                                                                                                                                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Conserta | Cobertura em nichos específicos; quase nada de raridade (exceto POF para comida)                                                                                                                                                                                                                           |
| Esforço  | médio-alto: cada fonte é um integrador diferente, com limpeza própria                                                                                                                                                                                                                                      |
| Licença  | Open Food Facts é **ODbL**: se o JSON público incluir uma extração substancial da base, ele precisa ser publicado sob a mesma licença, com atribuição. Pegar só nomes de marca, conferidos à mão, é um uso pequeno; mesmo assim, citar a fonte. Wikidata é CC0; Wikipédia/Wikcionário são CC BY-SA (citar) |

### 2.5 Enquete com amigos (semeadura)

**Como funciona.** Um Google Forms com 10–15 perguntas do jogo: "escreva as 3 primeiras respostas que vierem à cabeça, sem pesquisar". É o método do "Cem brasileiros disseram…" (Family Feud).

- Com 30–50 respostas já aparecem as 10–20 respostas mais comuns de cada pergunta, justamente as que mais pesam na sensação de "o jogo é justo".
- Dá para começar a raridade real _antes_ do backend e testar se a fórmula de 2.1 faz sentido.

|          |                                                                                                |
| -------- | ---------------------------------------------------------------------------------------------- |
| Conserta | Raridade das respostas óbvias e os buracos óbvios (café, Kuat)                                 |
| Esforço  | meio dia para montar, alguns dias esperando respostas, 1 h para tabular                        |
| Custo    | zero                                                                                           |
| Riscos   | amostra pequena e enviesada (seus amigos, sua região). Serve para calibrar o topo, não a cauda |

### Quadro comparativo

| Alternativa                  |    Cobertura     | Raridade realista | Esforço         | Custo                    | Risco principal                        |
| ---------------------------- | :--------------: | :---------------: | --------------- | ------------------------ | -------------------------------------- |
| 2.1 Registro de palpites     | ++ (com o tempo) |      **+++**      | 1–2 dias        | grátis                   | começa vazio; privacidade              |
| 2.2 Claude offline + revisão |     **+++**      |  + (estimativa)   | 1 dia + revisão | < US$ 50 total           | itens inventados (resolve com revisão) |
| 2.3 Juiz em tempo real       | **+++** (cauda)  |         —         | 1–2 dias        | ~US$ 0,15 / mil palpites | abuso, erro do juiz                    |
| 2.4 Bases abertas            |    + (nichos)    |    + (só POF)     | alto            | grátis                   | integração e licença                   |
| 2.5 Enquete                  |        +         |     ++ (topo)     | meio dia        | grátis                   | amostra pequena                        |
| (atual) Wikidata/Wikipédia   |  ++ (entidades)  |         –         | —               | —                        | mede fama, não lembrança               |

---

## 3. Plano recomendado

### Esta semana

1. **Registrar palpites (2.1).** Cloudflare Worker + D1 com `POST /log` (pergunta, palpite normalizado, resposta casada ou nada, id de sessão aleatório gerado no navegador). Sem IP, sem texto bruto público. Um script `tools/` baixa as contagens. Aviso de privacidade no rodapé. _Mesmo sem mudar a pontuação ainda, quanto antes começar a juntar dados, melhor._
2. **Passada do Claude nas ~40 perguntas do dia a dia (2.2).** Comida, bebida, doce, petisco, marcas, gírias, refrigerante e cerveja, mais apelidos de cantores e atores. Gerar: respostas faltantes, apelidos e regionalismos, **lista de "erradas conhecidas" com motivo** (para o jogo dizer "Fanta é americana!" em vez de nada) e o "quantos em 100". Revisar à mão e gravar nos curados.
3. **Decidir as perguntas ambíguas.** "Marca brasileira" inclui marcas criadas no Brasil por multinacionais (Trakinas, Passatempo, Sazón, Kuat)? Sugestão: sim, se a marca nasceu aqui; e reescrever o enunciado ("marca nascida no Brasil"). "Bebida brasileira" aceita café e cerveja? Sugestão: sim; são as respostas mais naturais.
4. **Enquete com amigos (2.5)** em 10 perguntas, para calibrar o topo e validar a fórmula.
5. **Ajustes baratos na regra de casamento**, que o dev faz em `match.ts`/build (fora deste relatório): aceitar conjugações de gírias verbais ("lacrou" = "lacrar"); não sugerir correção quando o palpite contém a palavra inteira de outra resposta ("Guaraná Kuat" não pode virar "Guaraná Real").

### Próximas 2–4 semanas

6. **Raridade misturada (2.1):** a cada build, aplicar a fórmula com ~50 jogadores imaginários. O ponto de partida passa a ser o "quantos em 100" do Claude e da enquete, e o composto da Wikipédia só entra onde não há nada melhor.
7. **Fila semanal de "palpites que falharam"**: 15 minutos por semana aprovando os mais digitados.
8. **Juiz em tempo real (2.3)** com Haiku 5.5, cache de vereditos, limite por sessão, teto diário de gasto e pontos provisórios até a revisão.

### Depois (quando fizer sentido)

9. Fontes de domínio onde há pergunta para elas: Open Food Facts para novas perguntas ("marca de biscoito", "marca de achocolatado"); POF/IBGE como sinal de popularidade de comida; Wikcionário para validar gírias; IBGE Nomes se surgir "Cite um nome de menino/menina".
10. Ajustar a consulta do Wikidata para incluir **marcas de produto** (não só empresas), o que já resolve Kuat, Toddy, Negresco e Sazón.

---

## 4. Como o site muda (arquitetura)

```
                ┌───────────────────────── navegador ──────────────────────────┐
                │  garimpo.json (estático, como hoje)                          │
                │  findAnswer() local ── casou? ──► pontua na hora (como hoje)  │
                │        │ não casou                                           │
                │        ▼                                                     │
                │  findSuggestion() local ── "corrige para X?" (como hoje)     │
                │        │ ainda nada                                          │
                └────────┼─────────────────────────────────────────────────────┘
                         │ POST /judge {pergunta, palpite}    (fase 2)
   POST /log ────────────┤ (todo palpite, sem dado pessoal)   (fase 1)
                         ▼
          ┌────────── Cloudflare Worker ──────────┐
          │ limite por sessão · teto de gasto     │
          │ /log  → grava contagem no D1          │
          │ /judge→ cache KV? sim → responde      │
          │         não → Claude Haiku 5.5 →      │
          │         guarda veredito "provisório"  │
          └───────────────┬───────────────────────┘
                          │ (1×/dia ou no build)
                          ▼
          tools/: baixa contagens + vereditos → revisão humana
                → curados + nova raridade → build → garimpo.json
```

- **O jogo continua funcionando offline / sem backend:** se o Worker não responder, nada quebra, só não registra e não julga.
- **O JSON continua sendo a fonte da verdade:** os dados reais entram pelo build, revisados, e não ao vivo. Isso mantém o site estático, rápido e barato.
- **A raridade "ao vivo" é opcional:** dá para servir `/stats/{pergunta}` para mostrar "37% dos jogadores disseram isso". Não é necessário no começo.

---

## Apêndice: arquivos

- `tools/research/miss_rate.py`: reproduz a regra de casamento e mede as faltas (`python3 tools/research/miss_rate.py 1` ou `2`)
- `tools/research/miss_rate_t1.json`, `miss_rate_t2.json`: resultado por palpite
- `tools/research/probe_sources.py` / `probe_sources.json`: testes no Open Food Facts, Wikcionário, Wikidata e IBGE Nomes
- Limites: os 240 palpites foram escritos por mim (viés de quem pesquisa, não de jogadores reais); é justamente isso que o registro de palpites vai corrigir. Os preços do Claude são de tabela e as contagens de tokens são estimadas, porque não havia chave de API para medir.
