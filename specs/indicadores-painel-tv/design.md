# Design — Painel de TV alimentado pelo Data Lake CORP (via FedHub)

> **Rastreabilidade** — RF: RF-IEX-009 · INV: INV-IEX-005, INV-IEX-006 · ADR: — · Questões: PA-024
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana · **Atualizado:** 2026-09-23
> **Baseado em:** `requirements.md` (aprovado em 2026-09-23)

## Visão Geral da Solução

Uma view DRF autenticada por JWT (`PainelTvView`) chama o FedHub em `/api/lake/painel-tv` com os headers que o repositório já usa para o FedHub e devolve as linhas como vieram. A página `public/tv/painel.html` deixa de ter dados fixos e passa a buscar essa rota com o token do `localStorage` (mesma origem do app), agrupando por seguradora no navegador. Nada muda no espelho, nos modelos nem nas migrações.

## Arquitetura

```mermaid
flowchart LR
  TV[painel.html<br/>mesma origem do app] -->|GET indicadores/painel-tv/<br/>JWT do usuário| FC[FedConnect Django]
  FC -->|GET /api/lake/painel-tv<br/>get_headers()| FH[FedHub]
  FH -->|lake_financeiro, somente leitura| LK[(lake.vw_painel_tv)]
```

| Arquivo | Mudança |
|---|---|
| `indicadores/services/painel_tv.py` | `linhas()`: uma chamada HTTP ao FedHub, `timeout` 15 s; 503 do FedHub vira `LakeIndisponivel(erro, detalhe)`. |
| `indicadores/views.py` | `PainelTvView(_IndicadorBase)`: JWT obrigatório; 200 com `{sucesso, gerado_em, linhas}`; 503 nomeado. |
| `bigcorp/urls.py` | `indicadores/painel-tv/`. |
| `indicadores/test_painel_tv.py` | CT-IEX-011..015. |
| Front `public/tv/painel.html` | `EXEMPLO` sai; `carregar()` busca a rota, `agrupar()` monta o formato que a tela já usava; recarga a cada 10 min; avisos por estado. |
| Front `IndicadoresHome.jsx` | o card passa `?api=<baseURL>` porque a página estática não enxerga `import.meta.env`. |

## Modelo de Dados e Contratos

Sem modelo novo. Resposta de `GET indicadores/painel-tv/`:

```json
{"sucesso": true, "gerado_em": "2026-09-23T20:34:20+00:00",
 "linhas": [{"seguradora_sigla": "ALLI", "seguradora_nome": "ALLIANZ SEGUROS", "codram": 4, "ramo_sigla": "COND",
             "ramo_nome": "CONDOMINIO", "mes_atual": "2026-09-01", "mes_anterior": "2025-09-01",
             "valor_atual": "819768.8700", "valor_anterior": "690450.0000", "apolices_atual": "211",
             "apolices_anterior": "180", "valor_meta": null, "variacao_percentual": "18.7", "atingimento": null}]}
```

As colunas são contrato do lake (`vw_painel_tv`); por isso a rota não tem serializer por campo — coluna nova lá chega aqui sem mudança.

Erro (503): `{"sucesso": false, "erro": "lake_nao_configurado|lake_indisponivel|contrato_nao_publicado|fedhub_indisponivel", "detalhe": "..."}`.

## Invariantes

| ID | Invariante | Garantido em |
|---|---|---|
| INV-IEX-005 | A rota devolve o que o FedHub devolve; nenhuma aritmética no backend. | `painel_tv.py` e a view não tocam nos valores (CT-IEX-012) |
| INV-IEX-006 | Nenhuma chamada ao FedHub sem usuário autenticado. | `_IndicadorBase` (`JWTAuthentication` + `IsAuthenticated`) antes de `linhas()` (CT-IEX-011) |

## Fluxo Principal

1. Usuário logado abre o card "Painel de TV"; a home abre `/tv/painel.html?api=<baseURL>` em aba nova.
2. A página lê `accessToken` do `localStorage` (mesma origem) e chama `GET <api>indicadores/painel-tv/`.
3. A view chama `painel_tv.linhas()` → FedHub `/api/lake/painel-tv` → lake `vw_painel_tv`.
4. A página agrupa por seguradora, monta faixa, tabela e ticker; rotaciona seguradoras a cada 12 s; recarrega a cada 10 min. Botões ◀ ❚❚ ▶ no rodapé, setas ← → e espaço, e os pontos clicáveis permitem voltar, avançar e pausar; troca manual reinicia a contagem dos 12 s.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| Sem JWT / expirado | 401; a página mostra "Sessão expirada — entre no FedConnect e abra o painel de novo" | RF-IEX-009 |
| FedHub 503 | 503 com o `erro` do FedHub; a página traduz cada um em uma frase | RF-IEX-009, RNF-IEX-005 |
| FedHub fora / timeout 15 s | 503 `fedhub_indisponivel` | RF-IEX-009 |
| Nenhuma linha com valor | página mostra "Nenhuma seguradora com produção no período" | RF-IEX-009 |
| Meta ausente | `valor_meta` nulo → coluna "—" e "sem meta cadastrada"; nada vira zero | RNF-IEX-005 |

## Decisões

- Sem ADR nova. Repasse em vez de agregação local segue a decisão do pacote do lake de que a classificação mora lá; usar o FedHub como caminho segue a spec `lake-financeiro` do FedHub. A alternativa "ler o espelho local" foi descartada porque o espelho não tem meta por ramo nem a comparação por mês de vigência — e teria dois donos para o mesmo número.
- A lista de seguradoras exibidas fica na página (`SEGURADORAS_EXIBIDAS`), não no lake nem na rota: o lake serve a carteira inteira a qualquer consumidor; o que vai para a TV do setor é escolha de exibição, e trocar uma seguradora não pode exigir publicação de view.
- `?api=` na URL da página estática: a única forma de uma página fora do bundle saber o endereço do Django sem duplicar a configuração do Vite.

## Divergência vs. produção

`[E]` 2026-09-23: em produção o FedHub ainda não tem cliente com escopo `/api/lake` em `AUTH_CLIENTS`, e o servidor do lake não tem o contrato do financeiro publicado (sequenciado pela gestão depois do TLS). Até lá a rota responde 503 `contrato_nao_publicado` — previsto. Verificado localmente de ponta a ponta (página → Django 8002 → FedHub 8000 → cópia de trabalho do lake): 45 linhas, ALLI R$ 829 mil no mês.

## Estratégia de Testes

| CT | Requisito | Caso |
|---|---|---|
| CT-IEX-011 | RF-IEX-009 | sem login → 401 |
| CT-IEX-012 | RF-IEX-009, RNF-IEX-005 | repassa as linhas do FedHub; `valor_meta` nulo continua nulo |
| CT-IEX-013 | RF-IEX-009 | FedHub 503 `contrato_nao_publicado` → 503 com o mesmo `erro` |
| CT-IEX-014 | RF-IEX-009 | FedHub fora → 503 `fedhub_indisponivel` |
| CT-IEX-015 | RF-IEX-009 | o serviço traduz o 503 do FedHub em `LakeIndisponivel` com o `erro` dele |

`indicadores/test_painel_tv.py`, FedHub substituído por `patch`. Rodada em 2026-09-23: 5 testes OK.

## Impacto e Riscos

- Sem migração, sem mudança em rota existente; reverter é remover a URL e voltar o `painel.html` do git.
- A página depende do `accessToken` no `localStorage` da mesma origem: se o app mudar onde guarda o token, o painel perde o dado (mostra "Sessão expirada").
- Cadência de 10 min na página × 10 min no lake: no pior caso o número tem 20 min de idade. Aceito pelo dono para um monitor de setor.
