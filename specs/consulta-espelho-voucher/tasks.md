# Tarefas — Consulta de voucher devolve exatamente o que entrou no documento

> **Rastreabilidade** — RF: RF-VOU-002..005 · RNF: RNF-VOU-001 · ADR: ADR-0008 · Questões: PA-016
> **Status:** em revisão · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-18
> **Baseado em:** `design.md` (em revisão, 2026-09-18). Código feito na branch `feat/consulta-espelho-voucher` no dia da decisão do dono; aprovação formal do design e destas tarefas pendente.

## Fase 1: Memória da emissão

- [x] T-VOU-1.1 `fedhub/models.py`: `VoucherEmitido` e `VoucherEmitidoItem`; `"fedhub"` em `INSTALLED_APPS`; migração `0001_voucher_emitido` _(RF-VOU-002 · CT-VOU-002)_
- [x] T-VOU-1.2 `fedhub/services/espelho_voucher_service.py`: `chave_da_linha`, `registrar_emissao` (idempotente), `aplicar_espelho`, `marcar_cancelamento` _(RF-VOU-002, RF-VOU-003, RF-VOU-004 · CT-VOU-002, CT-VOU-003, CT-VOU-004)_

## Fase 2: Ligação nas rotas

- [x] T-VOU-2.1 Emissão de voucher e de recibo registram após o PDF; falha só loga _(RF-VOU-002, RNF-VOU-001 · CT-VOU-002)_
- [x] T-VOU-2.2 Consulta com `voucher` aplica o espelho e devolve `espelho`/`aviso` _(RF-VOU-003 · CT-VOU-003)_
- [x] T-VOU-2.3 Cancelamento marca `cancelado_em` _(RF-VOU-004 · CT-VOU-004)_
- [x] T-VOU-2.4 `fedhub/test_consulta_espelho_voucher.py`: 12 testes verdes em 2026-09-18 (sqlite em memória)

## Fase 3: Produção e tela

- [ ] T-VOU-3.1 Deploy do Django com `migrate fedhub` **antes** do front _(design: Impacto e Riscos)_
- [ ] T-VOU-3.2 Emitir um voucher de teste e consultar pelo número: `total_registros` igual ao número de linhas do PDF e `espelho: true` _(INV-VOU-001)_
- [x] T-VOU-3.3 Front: tela de consulta mostra o `aviso` quando `espelho` é `false` — feito em 2026-09-18 na branch `feat/planilha-espelho-voucher` do frontend (`useConsultaComissao.js` + `ConsultaComissao.jsx`), build OK _(RF-VOU-003)_
- [ ] T-VOU-3.4 Decidir a pergunta em aberto de PA-016: parcela sem baixa deve entrar na lista de emissão?

## Fase 4: Documentos anteriores ao registro

- [x] T-VOU-4.1 Campo `reconstituido` em `VoucherEmitido` (migração 0002) e aviso na consulta quando o registro é inferido _(RF-VOU-005 · CT-VOU-005)_
- [x] T-VOU-4.2 `manage.py reconstituir_espelho_voucher` (simula por padrão, `--confirmar` grava, `--favorecido`, `--refazer`); 8 testes verdes em 2026-09-18 _(RF-VOU-005 · CT-VOU-005)_
- [ ] T-VOU-4.3 Rodar em produção para os vouchers antigos que o financeiro precisar consultar, conferindo o total contra o PDF de cada um _(RF-VOU-005)_
