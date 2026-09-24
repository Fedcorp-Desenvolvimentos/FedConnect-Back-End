# Requisitos — Meta mensal gravada no Data Lake CORP

> **Rastreabilidade** — RF: RF-IEX-010 · RNF: RNF-IEX-006 · Questões: PA-025
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana (arquitetura de dados), a pedido da gestão · **Atualizado:** 2026-09-23
> **Lado FedHub:** `FedHub-Backend/specs/lake-financeiro/` (RF-LAK-005, rotas `/api/lake/metas`). **Lado lake:** tabela `casa_meta_mensal` e views `vw_painel_tv`, `vw_meta_vs_realizado`. **Lado frontend:** sem mudança — o contrato de `indicadores/metas/` é o mesmo.

<!-- Contexto IEX (CONVENCOES §2.1); IDs continuam de RF-IEX-009. -->

## Contexto e Problema

`[E]` Até 23/09/2026 a meta mensal (RF-IEX-008) era gravada em `MetaMensal`, no banco do FedConnect, e o realizado do painel de TV era calculado no lake: o painel mostrava `valor_meta` nulo e o atingimento não existia (medição de 23/09/2026 em `vw_painel_tv`). `[D]` PA-025: a gestão decidiu "gravar a meta no lake" — meta e realizado no mesmo lugar, comparação com um dono só. `[E]` O lake já tinha `casa_meta_mensal` (a única tabela em que o consumidor escreve) e o FedHub ganhou `GET/POST /api/lake/metas` e `PUT/DELETE /api/lake/metas/{id}` com o mesmo corpo e a mesma resposta que esta API expõe ao front.

## Escopo

**Dentro do escopo:**
- `indicadores/metas/` (GET/POST) e `indicadores/metas/<id>/` (PUT/DELETE) passam a ser proxy das rotas do FedHub, mantendo o contrato do front.
- `meta_mes` do resumo e as colunas de meta do por-seguradora leem as metas do lake (via FedHub) e comparam com o **prêmio líquido** do mês.
- Lake fora não derruba a tela: a meta some, avisada.

**Fora do escopo:**
- Migrar as metas já gravadas em `MetaMensal` (o modelo fica como histórico; a gestão recadastra as metas vigentes na tela).
- Mover o restante da tela Produção CORP para o lake (spec própria: `indicadores-lake-como-origem`).

## User Stories e Critérios de Aceitação

### RF-IEX-010: Meta no lake, tela igual

**Como** gestor comercial, **quero** cadastrar a meta na mesma tela de sempre e vê-la no painel de TV e no resumo, **para** que os dois mostrem o mesmo número.

- **QUANDO** `POST indicadores/metas/` recebe `{seguradora, ramo, competencia, valor_meta, replicar_meses?}` válido, **ENTÃO** o sistema **DEVE** chamar `POST /api/lake/metas` do FedHub com a sigla da seguradora, a abreviatura do ramo e quem digitou (`usuario`), e devolver 201 com `metas[]` no contrato de RF-IEX-008 (`id, seguradora, seguradora_nome, ramo, ramo_nome, competencia, valor_meta, atualizado_em, atualizado_por`). `[E]` `indicadores/services/metas.py`, `serializar`
- **QUANDO** `GET indicadores/metas/?competencia=AAAA-MM`, **ENTÃO** `{competencia, metas[], total_meta}` vem do FedHub; sem `competencia`, o mês corrente local.
- **QUANDO** `PUT indicadores/metas/<id>/`, **ENTÃO** edita esta meta (inclusive a chave) via FedHub; chave ocupada → 400 com a mensagem; id inexistente → 404. **QUANDO** `DELETE`, **ENTÃO** 200 `{sucesso: true}` ou 404.
- **QUANDO** seguradora ou ramo não existem no espelho, **ENTÃO** 400 (validação local, como antes); **SE** existem no espelho e não no lake, **ENTÃO** 400 com o texto do FedHub (`referencia_desconhecida`).
- **QUANDO** o resumo calcula `meta_mes`, **ENTÃO** `meta` é a soma das metas do lake para a competência (respeitando o filtro de ramos/seguradoras), e `realizado` é a soma do **prêmio líquido** (`preliq`) do mês, dos pares seguradora × ramo com meta. `[D]` PA-025 (prêmio líquido, como o lake). O por-seguradora segue a mesma regra por linha.
- **SE** o FedHub ou o lake não respondem, **ENTÃO** `indicadores/metas/` responde 503 `{sucesso: false, erro: <nomeado>}`, e o resumo/por-seguradora respondem 200 com `meta: null` e `meta_mes.metas_indisponiveis: true`. `[E]` `agregacao._MetasIndisponiveis`

## Requisitos Não Funcionais

### RNF-IEX-006: Nenhum segundo dono da meta

- Nenhuma leitura ou escrita nova em `MetaMensal`; toda meta passa pelo FedHub. `[E]` `grep MetaMensal indicadores/services indicadores/views.py` em 2026-09-23: só o modelo e o admin.
- A suíte nunca fala com o FedHub real: `indicadores/fedhub_falso.py` implementa as quatro rotas em memória e `_ComCarga` o liga em todo teste.

## Questões em Aberto

- PA-025 (fechada em 2026-09-23): onde a meta é gravada e contra o quê é comparada.
