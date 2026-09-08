# Tarefas — Histórico e consulta do CIPA (fase A)

> **Rastreabilidade** — RF: RF-HIS-001..003 · CT: CT-HIS-001..005
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-04
> **Baseado em:** `design.md` (aprovado)

## Fase 1 (fase A do mapeamento) — Histórico e consulta

- [x] T-HIS-1.1 `PaginacaoHistorico` e action `historico` com filtros, busca e `distinct` _(RF-HIS-001, RNF-HIS-001 · CT-HIS-001, CT-HIS-002)_
- [x] T-HIS-1.2 `TurmaResumoSerializer` sem `inscricoes` _(RF-HIS-001 · CT-HIS-001)_
- [x] T-HIS-1.3 Action `participantes` e `InscricaoComTurmaSerializer` _(RF-HIS-002 · CT-HIS-003)_
- [x] T-HIS-1.4 Cobrir CT-HIS-001..004 em `condomed/tests.py` _(CT-HIS-001..004)_

## Fase 2 (fase B do mapeamento) — Lista de presença

- [x] T-HIS-2.1 `condomed/documentos.py`: linhas ordenadas por condomínio→nome com extras, cabeçalho a partir de local/instrutor, geração ReportLab _(RF-HIS-003 · CT-HIS-005)_
- [x] T-HIS-2.2 Action `lista-presenca/` com `Content-Disposition` exposto ao CORS _(RF-HIS-003 · CT-HIS-005)_
- [x] T-HIS-2.3 Cobrir CT-HIS-005 (6 testes) _(CT-HIS-005)_

## Fases C–D (rascunho, travadas em PA-007)

- [ ] Presença por inscrição · certificado — ver `../../docs/curso-cipa/MAPEAMENTO_CIPA_FASE2.md`

## Verificação Final

- [x] Todos os CT passando (`python manage.py test condomed`) — 85 testes, OK em 2026-09-08 (SQLite; os 79 anteriores também em PostgreSQL 14 + Django 6.0.2)
- [x] `bash specs/verificar.sh` sem violações
- [x] STATUS.md atualizado
