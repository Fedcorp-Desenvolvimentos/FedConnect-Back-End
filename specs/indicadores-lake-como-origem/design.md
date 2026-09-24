# Design — A tela Produção CORP lê o Data Lake CORP

> **Rastreabilidade** — RF: RF-IEX-011 · INV: INV-IEX-010 · ADR: ADR-0010 · Questões: PA-026
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana · **Atualizado:** 2026-09-23
> **Baseado em:** `requirements.md` (aprovado em 2026-09-23)

## Visão Geral da Solução

`agregacao.py` e `nao_fechadas.py` foram reescritos como **montadores**: cada seção pede ao FedHub as linhas já calculadas pelo lake (`fn_ind_*`) e monta o envelope que o front conhece. Nenhum número nasce aqui. As views só ganharam o tratamento de lake fora (503 nomeado). O espelho e suas cargas continuam no repositório como histórico; nenhuma leitura nova sai deles (ADR-0010).

## Arquitetura

```mermaid
flowchart LR
  FE[Produção CORP] -->|indicadores/* (JWT)| DJ[Django: views + agregacao/nao_fechadas]
  DJ -->|fedhub_lake.chamar → /api/lake/indicadores/*| FH[FedHub]
  FH -->|fn_ind_* SECURITY DEFINER| LK[(lake: vw_documento_indicador)]
  LK --> TV[vw_painel_tv]
```

| Arquivo | Mudança |
|---|---|
| `indicadores/services/agregacao.py` | reescrito: `_bloco_lake`, `totais`, `resumo`, `meta_mes`, `por_seguradora`, `serie`, `dominios`, `composicao` sobre as rotas do FedHub; `formatar_bloco` aceita as linhas do lake. |
| `indicadores/services/nao_fechadas.py` | reescrito: `calcular` lê `indicadores/nao-fechadas`; `Resultado` sobre dicionários; máscara de CPF continua aqui (apresentação). |
| `indicadores/views.py` | seis leituras traduzem `LakeIndisponivel` em 503. |
| `indicadores/fedhub_falso.py` | ganha as rotas `indicadores/*` calculadas com ORM sobre o banco de teste, regra do lake. |
| `indicadores/tests.py` | expectativas atualizadas para a regra do lake (documento 111 conta por vigência; valor fechado líquido; ALLI e PORT empatam em 5). |

## Modelo de Dados e Contratos

Sem migração. Contratos de resposta iguais a RF-IEX-002..008, com duas notas: `dominios.carga` passa a ser `{origem: "lake", concluida_em, rejeitos: {ausentes_na_origem}}` e `gerado_em` é a data/hora da última carga do lake.

Mapa seção → rota do FedHub → função do lake:

| Seção | Rotas | Função |
|---|---|---|
| resumo | `bloco` ×6, `totais`, metas | `fn_ind_bloco`, `fn_ind_totais` |
| por-seguradora | `por-seguradora`, `nao-fechadas`, `bloco` (total e pares com meta) | `fn_ind_por_seguradora`, `fn_ind_nao_fechadas`, `fn_ind_bloco` |
| serie | `serie?grao=dia|mes` | `fn_ind_serie` |
| dominios | `dominios`, `totais` | `fn_ind_dominios`, `fn_ind_totais` |
| nao-fechadas | `nao-fechadas` | `fn_ind_nao_fechadas` |
| composicao | `composicao`, `nao-fechadas` | `fn_ind_composicao`, `fn_ind_nao_fechadas` |

## Invariantes

| ID | Invariante | Garantido em |
|---|---|---|
| INV-IEX-010 | Nenhum número da tela é calculado neste repositório. | `agregacao.py`/`nao_fechadas.py` sem ORM; CT-IEX-020 (suíte inteira com FedHub falso) |
| INV-IEX-001 (mantida) | `fechados = renovacoes + captacoes` | agora no lake (`fn_ind_bloco`); testado em `PorSeguradoraTests` |

## Fluxo Principal

1. `GET indicadores/resumo/?...` → `FiltrosSerializer` valida → `agregacao.resumo` → `totais` + seis `bloco` + `meta_mes` (metas + um `bloco` por par com meta) → envelope.
2. `GET indicadores/nao-fechadas/` → `nao_fechadas.calcular` → uma rota → `Resultado.resposta()`.
3. Painel de TV lê `vw_painel_tv`, que soma o mesmo universo por seguradora × ramo: mesmo número.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| FedHub/lake fora | 503 `{sucesso: false, erro: lake_indisponivel|fedhub_indisponivel|contrato_nao_publicado|fedhub_sem_rota}` | RF-IEX-011 |
| Só metas fora | 200 com `meta: null`, `metas_indisponiveis: true` | RF-IEX-010 |
| Período sem documento | blocos vazios (`null` nas somas), como antes | RF-IEX-003 |
| Referência depois da última carga do lake | `dados_parciais: true` | RF-IEX-003 |

## Decisões

- ADR-0010: o lake é o dono do número; o espelho da ADR-0009 é aposentado como origem.
- Montagem aqui, cálculo lá: o envelope é contrato com o front (deste repositório); a regra é contrato do lake. Cada um muda no seu lugar.
- Realizado da meta por par (um `bloco` por seguradora × ramo com meta): é o mesmo número que o painel de TV mostra para o par, sem uma segunda soma.

## Divergência vs. produção

`[E]` 2026-09-23: o FedHub de produção ainda não tem as rotas `indicadores/*` nem `metas` (publicação de 24/09, junto com o pacote do lake); até lá a tela em produção responderia 503 `fedhub_sem_rota`. **Nada foi publicado nesta noite, por decisão da dona: teste local em 24/09 e só então produção.**

## Estratégia de Testes

| CT | Requisito | Caso |
|---|---|---|
| CT-IEX-020 | RNF-IEX-007 | a suíte inteira do app roda com o FedHub falso calculando `fn_ind_*` sobre o banco de teste |
| CT-IEX-021 | RF-IEX-011 | resumo/por-seguradora/série/domínios/composição/não fechadas com a regra do lake (`ResumoTests`, `PorSeguradoraTests`, `SerieTests`, `ComposicaoTests`, `NaoFechadasTests`) |
| CT-IEX-022 | RF-IEX-011 | lake inteiro fora → 503 nomeado nas leituras; só metas fora → degrada (`MetaComLakeForaTests`) |

Rodada de 2026-09-23: **78 testes OK**. Ponta a ponta local: os sete endpoints respondendo com o dado do lake (25.791 documentos, 9 ausentes na origem).

## Impacto e Riscos

- Sem migração; reverter é `git revert` de `agregacao.py`/`nao_fechadas.py`/`views.py`.
- Latência: 1,6–2,1 s no resumo pela travessia (sete chamadas). Mitigação prevista: `fn_ind_resumo` no lake.
- Os números da tela mudam para quem comparava com o relatório de emissão da CORP: agora batem com a grade por início de vigência (EVD-31 do lake). Comunicar ao gestor comercial.
