# Design — Meta mensal gravada no Data Lake CORP

> **Rastreabilidade** — RF: RF-IEX-010 · INV: INV-IEX-007 (mantida), INV-IEX-009 · ADR: — · Questões: PA-025
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana · **Atualizado:** 2026-09-23
> **Baseado em:** `requirements.md` (aprovado em 2026-09-23)

## Visão Geral da Solução

`indicadores/services/metas.py` deixa de usar o ORM e vira cliente do FedHub, por `indicadores/services/fedhub_lake.py` (um único lugar para URL, headers, tempo limite e tradução de erro). As views não mudam de contrato; `agregacao.py` passa a receber as metas como lista de dicionários e a comparar com `preliq`. A tela e o front não sabem que a origem mudou.

## Arquitetura

```mermaid
flowchart LR
  FE[MetasModal / Produção CORP] -->|indicadores/metas/ (JWT)| DJ[Django: views + metas.py]
  DJ -->|fedhub_lake.chamar → /api/lake/metas| FH[FedHub]
  FH -->|lake_financeiro: INSERT/UPDATE/DELETE só em casa_meta_mensal| LK[(lake.casa_meta_mensal)]
  LK --> TV[vw_painel_tv / vw_meta_vs_realizado]
```

| Arquivo | Mudança |
|---|---|
| `indicadores/services/fedhub_lake.py` | novo: `chamar(metodo, caminho, params, json)`; 2xx → corpo; 4xx → `RecusaDoFedHub(status, detail)`; 5xx/timeout/conexão → `LakeIndisponivel(erro, detalhe)`. |
| `indicadores/services/metas.py` | `listar`, `gravar`, `atualizar`, `apagar`, `metas_da_competencia` sobre o FedHub; `serializar` garante o conjunto de chaves do front; exceções `MetaNaoEncontrada`, `MetaDuplicada`, `ReferenciaDesconhecida`. |
| `indicadores/views.py` | `MetasView`/`MetaDetalheView` passam sigla/abreviatura ao serviço e traduzem `LakeIndisponivel` em 503 (`_lake_fora`). |
| `indicadores/services/agregacao.py` | `_metas_do_mes` → lista do lake (ou `_MetasIndisponiveis`); `_so_pares_com_meta`, `_metas_por_seguradora` sobre dicionários; realizado da meta em `preliq`; `meta_mes.metas_indisponiveis`. |
| `indicadores/fedhub_falso.py` | FedHub em memória para a suíte; ligado em `_ComCarga.setUp`. |
| `indicadores/test_metas.py` | CT-IEX-009/010 reescritos sobre o FedHub falso; `MetaComLakeForaTests`. |

## Modelo de Dados e Contratos

Sem migração. `MetaMensal` permanece no banco como histórico e não é lida nem escrita. O contrato de `indicadores/metas/` é o de RF-IEX-008; `meta_mes` ganha `metas_indisponiveis: bool` (aditivo).

Corpo enviado ao FedHub: `{seguradora: <sigla>, ramo: <abreviatura>, competencia: "AAAA-MM", valor_meta: "0.00", replicar_meses, usuario: <nome ou e-mail>}`.

## Invariantes

| ID | Invariante | Garantido em |
|---|---|---|
| INV-IEX-007 | Uma meta por seguradora × ramo × competência. | agora no lake (`UNIQUE` em `casa_meta_mensal`) e no upsert do FedHub |
| INV-IEX-009 | Nenhuma leitura ou escrita de meta fora do FedHub. | `metas.py` sem ORM; teste de suíte com FedHub falso; `grep MetaMensal` |

## Fluxo Principal

1. Usuário grava a meta no modal → `POST indicadores/metas/` → serializer valida seguradora/ramo no espelho → `metas.gravar` → `fedhub_lake.chamar("POST", "metas")` → FedHub upsert em `casa_meta_mensal` → 201 com as linhas.
2. Resumo → `agregacao.meta_mes` → `metas_da_competencia` (uma chamada GET) → soma e pares com meta → realizado em `preliq` do espelho.
3. Painel de TV lê `vw_painel_tv`, que já junta `casa_meta_mensal`: `valor_meta` e `atingimento` aparecem sem código novo.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| FedHub/lake fora em `indicadores/metas/` | 503 `{sucesso: false, erro: lake_indisponivel|fedhub_indisponivel|contrato_nao_publicado}` | RF-IEX-010 |
| FedHub/lake fora no resumo/por-seguradora | 200; `meta: null`, `metas_indisponiveis: true`; realizado continua | RF-IEX-010 |
| Chave ocupada no PUT | 400 com a mensagem do FedHub | RF-IEX-010 |
| Id inexistente (PUT/DELETE) | 404 | RF-IEX-010 |
| Seguradora/ramo fora do lake | 400 `referencia_desconhecida` | RF-IEX-010 |

## Decisões

- Proxy, não sincronização: uma cópia local da meta recriaria o problema que a decisão resolve (dois donos).
- Realizado da meta em `preliq` já nesta spec, e não só quando a tela inteira ler o lake: a meta é comparada no painel de TV em líquido; ter a mesma meta comparada em total no resumo daria dois atingimentos para a mesma meta na mesma noite.
- Degradar em vez de falhar quando o lake não responde: o resumo tem oito números; um deles ausente não justifica perder os outros sete.

## Divergência vs. produção

`[E]` 2026-09-23: o FedHub de produção ainda não tem as rotas de metas (código nos clones locais, a publicar amanhã junto com o pacote do lake); até lá o FedHub de produção responde 404 "Not Found" para `/api/lake/metas`, que `fedhub_lake` traduz em 503 `fedhub_sem_rota` — a tela diz "FedHub sem a rota", não "meta inválida". Pendência de publicação, não defeito.

## Estratégia de Testes

| CT | Requisito | Caso |
|---|---|---|
| CT-IEX-016 | RF-IEX-010 | POST/GET/PUT/DELETE mantêm o contrato do front sobre o FedHub falso (CT-IEX-009 reescrito) |
| CT-IEX-017 | RF-IEX-010 | `meta_mes` soma metas do lake e compara com `preliq` (CT-IEX-010 reescrito) |
| CT-IEX-018 | RF-IEX-010 | lake fora: metas 503 nomeado; resumo e por-seguradora 200 sem meta, avisado |
| CT-IEX-019 | RNF-IEX-006 | toda a suíte do app roda com o FedHub falso; nenhuma chamada real |

`indicadores/test_metas.py` e `indicadores/tests.py`. Rodada de 2026-09-23: 74 testes OK.

## Impacto e Riscos

- Sem migração; reverter é voltar `metas.py`/`agregacao.py` do git.
- As metas já digitadas em `MetaMensal` não migram sozinhas — precisam ser recadastradas na tela (poucas, de setembro).
- Depende do FedHub de produção receber o módulo com as rotas de metas.
