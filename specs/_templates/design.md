# Design — [Nome da Feature]

> **Rastreabilidade** — RF: RF-XXX-001.. · INV: INV-XXX-001.. · ADR: ADR-#### · Questões: PA-###
> **Status:** esboço · **Dono:** · **Atualizado:** AAAA-MM-DD
> **Baseado em:** `requirements.md` (aprovado em AAAA-MM-DD)

## Visão Geral da Solução

<!-- 1 parágrafo em prosa. Cite RF/ADR por ID; não repita descrições. -->

## Arquitetura

<!-- Diagrama mermaid se ajudar. ATENÇÃO: views/services duplicados entre consultas/ e
     fedhub/ — identifique o ATIVO em bigcorp/urls.py e o destino da duplicata. -->

| Arquivo/App | Mudança |
|---|---|
| `consultas/...` ou `fedhub/...` | |

## Modelo de Dados e Contratos

<!-- Modelos Django tocados + migração; contratos de payload (request/response do
     endpoint, payload ao FedHub). Se nada muda, dizer explicitamente. -->

## Invariantes

| ID | Invariante | Garantido em |
|---|---|---|
| INV-XXX-001 | | banco / aplicação / processo |

## Fluxo Principal

<!-- Passo a passo do caminho feliz, incluindo o salto para o FedHub quando houver. -->

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| FedHub indisponível (timeout/5xx do túnel) | | RNF-XXX-00n |
| Payload inválido do frontend | | RF-XXX-00n |
| Chamada duplicada (idempotência) | | RF-XXX-00n |

## Decisões

- ADR-####: [título]

## Divergência vs. produção

<!-- Obrigatória, mesmo que "nenhuma divergência conhecida". -->

## Estratégia de Testes

<!-- Cada caso ganha CT-XXX-### (referenciado na matriz.csv). Django TestCase/APIClient. -->

| CT | Requisito | Caso |
|---|---|---|
| CT-XXX-001 | RF-XXX-001 | |

## Impacto e Riscos

<!-- Migração? Deploy coordenado com frontend/FedHub? Rollback? -->
