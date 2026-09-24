# Requisitos — A tela Produção CORP lê o Data Lake CORP

> **Rastreabilidade** — RF: RF-IEX-011 · RNF: RNF-IEX-007 · Questões: PA-026
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana (arquitetura de dados), a pedido da gestão; tela do gestor comercial via Lucas Guidi · **Atualizado:** 2026-09-23
> **Lado FedHub:** `FedHub-Backend/specs/lake-financeiro/` (RF-LAK-006, rotas `/api/lake/indicadores/*`). **Lado lake:** `vw_documento_indicador` e funções `fn_ind_*` do contrato do financeiro. **Lado frontend:** sem mudança — os sete endpoints mantêm o contrato.

<!-- Contexto IEX; IDs continuam de RF-IEX-010. Reverte a decisão de origem da ADR-0009 (ADR-0010). -->

## Contexto e Problema

`[E]` Em 23/09/2026, com a meta já no lake, a mesma meta Allianz × condomínio tinha **dois atingimentos**: 38,5 % no resumo (espelho local, corte por data de emissão) e 69,8 % no painel de TV (lake, corte por início de vigência) — medição de ponta a ponta na estação. `[D]` PA-026: a gestão decidiu "vamos manter o que está no lake": o lake é o dono do número, e a tela Produção CORP passa a lê-lo. `[E]` O lake publicou `vw_documento_indicador` e as funções `fn_ind_bloco`, `fn_ind_por_seguradora`, `fn_ind_serie`, `fn_ind_dominios`, `fn_ind_totais`, `fn_ind_nao_fechadas` e `fn_ind_composicao`, com os parâmetros desta tela, e o FedHub as repassa em `/api/lake/indicadores/*`.

## Escopo

**Dentro do escopo:**
- Os sete endpoints (`dominios`, `resumo`, `por-seguradora`, `serie`, `nao-fechadas`, `composicao`, `metas`) respondem com dado do lake, no mesmo contrato de RF-IEX-002..008.
- Regra do lake: corte por **início de vigência**, `valor_fechado` = **prêmio líquido**, renovação pela regra da casa, documento que a CORP apagou fora.
- Lake fora → 503 nomeado em toda leitura (não há mais número local).

**Fora do escopo:**
- Apagar o espelho (`Producao`, `Documento`, `Cliente`…) e suas cargas: ficam como histórico até a ADR-0010 ser cumprida com migração própria.
- Mudar o front.

## User Stories e Critérios de Aceitação

### RF-IEX-011: Um dono para o número

**Como** gestor comercial, **quero** que o resumo, o por-seguradora, as séries, as não fechadas, a composição e o painel de TV mostrem **o mesmo número** para o mesmo recorte, **para** não ter duas respostas para a mesma pergunta.

- **QUANDO** qualquer dos endpoints de leitura é chamado com os parâmetros de RF-IEX-003, **ENTÃO** o sistema **DEVE** montar a resposta a partir de `/api/lake/indicadores/*` do FedHub, sem somar, converter ou reclassificar nada localmente; os filtros (`ramo`, `seguradora`, `incluir_cancelados`, `todos_tipdoc`, janela) **DEVEM** ir como parâmetros das funções do lake. `[E]` `agregacao.py`, `nao_fechadas.py`
- **QUANDO** o resumo calcula `atual`, `anterior` e `periodos`, **ENTÃO** cada bloco **DEVE** ser um `fn_ind_bloco` do lake com a janela correspondente; `valor_fechado` é o prêmio líquido. `[D]` PA-026
- **QUANDO** o mesmo recorte é pedido ao painel de TV (`vw_painel_tv`) e ao resumo (mês corrente), **ENTÃO** os dois **DEVEM** dar o mesmo valor. `[E]` medição de 23/09/2026: Allianz × condomínio, setembro — 218 / R$ 837.800,27 nos dois.
- **QUANDO** `dominios` é chamado, **ENTÃO** `extraido_em`, `total_documentos`, `documentos_sem_datemi` e `carga` **DEVEM** vir de `fn_ind_totais` (`carga.origem = "lake"`, `carga.rejeitos.ausentes_na_origem`).
- **SE** o FedHub ou o lake não respondem, **ENTÃO** as leituras **DEVEM** responder 503 `{sucesso: false, erro: <nomeado>}`; **SE** só as metas falham, **ENTÃO** o resumo e o por-seguradora **DEVEM** responder 200 com `meta: null` e `metas_indisponiveis: true` (RF-IEX-010).

## Requisitos Não Funcionais

### RNF-IEX-007: Nenhuma agregação local

- `agregacao.py` e `nao_fechadas.py` **NÃO DEVEM** consultar `Producao`/`Documento`; a suíte prova o contrato com um FedHub em memória que calcula as mesmas funções sobre o banco de teste (`fedhub_falso.py`), com a regra do lake escrita duas vezes para ter de bater. `[E]` 78 testes OK em 2026-09-23
- Tempo: um `resumo` faz sete chamadas ao FedHub (seis blocos + metas); medido em 1,6–2,1 s na estação pela travessia local. Aceito para uma tela de gestão; se incomodar, o lake ganha `fn_ind_resumo` devolvendo os seis blocos numa chamada.

## Questões em Aberto

- PA-026 (fechada em 2026-09-23): quem é o dono do número da tela Produção CORP.
