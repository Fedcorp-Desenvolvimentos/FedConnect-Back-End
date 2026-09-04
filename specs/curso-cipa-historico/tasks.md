# Tarefas — Histórico e consulta do CIPA (fase A)

> **Rastreabilidade** — RF: RF-HIS-001..002 · CT: CT-HIS-001..004
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-04
> **Baseado em:** `design.md` (aprovado)

## Fase 1 (fase A do mapeamento) — Histórico e consulta

- [x] T-HIS-1.1 `PaginacaoHistorico` e action `historico` com filtros, busca e `distinct` _(RF-HIS-001, RNF-HIS-001 · CT-HIS-001, CT-HIS-002)_
- [x] T-HIS-1.2 `TurmaResumoSerializer` sem `inscricoes` _(RF-HIS-001 · CT-HIS-001)_
- [x] T-HIS-1.3 Action `participantes` e `InscricaoComTurmaSerializer` _(RF-HIS-002 · CT-HIS-003)_
- [x] T-HIS-1.4 Cobrir CT-HIS-001..004 em `condomed/tests.py` _(CT-HIS-001..004)_

## Fases B–D (rascunho, travadas em PA-007)

- [ ] Lista de presença em PDF · presença por inscrição · certificado — ver `../../MAPEAMENTO_CIPA_FASE2.md`

## Verificação Final

- [x] Todos os CT passando (`python manage.py test condomed`) — 71 testes, OK em 2026-09-04 (SQLite)
- [x] `bash specs/verificar.sh` sem violações
- [x] STATUS.md atualizado
