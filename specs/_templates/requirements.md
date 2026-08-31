# Requisitos — [Nome da Feature]

> **Rastreabilidade** — RF: RF-XXX-001.. · RNF: RNF-XXX-001.. · Questões: PA-###
> **Status:** esboço · **Dono:** · **Atualizado:** AAAA-MM-DD

<!-- Convenções em specs/CONVENCOES.md. <CTX> da tabela §2.1; IDs nunca reciclados.
     Todo enunciado relevante carrega [E] (com arquivo:linha ou verificação datada),
     [D] (com ADR-####) ou [P] (com PA-###). Enunciado sem marca = [P] na revisão. -->

## Contexto e Problema

<!-- 2-4 frases. Fatos verificados entram com [E]; hipóteses com [P] e a PA aberta. -->

## Escopo

**Dentro do escopo:**
-

**Fora do escopo:** <!-- tão importante quanto o que entra -->
-

## User Stories e Critérios de Aceitação

### RF-XXX-001: [Título da story]

**Como** [ator], **quero** [ação], **para** [benefício].

Critérios (formato EARS — cada um testável):

- **QUANDO** [evento/condição], **ENTÃO** o sistema **DEVE** [comportamento].
- **SE** [condição de erro], **ENTÃO** o sistema **DEVE** [comportamento de falha].
- **ENQUANTO** [estado], o sistema **DEVE** [invariante].

### RF-XXX-002: ...

## Requisitos Não Funcionais

<!-- Verificáveis — número, condição ou invariante; nada de "deve ser performático".
     Todo RNF deste projeto considera: segurança (JWT/permissões, segredo via env),
     compatibilidade (contrato com o frontend e com o FedHub), resiliência
     (FedHub indisponível é rotina; timeout explícito para não esgotar workers)
     e desempenho (paginação; sem N+1; sem listas inteiras). -->

### RNF-XXX-001: [Segurança]
### RNF-XXX-002: [Compatibilidade]
### RNF-XXX-003: [Resiliência]

## Questões em Aberto

<!-- Só referências: as questões nascem e vivem em specs/00-registro-de-questoes.md. -->

- PA-###: [título curto] — trava RF-XXX-00n
