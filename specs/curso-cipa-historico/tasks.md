# Tarefas — Histórico, consulta e documentos do CIPA (fases A–D)

> **Rastreabilidade** — RF: RF-HIS-001..006 · CT: CT-HIS-001..008
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
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

## Fase 3 (fase C do mapeamento) — Presença

- [x] T-HIS-3.1 Campos `presenca`, `presenca_registrada_em`, `presenca_registrada_por` em `InscricaoCipa`; `TurmaCipa.contagem_presenca()`; migração `0004_presenca_por_inscricao` _(RF-HIS-004, RNF-HIS-002 · CT-HIS-006)_
- [x] T-HIS-3.2 `services.validar_turma_para_presenca` e `services.registrar_presenca` (lote atômico, auditoria, turma → realizada) _(RF-HIS-004 · CT-HIS-006)_
- [x] T-HIS-3.3 Serializers: presença só leitura na inscrição, contagens na turma, `PresencaLoteSerializer`; action `POST cursos-cipa/{id}/presenca/` _(RF-HIS-004 · CT-HIS-006)_
- [x] T-HIS-3.4 Cobrir CT-HIS-006 (11 testes em `PresencaTests`) _(CT-HIS-006)_

## Fase 4 (fase D do mapeamento) — Certificado

- [x] T-HIS-4.1 `ContadorCertificado`, `CertificadoCipa`, `certificado_ou_none`, `contagem_certificados`; migração `0007_certificado_por_inscricao` _(RF-HIS-005, RNF-HIS-003 · CT-HIS-007)_
- [x] T-HIS-4.2 `services`: validação da turma, numeração travada por ano, `emitir_certificados` parcial e idempotente, `motivo_turma_intocavel` _(RF-HIS-005 · CT-HIS-007)_
- [x] T-HIS-4.3 Serializers (certificado na inscrição, contagens e `instrutor_tem_assinatura` na turma, bloqueio de `cancelada`); actions `certificados` e `certificados/pdf`; `CertificadoPdfView`; bloqueios em `perform_destroy` e `DELETE inscricoes/{id}` _(RF-HIS-005, RF-HIS-006 · CT-HIS-007, CT-HIS-008)_
- [x] T-HIS-4.4 `documentos.gerar_certificados` (frente/verso 16:9, assets, assinatura do storage) e `dados_certificado` _(RF-HIS-006 · CT-HIS-008)_
- [x] T-HIS-4.5 Cobrir CT-HIS-007 (9 testes) e CT-HIS-008 (4 testes) em `CertificadoTests` _(CT-HIS-007, CT-HIS-008)_

## Verificação Final

- [x] Todos os CT passando (`python manage.py test condomed`) — 125 testes, OK em 2026-09-09 (SQLite, Django 5.2.1; os 79 da fase A também em PostgreSQL 14 + Django 6.0.2)
- [x] `bash specs/verificar.sh` sem violações
- [x] STATUS.md atualizado
