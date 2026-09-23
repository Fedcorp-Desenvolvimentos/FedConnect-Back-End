# Painel de status das specs

> **Atualizado:** 2026-09-23

Estado de cada documento. Se esta página divergir do cabeçalho de um documento, **esta página vence**. Significado dos estados em [CONVENCOES.md](./CONVENCOES.md) §4 — só `aprovado` vincula.

| Spec | requirements | design | tasks |
|---|---|---|---|
| `consulta-espelho-voucher` | aprovado (2026-09-18) — decisão do dono em PA-016: a consulta por voucher devolve exatamente o que entrou no documento | **em revisão** (2026-09-18) — ADR-0008; modelos `VoucherEmitido`/`VoucherEmitidoItem` no app `fedhub` (que entrou em `INSTALLED_APPS`) | **em revisão** (2026-09-18) — Fases 1–2 na branch `feat/consulta-espelho-voucher` (12 testes); Fase 3 (migrate em produção antes do front, teste com voucher real, aviso na tela, pergunta em aberto) pendente |
| `curso-cipa` | **em revisão** (2026-09-04) | **em revisão** (2026-09-04) | **em revisão** (2026-09-04) — Fases 1–3 concluídas (29 testes); Fase 4 (ADR-0004, vínculo no inscrito) **pendente de aprovação** |
| `curso-cipa-historico` | aprovado (2026-09-09) — RF-HIS-001..006, RNF-HIS-001..003 | aprovado (2026-09-09) — fases A–D | aprovado (2026-09-09) — fases A (histórico e consulta), B (lista de presença em PDF), C (presença) e **D (certificado em lote, PDF e reemissão)** concluídas; 125 testes |
| `curso-cipa-cadastros` | aprovado (2026-09-09) — palestrantes e locais editáveis (reverte PA-001 e Q3 de PA-008; PA-010/011 fechadas) | aprovado (2026-09-09) | aprovado (2026-09-09) — fases 1–3 concluídas (112 testes); pendente de operação: bucket S3 e variáveis no App Platform antes do deploy |
| `auth-refresh-token` | formato legado (sem matriz — não verificado); cabeçalho diz Aprovado (2026-08-24) | — | — |
| `cadastro-etl` | em revisão (2026-09-23) — RF-CAD-001..003, RNF-CAD-001..003; proxy `cadastro/<rota>` → `/api/etl/<rota>` do FedHub (spec `FedHub-Backend/specs/etl-cadastro-api/`); contexto `CAD` novo; PA-014 aberta (só `admin` por ora); **implementado por instrução do dono, aprovação retroativa pendente** | em revisão (2026-09-23) — ADR-0008 | em revisão (2026-09-23) — fase 1 implementada e testada; fase 2 (deploy, PA-014) do dono |
