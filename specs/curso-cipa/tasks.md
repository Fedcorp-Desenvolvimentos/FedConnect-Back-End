# Tarefas — Agendamento de cursos CIPA (Condomed)

> **Rastreabilidade** — RF: RF-CIP-001..005 · CT: CT-CIP-001..019
> **Status:** em revisão · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-04
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

## Fase 4 — Vínculo no inscrito (ADR-0004)

- [x] T-CIP-4.1 Mover `administradora_codigo`, `administradora_nome` e `condominio_nome` de `TurmaCipa` para `InscricaoCipa` (obrigatórios) + migração `0002` destrutiva; `__str__` da turma por local + data _(RF-CIP-001, RF-CIP-003 · CT-CIP-011, CT-CIP-013)_
- [x] T-CIP-4.2 `InscricaoCipaSerializer` exige e valida o vínculo; `TurmaCipaSerializer` deixa de aceitá-lo e expõe `administradoras`/`condominios` derivados _(RF-CIP-001, RF-CIP-003 · CT-CIP-011, CT-CIP-012)_
- [x] T-CIP-4.3 Tema do espelho na agenda por local; 409 sem citar condomínio da turma _(RF-CIP-002 · CT-CIP-003)_
- [x] T-CIP-4.4 `verificar-cpf` devolvendo administradora e condomínio de cada inscrição _(RF-CIP-003 · CT-CIP-009)_
- [x] T-CIP-4.5 Numerar e cobrir CT-CIP-009 a CT-CIP-013 em `condomed/tests.py`, ajustando os testes que hoje criam turma com cliente _(RNF-CIP-001 · CT-CIP-009..013)_
- [x] T-CIP-4.6 Cobrir a exclusão da turma inteira: cascata das inscrições, remoção do espelho, dia liberado, 403 e a alternativa de cancelar _(RF-CIP-002 · CT-CIP-014)_

## Fase 5 — Importação por planilha (ADR-0005)

- [x] T-CIP-5.1 `ImportarTurmaSerializer`: capacidade, regras de linha por índice e CPF repetido na planilha _(RF-CIP-005 · CT-CIP-016, CT-CIP-017)_
- [x] T-CIP-5.2 `POST cursos-cipa/importar/` criando turma, espelho e inscritos em uma transação _(RF-CIP-005 · CT-CIP-015)_
- [x] T-CIP-5.3 `GET cursos-cipa/planilha-modelo/` com openpyxl, CPF como texto e sem colunas de local/data _(RF-CIP-005 · CT-CIP-018)_
- [x] T-CIP-5.4 Cobrir CT-CIP-015..018 em `condomed/tests.py` _(RNF-CIP-001 · CT-CIP-015..018)_

## Fase 6 — Capacidade como referência (ADR-0006)

- [x] T-CIP-6.1 Retirar a recusa por capacidade da inscrição individual e da importação _(RF-CIP-003, RF-CIP-005 · CT-CIP-006, CT-CIP-017)_
- [x] T-CIP-6.2 `acima_da_capacidade` na resposta da turma _(RF-CIP-003 · CT-CIP-006)_
- [x] T-CIP-6.3 Remover `travar_turma`/`select_for_update`, que existia só para a trava _(RF-CIP-003)_
- [x] T-CIP-6.4 Ajustar CT-CIP-006 e CT-CIP-017 e acrescentar `cpf_sintetico` para listas grandes nos testes _(RNF-CIP-001 · CT-CIP-006, CT-CIP-017)_

## Fase 7 — Duplicidade de CPF à prova de corrida

- [x] T-CIP-7.1 `views.salvar_inscricao` traduz o `unique_together` em 400 e isola a falha em `atomic` _(RF-CIP-003 · CT-CIP-019)_
- [x] T-CIP-7.2 `CPF_DUPLICADO` como frase única, no serializer, importada pela view _(RF-CIP-003 · CT-CIP-019)_
- [x] T-CIP-7.3 Cobrir CT-CIP-019, inclusive a corrida com a validação neutralizada _(RNF-CIP-001 · CT-CIP-019)_

## Verificação Final

- [x] Todos os CT da matriz passando (`python manage.py test condomed`) — 29 testes, OK em 2026-09-01 (local, SQLite: sem Postgres na máquina)
- [x] Fases 4 a 7 verificadas: 59 testes OK em 2026-09-04 (SQLite; o `.env` local tem credenciais placeholder de Postgres)
- [ ] Reverificar em Postgres antes do merge
- [x] `bash specs/verificar.sh` sem violações
- [x] Spec e código não divergem; STATUS.md atualizado
