# Requisitos — Painel de TV alimentado pelo Data Lake CORP (via FedHub)

> **Rastreabilidade** — RF: RF-IEX-009 · RNF: RNF-IEX-005 · Questões: PA-024
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana (arquitetura de dados), painel do gestor comercial via Lucas Guidi · **Atualizado:** 2026-09-23
> **Lado frontend:** `FedConnect-FrontEnd/public/tv/painel.html` e o card em `src/pages/Indicadores/Home/IndicadoresHome.jsx`. **Lado FedHub:** `FedHub-Backend/specs/lake-financeiro/` (rota `GET /api/lake/painel-tv`). **Lado lake:** `datalake/pipeline/ddl/contrato-financeiro.sql` (`vw_painel_tv`).

<!-- Contexto IEX (CONVENCOES §2.1): mesmo app `indicadores`, IDs continuam de RF-IEX-008.
     Spec separada porque o dono e a origem do dado são outros: aqui nada vem do espelho. -->

## Contexto e Problema

`[E]` O card "Painel de TV" da home de indicadores abria `public/tv/painel.html`, um protótipo com valores fixos (`const EXEMPLO`, "DADOS ILUSTRATIVOS", verificado em 2026-09-23). `[D]` PA-024: a ordem de 23/09/2026 é alimentá-lo com dado real, e a regra do número (mês corrente × mesmo mês do ano anterior por seguradora × ramo, com meta) **mora no Data Lake CORP**, não neste repositório — decisão da arquitetura de dados registrada nas decisões de arquitetura do pacote do lake (classificação e meta vivem no lake). `[E]` O FedConnect roda na Digital Ocean e não alcança o lake; o FedHub alcança e já expõe `GET /api/lake/painel-tv` (spec `lake-financeiro` do FedHub, aprovada em 2026-09-23). `[E]` Este repositório já fala com o FedHub por `consultas/utils/get_headers.py` (bearer + chave legada + gateway).

## Escopo

**Dentro do escopo:**
- Uma rota de leitura, `GET indicadores/painel-tv/`, autenticada pelo JWT do usuário, que repassa as linhas de `vw_painel_tv` lidas pelo FedHub.
- A página estática do painel buscando essa rota, agrupando por seguradora e recarregando a cada 10 minutos.

**Fora do escopo:**
- Recalcular, somar ou converter valor no backend (RNF-IEX-005).
- Cadastro de meta: continua em RF-IEX-008 até a migração da meta para o lake (decisão do pacote do lake: meta no lake) ser feita — aí a comparação passa a vir pronta na view.
- Ler o painel do espelho local (`Producao`): o espelho é a v1 da ADR-0009 e não é a origem deste número.

## User Stories e Critérios de Aceitação

### RF-IEX-009: Painel de TV com dado do lake

**Como** gestor comercial, **quero** o monitor do setor mostrando o prêmio do mês por seguradora e ramo contra o ano anterior e a meta, **para** acompanhar a produção sem abrir relatório.

- **QUANDO** um usuário autenticado consulta `GET indicadores/painel-tv/`, **ENTÃO** o sistema **DEVE** devolver `{"sucesso": true, "gerado_em": <ISO>, "linhas": [...]}` onde `linhas` é exatamente o que o FedHub devolveu em `/api/lake/painel-tv` (colunas de `vw_painel_tv`: `seguradora_sigla`, `seguradora_nome`, `codram`, `ramo_sigla`, `ramo_nome`, `mes_atual`, `mes_anterior`, `valor_atual`, `valor_anterior`, `apolices_atual`, `apolices_anterior`, `valor_meta`, `variacao_percentual`, `atingimento`). `[E]` medição de 2026-09-23: 45 linhas, 0,45 s pela rota local
- **SE** a consulta vem sem JWT válido, **ENTÃO** o sistema **DEVE** responder 401 — a página é aberta a partir do FedConnect logado e lê o mesmo token. `[D]` PA-024: autenticação pelo FedConnect
- **SE** o FedHub responde 503, **ENTÃO** o sistema **DEVE** responder 503 com `{"sucesso": false, "erro": <o erro nomeado pelo FedHub>, "detalhe": ...}` — `lake_nao_configurado`, `lake_indisponivel` ou `contrato_nao_publicado`. `[E]` `FedHub-Backend/specs/lake-financeiro/design.md`, Tratamento de Erros
- **SE** o FedHub não responde, **ENTÃO** o sistema **DEVE** responder 503 com `erro: fedhub_indisponivel`, e nenhuma outra rota é afetada.
- **QUANDO** a página recebe as linhas, **ENTÃO** ela **DEVE** exibir só as seguradoras escolhidas para o monitor — Allianz, Bradesco, AXA, Chubb, Porto Seguro, HDI e Tokio Marine (siglas `ALLI`, `BRAD`, `AXA`, `CHUB`, `PORT`, `HDI`, `TOKI`; lista `SEGURADORAS_EXIBIDAS` na própria página) `[D]` PA-024 (23/09/2026) —, agrupar por seguradora, descartar ramo sem valor nos dois anos, ordenar seguradoras pelo valor do mês atual e recarregar a cada 10 minutos — a mesma cadência da rotina intradiária do lake. `[E]` decisão do pacote do lake sobre a rotina intradiária (janela de vigência, 10 em 10 minutos)

## Requisitos Não Funcionais

### RNF-IEX-005: A rota é um repasse

- O backend **NÃO DEVE** somar, converter, arredondar nem reclassificar nada do que vem do FedHub: `valor_meta` nulo chega nulo, decimais chegam como texto. A regra é do lake e o número tem um dono. `[D]` PA-024 (regra do número mora no lake, decisão do pacote do lake)
- Credencial do FedHub e do lake **NÃO DEVEM** aparecer neste repositório nem em log: a rota usa `get_headers()` e `FEDHUB_URL` do ambiente.
- Enquanto o contrato do financeiro não estiver publicado no servidor do lake, a produção **DEVE** responder `contrato_nao_publicado` e a página **DEVE** mostrar "dado do financeiro ainda não liberado no lake" — estado previsto, não defeito. `[E]` `FedHub-Backend/specs/lake-financeiro/design.md`, Divergência vs. produção

## Questões em Aberto

- PA-024 (fechada em 2026-09-23): origem do dado do painel de TV e autenticação — ver `specs/00-registro-de-questoes.md`.
