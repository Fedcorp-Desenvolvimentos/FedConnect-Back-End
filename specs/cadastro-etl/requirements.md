# Requisitos — Proxy do cadastro novo (`cadastro/*` → `/api/etl/*` do FedHub)

> **Rastreabilidade** — RF: RF-CAD-001..003 · RNF: RNF-CAD-001..003 · Questões: PA-027
> **Status:** em revisão · **Dono:** Daniel Mello · **Atualizado:** 2026-09-23 · **Implementado em 2026-09-23 por instrução do dono ("faça ele começar a consumir as rotas"); aprovação retroativa pendente**
> **Par:** `FedHub-Backend/specs/etl-cadastro-api/` (o contrato) · `FedConnect-FrontEnd/specs/cadastro-clientes/` fase 10 (a tela)

## Contexto e Problema

`[E]` O FedHub tem o módulo `etl`: API de cadastro e consulta sobre o banco PostgreSQL novo, 36 rotas sob `/api/etl`, contrato em `FedHub-Backend/specs/etl-cadastro-api/design.md` §Rotas; toda rota exceto `/health` exige o bearer com escopo, que este Django já obtém como cliente `fedconnect` (`consultas/utils/fedhub_auth.py`, `get_headers.py`). `[E]` A tela `CadastroClientes` do FedConnect roda sobre um dump em memória e não tem backend (`FedConnect-FrontEnd/specs/cadastro-clientes/requirements.md` RNF-CAD-001). `[E]` O frontend não chama o FedHub direto: todo service importa `src/services/api.js` (este Django). `[E]` O dono decidiu em 2026-09-23 que o caminho do cadastro é o mesmo dos outros proxies (frontend → Django → FedHub, com o Kong onde já está).

**Problema:** falta a ponte. Este documento especifica o proxy.

## Escopo

**Dentro do escopo:** rota `cadastro/<rota>` repassando `GET/POST/PUT/PATCH` a `/api/etl/<rota>`; autorização por nível; repasse de `Idempotency-Key` e `X-Request-Id`; 503 legível com o túnel fora; testes sem rede.

**Fora do escopo:** validar ou transformar corpo/resposta (é o FedHub que valida — ADR-0008); cache; qualquer rota do FedHub fora de `/api/etl`; a tela (spec do frontend); Kong (envs `FEDHUB_JWT_*` já existentes).

## User Stories e Critérios de Aceitação

### RF-CAD-001: Consultas do cadastro novo

**Como** operador do FedConnect, **quero** que as listas e detalhes do cadastro novo venham do banco novo pelo FedHub, **para** a tela deixar de usar o dump.

- **QUANDO** o frontend faz `GET cadastro/<rota>?<query>`, **ENTÃO** o sistema **DEVE** chamar `GET {FEDHUB_URL}/api/etl/<rota>?<query>` com `get_headers()` e devolver **o mesmo status e o mesmo corpo** do FedHub. `[D]` ADR-0008
- **QUANDO** o FedHub responde 404/422/409/503 em JSON, **ENTÃO** o sistema **DEVE** repassar status e corpo sem reescrever. `[D]` ADR-0008
- **QUANDO** a resposta do FedHub não é JSON (HTML do ngrok, 5xx do túnel) ou há timeout/erro de rede, **ENTÃO** o sistema **DEVE** responder 503 `{"erro": "servico_indisponivel", "mensagem": "...", "origem": "fedconnect"}` e registrar em log o status e os 300 primeiros caracteres. `[E]` padrão de `fedhub/services/envio_porto_service.py:33-46` · `[D]` ADR-0008

### RF-CAD-002: Cadastros

- **QUANDO** o frontend faz `POST/PUT/PATCH cadastro/<rota>` com corpo JSON, **ENTÃO** o sistema **DEVE** repassar método, corpo (bytes como vieram) e o header `Idempotency-Key`, se presente, e devolver status e corpo do FedHub (201/200/409/422). `[D]` ADR-0008
- **QUANDO** o cliente manda `X-Request-Id`, **ENTÃO** o sistema **DEVE** repassá-lo; senão **DEVE** gerar um uuid, mandá-lo ao FedHub e devolvê-lo no header da resposta. `[D]` ADR-0008
- **QUANDO** o método não é GET/POST/PUT/PATCH, **ENTÃO** 405. `[D]` ADR-0008

### RF-CAD-003: Autorização

- **QUANDO** a requisição não tem JWT válido, **ENTÃO** 401 (padrão DRF). `[E]` `bigcorp/settings.py:175-186`
- **QUANDO** o usuário autenticado não tem `nivel_acesso` em `NIVEIS_TELA`, **ENTÃO** 403 `{"erro": "sem_acesso", "mensagem": ...}` **sem** chamar o FedHub. `[P]` PA-027 (hoje só `admin`)
- **QUANDO** a chamada é repassada, **ENTÃO** o header `X-Operador` **DEVE** levar o e-mail do usuário autenticado (nunca do corpo). `[E]` mesmo princípio de `fedhub/views/fedpay_view.py` (operador vem do JWT)

## Requisitos Não Funcionais

### RNF-CAD-001: Resiliência
- Timeout explícito: 20 s em GET, 30 s em escrita; nenhuma chamada sem timeout. `[D]` ADR-0008 · `[E]` CLAUDE.md (incidente 14/08/2026)
- Túnel fora é rotina: 503 legível, nunca 500 com traceback. `[E]` CLAUDE.md:3

### RNF-CAD-002: Segurança
- Credenciais do FedHub só via env (`FEDHUB_URL`, `FEDHUB_X_API_KEY`, `FEDHUB_CLIENT_ID/SECRET`, `FEDHUB_JWT_*`), já existentes; nenhum header do cliente além de `Idempotency-Key` e `X-Request-Id` chega ao FedHub. `[E]` `consultas/utils/get_headers.py` · `[D]` ADR-0008
- Só o prefixo `/api/etl/` é alcançável; `rota` não pode conter `..` nem `//`. `[D]` ADR-0008

### RNF-CAD-003: Compatibilidade
- O corpo devolvido é o do FedHub; mudança de campo é mudança de contrato e vive em `FedHub-Backend/specs/etl-cadastro-api/`, não aqui. `[D]` ADR-0008
- Nenhuma view ou service existente muda; nada é criado no god-object `consultas/services/fedhub_service.py`. `[E]` CLAUDE.md

## Casos de teste (sem rede; `requests` mockado)
- CT-CAD-001 — GET repassa query, headers de auth, `X-Operador`, status e corpo. _(RF-CAD-001, RF-CAD-003)_
- CT-CAD-002 — 404/422/409 do FedHub repassados; HTML/5xx sem JSON → 503; timeout → 503. _(RF-CAD-001, RNF-CAD-001)_
- CT-CAD-003 — POST repassa corpo e `Idempotency-Key`; `X-Request-Id` gerado e devolvido; DELETE → 405. _(RF-CAD-002)_
- CT-CAD-004 — usuário `usuario` → 403 sem chamar o FedHub; `admin` passa; sem JWT → 401. _(RF-CAD-003, RNF-CAD-002)_
- CT-CAD-005 — `rota` com `..` → 400; timeouts 20/30 nas chamadas. _(RNF-CAD-001, RNF-CAD-002)_
- CT-CAD-006 — nenhum arquivo de `consultas/services/fedhub_service.py` no diff; rota registrada em `bigcorp/urls.py`. _(RNF-CAD-003)_

## Questões em Aberto
- PA-027 — `ti` acessa? — trava a tupla de RF-CAD-003
