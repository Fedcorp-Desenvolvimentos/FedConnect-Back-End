# Design — Proxy do cadastro novo (`cadastro/*` → `/api/etl/*`)

> **Rastreabilidade** — RF: RF-CAD-001..003 · RNF: RNF-CAD-001..003 · INV: INV-CAD-001..003 · ADR: ADR-0008 · Questões: PA-014
> **Status:** em revisão · **Dono:** Daniel Mello · **Atualizado:** 2026-09-23 · **Implementado junto (instrução do dono); aprovação retroativa pendente**
> **Baseado em:** `requirements.md` (em revisão, 2026-09-23)

## Visão Geral da Solução

Um service (`CadastroService`) com um único método `repassar(metodo, rota, params, corpo, headers_extra)` que monta `{FEDHUB_URL}/api/etl/<rota>`, chama com `requests` e `get_headers()`, e devolve `{"http_status", "body", "headers"}`; uma view (`CadastroProxyView`) que autentica por JWT, checa o nível, injeta `X-Operador` e `X-Request-Id`, repassa `Idempotency-Key` e devolve a resposta tal qual (ADR-0008). Uma linha em `bigcorp/urls.py`.

## Arquitetura

| Arquivo | Mudança |
|---|---|
| `fedhub/services/cadastro_service.py` (novo) | `CadastroService.repassar(...)`; `TIMEOUT_LEITURA = 20`, `TIMEOUT_ESCRITA = 30`; `_resposta()` normaliza não-JSON em 503 no formato do FedHub |
| `fedhub/views/cadastro_view.py` (novo) | `CadastroProxyView(APIView)`: `JWTAuthentication`, `IsAuthenticated`, `NIVEIS_TELA = ("admin",)`, métodos `get/post/put/patch`, 405 para o resto, validação de `rota` |
| `bigcorp/urls.py` | `path("cadastro/<path:rota>", CadastroProxyView.as_view(), name="cadastro-etl")` num bloco `# CADASTRO NOVO (proxy /api/etl do FedHub) *******` |
| `fedhub/test_cadastro_proxy.py` (novo) | unittest com `requests` mockado e `APIRequestFactory` + `force_authenticate` com usuário falso (sem banco) |
| `specs/CONVENCOES.md` | contexto `CAD` |

## Contratos de API

Rota: `cadastro/<rota>` — `rota` é o caminho relativo a `/api/etl/` do FedHub, com a mesma query string. Corpo e resposta: os do FedHub (`FedHub-Backend/specs/etl-cadastro-api/design.md` §Rotas e decisão 0042 do FedHub). Erros próprios deste proxy, no mesmo formato do FedHub:

| Situação | Status | Corpo |
|---|---|---|
| sem nível | 403 | `{"erro": "sem_acesso", "mensagem": "Seu nível de acesso não permite usar o cadastro."}` |
| método fora da lista | 405 | `{"erro": "metodo_nao_permitido", "mensagem": ...}` |
| rota inválida (`..`, `//`, vazia) | 400 | `{"erro": "rota_invalida", "mensagem": ...}` |
| FedHub sem JSON / rede / timeout | 503 | `{"erro": "servico_indisponivel", "mensagem": "FedHub indisponível no momento — tente novamente em instantes.", "origem": "fedconnect"}` |

Headers que saem ao FedHub: `get_headers()` + `X-Operador: <email>` + `X-Request-Id` + `Idempotency-Key` (se veio). Headers que voltam ao cliente: `X-Request-Id`, e `Idempotent-Replayed` quando o FedHub o mandar.

## Invariantes

| ID | Invariante | Garantido em |
|---|---|---|
| INV-CAD-001 | Nenhuma requisição chega ao FedHub sem passar por JWT válido e nível em `NIVEIS_TELA`. | view (checagem antes de instanciar o service) |
| INV-CAD-002 | Toda chamada ao FedHub tem timeout (20 s leitura, 30 s escrita). | service (constantes; teste confere o argumento) |
| INV-CAD-003 | O caminho chamado começa sempre por `{FEDHUB_URL}/api/etl/`; `rota` sem `..`, `//` ou vazio. | view (validação) + service (prefixo fixo) |

## Fluxo Principal

1. `GET /cadastro/administradoras?busca=bbz` → JWT → nível → `rota = "administradoras"` → service `GET {FEDHUB_URL}/api/etl/administradoras?busca=bbz` (timeout 20) → 200 JSON → `Response(body, status=200, headers={X-Request-Id})`.
2. `POST /cadastro/administradoras` com `Idempotency-Key` → idem, corpo em bytes como veio, timeout 30 → 201/409/422 repassados; `Idempotent-Replayed` repassado se vier.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| FedHub indisponível (timeout/5xx do túnel/HTML) | 503 formato FedHub, log com status e 300 chars | RF-CAD-001, RNF-CAD-001 |
| FedHub 4xx JSON | repassado | RF-CAD-001 |
| corpo não JSON no POST | repassado como veio; o FedHub responde 400 `json_invalido` | RF-CAD-002 |
| usuário sem nível | 403 sem chamar o FedHub | RF-CAD-003 |
| `rota` com `..` | 400 | RNF-CAD-002 |

## Decisões
- ADR-0008: proxy transparente por prefixo, sem envelope

## Divergência vs. produção
- Os outros proxies do FedHub aqui envelopam em `{sucesso, resultado|erro}` (`fedhub/views/envio_porto_view.py:40-49`); este não (ADR-0008). Não há duplicata em `consultas/`: esta view existe só em `fedhub/`, e é a que `bigcorp/urls.py` importa.
- `fedhub` não está em `INSTALLED_APPS`; os testes deste proxy rodam com `python -m unittest fedhub.test_cadastro_proxy` (sem banco), como `fedhub/test_segunda_via_service.py`.

## Estratégia de Verificação

| CT | Requisito | Caso |
|---|---|---|
| CT-CAD-001 | RF-CAD-001, RF-CAD-003 | GET repassa query, `X-Operador`, `X-Request-Id`, status e corpo |
| CT-CAD-002 | RF-CAD-001, RNF-CAD-001 | 404/422/409 repassados; HTML → 503; `Timeout` → 503 |
| CT-CAD-003 | RF-CAD-002 | POST repassa bytes e `Idempotency-Key`; `X-Request-Id` gerado; `Idempotent-Replayed` repassado; DELETE 405 |
| CT-CAD-004 | RF-CAD-003, RNF-CAD-002 | `usuario` → 403 e `requests` não chamado; `admin` passa; anônimo → 401 |
| CT-CAD-005 | RNF-CAD-001, RNF-CAD-002 | `..` → 400; `timeout=20` em GET e `30` em POST |
| CT-CAD-006 | RNF-CAD-003 | rota em `bigcorp/urls.py`; god-object intocado |

## Impacto e Riscos
- Deploy: sem env nova (o cliente `fedconnect` já existe no FedHub com escopo `*`); só código. Rollback: remover a linha de `urls.py`.
- Nível só `admin` até PA-014.
- Cada GET de lista de condomínios segura um worker por até ~2 s (medição do FedHub); 20 s de timeout limita o dano de um túnel lento.
