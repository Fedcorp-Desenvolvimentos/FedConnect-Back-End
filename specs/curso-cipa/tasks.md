# Tarefas — Agendamento de cursos CIPA (Condomed)

> **Rastreabilidade** — RF: RF-CIP-001..004 · CT: CT-CIP-001..008
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-08-31
> **Baseado em:** `design.md` (aprovado)

## Fase 1 — Modelos e acesso

- [x] T-CIP-1.1 App `condomed` + `TurmaCipa`/`InscricaoCipa` + `LOCAIS_CIPA` + migração _(RF-CIP-001, RF-CIP-003 · CT-CIP-001)_
- [x] T-CIP-1.2 Choice `condomed` em `users.Usuario.nivel_acesso` + migração _(RF-CIP-004 · CT-CIP-007)_
- [x] T-CIP-1.3 `IsCondomedOrAdmin` em `users/permissions.py` _(RF-CIP-004 · CT-CIP-007)_

## Fase 2 — Regras

- [x] T-CIP-2.1 Serializer de turma: conflito local+dia → 409 _(RF-CIP-001 · CT-CIP-002)_
- [x] T-CIP-2.2 Conflito com `agenda.Reserva` quando sala _(RF-CIP-002 · CT-CIP-004)_
- [x] T-CIP-2.3 Espelho atômico em create/destroy _(RF-CIP-002, RNF-CIP-002 · CT-CIP-003, CT-CIP-008)_
- [x] T-CIP-2.4 Serializer de inscrição: CPF, duplicidade, capacidade com `select_for_update` _(RF-CIP-003 · CT-CIP-005, CT-CIP-006)_

## Fase 3 — Rotas e testes

- [x] T-CIP-3.1 ViewSet + rota aninhada + registro em `bigcorp/urls.py` e `INSTALLED_APPS` _(RF-CIP-001..004 · CT-CIP-001)_
- [x] T-CIP-3.2 `condomed/tests.py` cobrindo CT-CIP-001..008 + edição de inscrito _(RNF-CIP-001 · CT-CIP-001..008)_

## Verificação Final

- [x] Todos os CT da matriz passando (`python manage.py test condomed`) — 29 testes, OK em 2026-09-01 (local, SQLite: sem Postgres na máquina)
- [x] `bash specs/verificar.sh` sem violações
- [x] Spec e código não divergem; STATUS.md atualizado
