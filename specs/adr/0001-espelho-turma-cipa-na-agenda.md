# ADR-0001 — Turma CIPA na sala de reunião espelhada como Reserva da agenda

> **Status:** a decidir (recomendação abaixo; vira decidido com a aprovação do design de `curso-cipa`) · **Dono:** Ingrid Aylana · **Data:** 2026-08-26
> **Pode ser adiada:** não (define o modelo de dados da turma e a regra de conflito da sala antes da primeira migração)
> **Contexto(s):** `CIP` · **Specs:** `specs/curso-cipa/`

## Contexto

A sala de reunião é compartilhada entre a agenda atual (`agenda.Reserva`, sem campo de local — a sala é premissa embutida) e os cursos CIPA. A operação decidiu que o CIPA terá tela e API próprias, com dois calendários (auditório / sala), **mas** que um curso na sala deve bloquear a sala na agenda atual e uma reunião deve bloquear o curso. A agenda atual não valida conflito no servidor (`agenda/serializers.py` sem `validate()`), só no frontend (`src/utils/agendaSlots.js`).

## Decisão (recomendada)

Turma com `local=SALA_REUNIAO` cria, na mesma transação, uma `agenda.Reserva` vinculada por `OneToOne` (`tema="Curso CIPA — <condomínio>"`, `horario="09:00"`, `duracao=510`); cancelar/excluir a turma remove a reserva; a validação de conflito do CIPA para a sala consulta também as `Reserva` do dia. O auditório só existe no CIPA.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Espelhar como `Reserva` (recomendada) | Baixo | Agenda atual intocada em modelo e tela e mesmo assim enxerga o curso; a direção reunião→curso é coberta pela consulta às Reservas na validação do CIPA |
| Generalizar a agenda (model `Local` + `Reserva.local`) | Alto | Mexe em tela e algoritmo de conflito em produção sem testes; contraria a decisão de calendários separados |
| Agendas totalmente independentes | Baixo | Permite overbooking real da sala — rejeitada pela operação |

## Consequências

- Melhor: uma única fonte de ocupação da sala; agenda atual sem regressão.
- Pior: a `Reserva` espelho tem `duracao=510`, fora das durações da UI da agenda (60–240) — renderização da grade a verificar (PA no frontend); dupla escrita exige `transaction.atomic()`.
- Obrigatório: nunca editar a Reserva espelho pela agenda (marcar `tema` com prefixo fixo e documentar; exclusão pela agenda deixa a turma sem espelho → invariante violado, tratar no design).
