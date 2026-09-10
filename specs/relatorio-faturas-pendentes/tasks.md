# Tarefas — Relatório de faturas pendentes (proxy e exportações)

> **Rastreabilidade** — RF: RF-FAT-001..003 · CT: CT-FAT-001..003
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
> **Baseado em:** `design.md` (aprovado em 2026-09-09)

## Fase 1 — Proxy, permissão e exportações

- [x] T-FAT-1.1 `IsFinanceiroOuFaturamentoOuAdmin` em `users/permissions.py` _(RNF-FAT-001 · CT-FAT-001)_
- [x] T-FAT-1.2 `fedhub/services/relatorios_service.py`: `filtrar_parametros`, chamada ao FedHub com timeout e exceções próprias _(RF-FAT-001, RNF-FAT-002 · CT-FAT-001)_
- [x] T-FAT-1.3 `fedhub/relatorios_documentos.py`: planilha openpyxl e PDF ReportLab no layout do legado _(RF-FAT-002, RF-FAT-003 · CT-FAT-002, CT-FAT-003)_
- [x] T-FAT-1.4 `fedhub/views/relatorios_view.py` e rotas em `bigcorp/urls.py` _(RF-FAT-001..003 · CT-FAT-001..003)_
- [x] T-FAT-1.5 Cobrir CT-FAT-001..003 (17 testes) _(CT-FAT-001..003)_

## Fase 2 — Verificação com o FedHub real

- [ ] T-FAT-2.1 Rodar a tela contra o FedHub pelo túnel e comparar planilha e PDF com o relatório do legado da mesma administradora _(RF-FAT-002, RF-FAT-003)_

## Verificação Final

- [x] Todos os CT da matriz passando (`python manage.py test fedhub.test_relatorio_faturas_pendentes` — 17 testes OK em 2026-09-09, SQLite)
- [x] `bash specs/verificar.sh` sem violações
- [x] Spec e código não divergem
- [x] STATUS.md atualizado
