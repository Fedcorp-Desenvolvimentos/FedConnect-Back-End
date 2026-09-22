# Requisitos — Indicadores executivos da produção (espelho da CORP e agregações)

> **Rastreabilidade** — RF: RF-IEX-001..007 · RNF: RNF-IEX-001..004 · Questões: PA-018, PA-019, PA-020, PA-021, PA-022
> **Status:** em revisão · **Dono:** Hamilton (gestor comercial), via Lucas Guidi · **Atualizado:** 2026-09-22
> **Lado frontend:** `FedConnect-FrontEnd/specs/indicadores-executivos/`. **Referências recebidas do dono em 2026-09-22:** protótipo `index.html`, snapshot `dados-teste.json` (dado real, fora do git) e `DEFINICAO-TECNICA.md` do pacote `pacote-indicador-executivo`.

## Contexto e Problema

`[D]` PA-018: o gestor comercial pediu um painel de indicadores da produção de seguros dentro do FedConnect, como primeiro tile de uma área de indicadores, e entregou um protótipo funcional com as regras já definidas. `[E]` O repositório não tem nenhuma agregação no ORM (`Sum`, `Count`, `Trunc*` ausentes; verificado em 2026-09-22): os endpoints `analytics/` em `fedhub/views/analytics_view.py` são proxy ao FedHub. `[E]` Não existe modelo, serviço ou vocabulário de seguradora, apólice, renovação ou captação no código (busca em 2026-09-22); "comissão" no repo é comissão de voucher (`fedhub/models.py`), outro conceito. `[D]` PA-018: a v1 é local, carregada a partir do snapshot da CORP; a ligação com os dados vivos (lake) é fase 2 (PA-021).

## Escopo

**Dentro do escopo:**
- App Django novo `indicadores` com o espelho normalizado das tabelas da CORP que o indicador usa (produção, cliente, ramo, seguradora, documento, negócio de origem) e o registro de cada carga.
- Management command que carrega o snapshot (arquivo local, fora do git) e calcula a classificação de renovação.
- Endpoints de leitura, já agregados, para cada seção do painel: resumo, por seguradora, séries por dia e por mês, não fechadas do mês, composição, domínios.

**Fora do escopo:**
- Cliente HTTP da API CORP e ingestão agendada dos dados vivos (fase 2, PA-021, spec própria).
- `/itens` e tabelas de item segurado; exportação xlsx/PDF; metas; substituição dos dashboards Power BI de `/metricas`.
- Controle de acesso por nível além de estar autenticado (decisão do dono em PA-018).

## User Stories e Critérios de Aceitação

### RF-IEX-001: Carregar o snapshot da CORP no Postgres

**Como** desenvolvedor, **quero** carregar o snapshot da CORP no banco local com um comando, **para** construir e testar o painel sem acesso à API nem ao lake.

- **QUANDO** executo `python manage.py carregar_snapshot_corp <caminho>` com um JSON no contrato do snapshot (`gerado_em`, `extracao`, `colunas`, `docs`, `clientes`, `seguradoras`, `ramos`, `valores`, `negocios`, `fontes`), **ENTÃO** o sistema **DEVE** gravar clientes, ramos, seguradoras, produção, documento (valores) e negócio de origem por `upsert` na chave natural, dentro de uma transação, e registrar a carga (origem, `extraido_em`, contagens por tabela, rejeitos, duração). `[E]` contrato em `DEFINICAO-TECNICA.md` §7 do pacote recebido em 2026-09-22; `[E]` padrão de management command em `fedhub/management/commands/`
- **QUANDO** um documento cita cliente, ramo ou seguradora que não existe no snapshot, **ENTÃO** o sistema **DEVE** gravar o documento com a referência nula e contar o caso como rejeito nomeado na carga, nunca descartar em silêncio. `[E]` `DEFINICAO-TECNICA.md` §8
- **QUANDO** uma data vem inválida ou ausente (`datemi`, `inivig`, `fimvig`), **ENTÃO** o sistema **DEVE** gravar nulo e contar; **NÃO DEVE** corrigir por suposição. `[E]` §8; no snapshot há 2.037 documentos sem `datemi` e datas como 2052 (medição 2026-09-22)
- **QUANDO** a carga termina, **ENTÃO** cada documento de produção **DEVE** ter `renovacao` gravado: verdadeiro se `nosnum_ren > 0` **ou** se existe outro documento do mesmo CPF/CNPJ, de qualquer ramo ou seguradora, cancelado ou não, com `inivig` menor (empate resolvido por `nosnum` menor); cliente sem CPF/CNPJ só pela cadeia `nosnum_ren`. `[D]` PA-018 (regra do dono, "HC em 22/09/2026", no protótipo e em `DEFINICAO-TECNICA.md` §4)
- **QUANDO** o mesmo snapshot é carregado duas vezes, **ENTÃO** o sistema **NÃO DEVE** duplicar linha nenhuma (chave natural `nosnum`; `codfil` opcional). `[P]` PA-020

### RF-IEX-002: Domínios e metadados

**Como** tela, **quero** as listas de ramos e seguradoras com contagens e a data da extração, **para** montar os filtros e o cabeçalho.

- **QUANDO** consulto `GET indicadores/dominios/` com os mesmos filtros de RF-IEX-003, **ENTÃO** o sistema **DEVE** devolver `extraido_em`, total de documentos na base, e para cada ramo e cada seguradora: sigla, nome, total na base e fechados no período (o contador de ramo respeita as seguradoras escolhidas e vice-versa). `[E]` `montarRamos()` do protótipo

### RF-IEX-003: Resumo do período (os cartões)

**Como** diretor, **quero** os cinco números do período escolhido com comparação, **para** ler a produção num olhar.

- **QUANDO** consulto `GET indicadores/resumo/?periodo=hoje|semana|mes|ano|faixa&data_referencia=AAAA-MM-DD[&data_ini&data_fim][&ramo=..&seguradora=..][&incluir_cancelados][&todos_tipdoc][&janela_dias]`, **ENTÃO** o sistema **DEVE** aplicar o universo padrão (`tipdoc = 'A'`, não cancelado) e devolver, para o período pedido **e** para hoje/semana/mês/ano da mesma referência: `fechados`, `renovacoes`, `captacoes`, `com_negocio_origem`, `valor_fechado` com `documentos_com_valor`, `comissao` com `documentos_com_comissao`. `[E]` `agregar()` do protótipo; `[E]` `DEFINICAO-TECNICA.md` §4
- **QUANDO** o período tem documentos sem valor conhecido, **ENTÃO** a resposta **DEVE** trazer a soma dos que têm e a cobertura; **NÃO DEVE** somar zero no lugar do ausente. `[P]` PA-019
- **QUANDO** consulto, **ENTÃO** a resposta **DEVE** trazer também o período anterior equivalente (dia anterior, semana anterior, mesmo trecho do mês anterior, mesmo trecho do ano anterior, intervalo anterior de mesma duração) com os mesmos campos, para a tela calcular o delta. `[E]` `periodos()` do protótipo
- **ENQUANTO** a semana é o período, o sistema **DEVE** contar de segunda-feira até a referência; mês do dia 1 até a referência; ano de 1º de janeiro até a referência; tudo pela `datemi`. `[E]` `DEFINICAO-TECNICA.md` §4 e glossário do protótipo
- **SE** a `data_referencia` é posterior à extração, **ENTÃO** o sistema **DEVE** responder normalmente e marcar `dados_parciais: true`. `[E]` lacuna declarada no protótipo

### RF-IEX-004: Por seguradora

**Como** diretor, **quero** os mesmos números abertos por seguradora, **para** comparar carteiras.

- **QUANDO** consulto `GET indicadores/por-seguradora/` com os filtros de RF-IEX-003, **ENTÃO** o sistema **DEVE** devolver uma linha por seguradora com fechados, valor fechado e cobertura, renovações, captações, comissão e cobertura, e não fechadas do mês (RF-IEX-006), ordenada por fechados decrescente, mais a linha de total. `[E]` `renderTabSeg()` do protótipo
- **QUANDO** a resposta volta, **ENTÃO** a soma das linhas **DEVE** ser igual ao total e `fechados = renovacoes + captacoes` em cada linha. `[E]` `DEFINICAO-TECNICA.md` §8

### RF-IEX-005: Séries por dia e por mês

**Como** diretor, **quero** a evolução das emissões, **para** ver tendência.

- **QUANDO** consulto `GET indicadores/serie/?tipo=dia|mes` com os filtros, **ENTÃO** o sistema **DEVE** devolver, para `dia`, os 30 dias até a referência e, para `mes`, os 12 meses do ano da referência (meses depois da referência marcados como futuros), cada ponto com renovações, captações, total, valor, comissão e coberturas. `[E]` `renderChartDia()`, `meses()` do protótipo
- **ENQUANTO** o corte de dia, semana e mês é calculado, o sistema **DEVE** usar o fuso `America/Sao_Paulo`, nunca UTC. `[E]` `bigcorp/settings.py` (`USE_TZ = True`, `TIME_ZONE`)

### RF-IEX-006: Não fechadas do mês

**Como** diretor, **quero** saber quais apólices venceram no mês sem nova apólice, **para** agir sobre a perda.

- **QUANDO** consulto `GET indicadores/nao-fechadas/` com a referência e os filtros, **ENTÃO** o sistema **DEVE** considerar as apólices do universo com `fimvig` no mês da referência e devolver: contagens (vencem no mês, já vencidas até a referência, vencidas sem nova apólice, a vencer, distribuição de `renovacao_situacao` das vencidas) e duas listas, `vencidas` (só `renovacao_situacao ∈ {2, 3}` e `fimvig ≤ referência`) e `a_vencer`, cada linha com fim de vigência, cliente, CPF/CNPJ **mascarado**, seguradora, ramo, `nosnum`, emissão, situação CORP, novas apólices (código e seguradora) e situação de sinistro. `[E]` `naoFechadas()` e `renderNf()` do protótipo; `[D]` PA-022
- **QUANDO** avalio se a apólice tem nova apólice, **ENTÃO** o sistema **DEVE** considerar (a) documento posterior com `nosnum_ren` apontando para ela, ou (b) apólice A não cancelada do mesmo CPF/CNPJ com `inivig` em `fimvig ± janela_dias` (padrão 30), **em qualquer ramo**. `[E]` `DEFINICAO-TECNICA.md` §4
- **QUANDO** a lista passa de 400 linhas, **ENTÃO** o sistema **DEVE** cortar em 400 e informar quantas ficaram de fora. `[E]` limite do protótipo

### RF-IEX-007: Composição dos indicadores

**Como** diretor, **quero** ver quais objetos compõem cada número, **para** conferir o cartão.

- **QUANDO** consulto `GET indicadores/composicao/` com os filtros, **ENTÃO** o sistema **DEVE** devolver três listas — captações, renovações (emitidas no período, ordem de emissão decrescente e cliente) e vencidas sem nova apólice (ordem de `fimvig` decrescente) — cada linha com objeto/cliente, seguradora, ramo, apólice e data. `[E]` `renderComposicao()` do protótipo
- **QUANDO** a resposta volta, **ENTÃO** as quantidades das listas **DEVEM** ser exatamente as dos cartões de RF-IEX-003 e RF-IEX-006 para os mesmos filtros. `[E]` `DEFINICAO-TECNICA.md` §8

## Requisitos Não Funcionais

### RNF-IEX-001: Segurança

Todas as rotas exigem JWT válido (`IsAuthenticated`); sem restrição por nível nesta versão. `[D]` PA-018. CPF sai mascarado em toda lista; CNPJ e nome saem completos. `[P]` PA-022. Nenhum token da CORP ou do lake em código, log, spec ou resposta: só variável de ambiente, quando existir. `[E]` `CLAUDE.md` e CONVENCOES §8. Snapshot com dado real fica fora do repositório; os testes usam dados sintéticos. `[E]` CONVENCOES §8

### RNF-IEX-002: Compatibilidade e contrato

Nomes de campo seguem os da CORP (`nosnum`, `datemi`, `inivig`, `fimvig`, `pretot`, `val_c`, `renovacao_situacao`), sem tradução, para a tela, o glossário e o lake falarem a mesma língua. `[E]` `DEFINICAO-TECNICA.md` §3. Valores monetários viajam como string decimal (`DecimalField(14,2)`), nunca float. `[E]` `fedhub/models.py`. Toda soma monetária vem acompanhada da contagem de documentos com valor. `[P]` PA-019. O contrato de resposta é citado pela spec do frontend pelo caminho deste arquivo.

### RNF-IEX-003: Desempenho

Agregações no banco (ORM), nunca no Python linha a linha, nem no navegador. Base de referência: 25.760 documentos. Cada endpoint responde em menos de 2 s nessa base em ambiente local; nenhuma resposta envia o histórico inteiro. `[E]` medição do snapshot em 2026-09-22. Endpoints documentados com `extend_schema`. `[E]` dívida registrada em `docs/curso-cipa/RETROSPECTIVA_CURSO_CIPA.md`

### RNF-IEX-004: Fonte trocável

O modelo e os endpoints não sabem de onde veio a carga: `CargaCorp.origem` distingue `snapshot` de `lake`. A fase 2 substitui só o carregador. `[P]` PA-021

**Verificação prevista (detalhada no design, após aprovação):** CT-IEX-001 — carga do snapshot sintético: contagens, rejeitos nomeados, datas inválidas nulas, idempotência. CT-IEX-002 — classificação de renovação: cadeia `nosnum_ren`, CPF com apólice anterior, empate por `nosnum`, cliente sem documento. CT-IEX-003 — resumo: universo padrão, toggles, períodos e períodos anteriores, cobertura, `dados_parciais`. CT-IEX-004 — por seguradora: soma das linhas = total, `fechados = ren + cap`. CT-IEX-005 — séries: 30 dias, 12 meses, futuro marcado, fuso local no corte do dia. CT-IEX-006 — não fechadas: janela, nova apólice por cadeia e por CPF em outro ramo, `renovacao_situacao`, mascaramento, corte em 400. CT-IEX-007 — composição: quantidades iguais aos cartões. CT-IEX-008 — segurança: sem JWT → 401; com JWT de qualquer nível → 200; nenhum CPF completo na resposta.

## Questões em Aberto

- PA-019: cobertura de prêmio e comissão — trava o valor exibido em RF-IEX-003 e RF-IEX-004, não a entrega
- PA-020: `codfil`, letras de `tipdoc`, `renovacao_situacao = 5`, corte do histórico — trava a chave de RF-IEX-001
- PA-021: ingestão dos dados vivos — trava a fase 2 (RNF-IEX-004)
- PA-022: mascaramento — hipótese aplicada em RF-IEX-006 e RNF-IEX-001
