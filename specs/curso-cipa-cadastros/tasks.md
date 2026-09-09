# Tarefas — Cadastro de palestrantes e de locais do CIPA

> **Rastreabilidade** — RF: RF-CIP-006..007 · CT: CT-CIP-021..023
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
> **Baseado em:** `design.md` (aprovado)

## Fase 1 — Modelos e migração

- [x] T-CAD-1.1 `LocalCipa`, `InstrutorCipa`, `UNIDADES`, `gerar_codigo`; FKs em `TurmaCipa` _(RF-CIP-006, RF-CIP-007 · CT-CIP-021, CT-CIP-022)_
- [x] T-CAD-1.2 Migração 0005 (modelos + semente com upload das assinaturas legadas) e 0006 (troca dos campos) _(RF-CIP-006, RF-CIP-007 · CT-CIP-021, CT-CIP-022)_

## Fase 2 — API

- [x] T-CAD-2.1 `CodigoField`; `TurmaCipaSerializer`/`ImportarTurmaSerializer` por código, recusa de cadastro desativado; `services` lendo do registro _(RNF-CIP-004 · CT-CIP-023)_
- [x] T-CAD-2.2 `LocalCipaSerializer`, `InstrutorCipaSerializer` (assinatura write-only, limites), `CadastroCipaViewSet` e subclasses; router antes de `cursos-cipa` _(RF-CIP-006, RF-CIP-007, RNF-CIP-006 · CT-CIP-021..023)_
- [x] T-CAD-2.3 `documentos.py` e `verificar-cpf` lendo do registro _(RF-CIP-006, RF-CIP-007 · CT-HIS-005)_
- [x] T-CAD-2.4 `MEDIA_ROOT` + `STORAGES` S3 condicional; `django-storages[s3]` no requirements; `media/` no `.gitignore` _(RNF-CIP-005 · CT-CIP-021)_

## Fase 3 — Testes

- [x] T-CAD-3.1 Adaptar a suíte existente (turmas criadas por registro, não por código) _(CT-CIP-001..020, CT-HIS-001..006)_
- [x] T-CAD-3.2 `CadastrosCipaTests` cobrindo CT-CIP-021..023 (16 testes) _(CT-CIP-021..023)_

## Pendente de operação (não é código)

- [ ] T-CAD-4.1 Provisionar bucket S3 privado e as quatro variáveis de ambiente no App Platform **antes** do deploy que roda a 0005 _(RNF-CIP-005)_

## Verificação Final

- [x] `python manage.py test condomed` — 112 testes OK em 2026-09-08 (SQLite, Django 5.2.1)
- [x] `python manage.py makemigrations --check` sem diferenças
- [x] `bash specs/verificar.sh` sem violações; STATUS.md atualizado
