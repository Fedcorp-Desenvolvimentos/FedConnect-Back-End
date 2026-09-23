# Tarefas — Proxy do cadastro novo

> **Rastreabilidade** — RF: RF-CAD-001..003 · CT: CT-CAD-001..006
> **Status:** em revisão · **Dono:** Daniel Mello · **Atualizado:** 2026-09-23 · **Implementadas em 2026-09-23 (instrução do dono); aprovação retroativa pendente**
> **Baseado em:** `design.md` (em revisão, 2026-09-23)

## Fase 1 — Service e view
- [x] T-CAD-1.1 `fedhub/services/cadastro_service.py` _(RF-CAD-001 · RF-CAD-002 · RNF-CAD-001 · CT-CAD-001 · CT-CAD-002 · CT-CAD-005)_
- [x] T-CAD-1.2 `fedhub/views/cadastro_view.py` e rota em `bigcorp/urls.py` _(RF-CAD-002 · RF-CAD-003 · RNF-CAD-002 · CT-CAD-003 · CT-CAD-004 · CT-CAD-006)_
- [x] T-CAD-1.3 `fedhub/test_cadastro_proxy.py` (unittest sem banco) _(CT-CAD-001..006)_

## Fase 2 — Do dono
- [ ] T-CAD-2.1 Deploy no App Platform e teste com a tela (`FedConnect-FrontEnd/specs/cadastro-clientes/` fase 10) _(RNF-CAD-003)_
- [ ] T-CAD-2.2 Fechar PA-014 (`ti`?) _(RF-CAD-003)_

## Verificação Final
- [x] `DJANGO_SETTINGS_MODULE=bigcorp.settings python -m unittest fedhub.test_cadastro_proxy`
- [x] `bash specs/verificar.sh` sem violações
- [x] Views duplicadas em sincronia (não há duplicata)
- [x] STATUS.md atualizado
