# ADR-0008 — Proxy transparente por prefixo para `/api/etl/*` do FedHub (sem envelope `{sucesso}`)

> **Status:** decidido · **Dono:** Daniel Mello · **Data:** 2026-09-23
> **Pode ser adiada:** sim (atrás de `CadastroService`); mas cada rota nova do FedHub exigiria uma view aqui se a decisão fosse a contrária
> **Contexto(s):** `CAD` · **Specs:** `specs/cadastro-etl/`, `FedHub-Backend/specs/etl-cadastro-api/`

## Contexto

O FedHub ganhou o módulo `etl` com 36 rotas sob `/api/etl` (spec `FedHub-Backend/specs/etl-cadastro-api/`), cujo contrato de campos é o que a tela `CadastroClientes` do FedConnect já consome (decisão 0042 do FedHub). O frontend não fala com o FedHub direto: passa por este Django, que já sabe autenticar no FedHub (`consultas/utils/get_headers.py`: bearer do cliente `fedconnect` + chave legada + JWT do Kong). Os proxies existentes (`fedpay_service.py`, `envio_porto_service.py`) têm uma view por rota e envelopam a resposta em `{"sucesso", "resultado"|"erro"}`. Aqui são 36 rotas com formato já definido e um frontend que espera esse formato tal qual.

## Decisão

1. **Uma rota curinga** `cadastro/<path:rota>` em `bigcorp/urls.py` repassa `GET/POST/PUT/PATCH` para `{FEDHUB_URL}/api/etl/<rota>`, com a query string e o corpo JSON como vieram.
2. **Sem envelope**: status HTTP e corpo do FedHub voltam como estão (`{linhas,total,...}`, `{"erro","mensagem",...}`). Quando o FedHub não responde JSON (túnel fora, 5xx do ngrok) ou há erro de rede/timeout, o proxy responde **503 no formato de erro do FedHub** — `{"erro": "servico_indisponivel", "mensagem": ..., "origem": "fedconnect"}` — para o frontend tratar um único shape.
3. **Headers repassados** ao FedHub: só `Idempotency-Key` (dos POSTs de cadastro) e `X-Request-Id` (o do cliente, ou um uuid gerado aqui, também devolvido na resposta). Nada mais do cliente chega ao FedHub; as credenciais são só as de `get_headers()`.
4. **Timeouts** por método, justificados pelas medições do FedHub em 2026-09-23 (`FedHub-Backend/specs/etl-cadastro-api/lacunas.md`): `GET` 20 s (lista de condomínios mede 1,9 s; histórico da maior administradora 1,1 s; folga para ngrok), escrita 30 s (uma transação, sem chamada a banco emissor). Nunca sem timeout (incidente de 14/08/2026).
5. **Autorização**: JWT + `IsAuthenticated` + nível em `NIVEIS_TELA` (hoje `("admin",)`, PA-027); 403 no formato `{"erro": "sem_acesso", "mensagem": ...}`. O FedHub não conhece o usuário final: o e-mail do operador vai no header `X-Operador` para o log do FedHub (trilha de leitura de funcionário, decisão 0043 do FedHub).
6. **Lista branca de métodos**: qualquer outro método responde 405. Nenhum caminho fora de `/api/etl/` é alcançável por esta rota (o prefixo é fixo no service).

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Rota curinga transparente, sem envelope | baixo | **Escolhida.** Zero duplicação de contrato; o formato mora na spec do FedHub; frontend troca só a fonte |
| Uma view por rota com `{sucesso, resultado}` | médio — 36 views + service espelhando o FedHub | Padrão dos proxies atuais, mas o frontend teria que desembrulhar e cada rota nova do FedHub viraria mudança aqui |
| Frontend direto no FedHub via Kong | — | Descartado pelo dono em 2026-09-23 (caminho é o mesmo dos outros proxies) |

## Consequências

- Rota nova no FedHub sob `/api/etl` fica disponível ao frontend sem deploy do Django — e sem revisão aqui: a autorização por nível cobre o prefixo inteiro, não rota a rota.
- O formato de erro que o frontend trata é o do FedHub (`{"erro","mensagem"}`), diferente do `{"sucesso": false, "erro"}` das outras telas; a spec do frontend registra isso.
- O Django não valida corpo: quem valida é o FedHub (422 com `campos`).
