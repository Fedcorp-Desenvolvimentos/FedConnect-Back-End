# Tarefas — Meta mensal gravada no Data Lake CORP

> **Rastreabilidade** — RF: RF-IEX-010 · CT: CT-IEX-016..019
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana · **Atualizado:** 2026-09-23
> **Baseado em:** `design.md` (aprovado em 2026-09-23)

<!-- Aprovação em bloco pela dona em 23/09/2026 ("vamos gravar a meta no lake"; "esses dois já pode adiantar"). -->

## Fase 1 — Backend

- [x] T-IEX-10.1 `indicadores/services/fedhub_lake.py` (cliente HTTP das rotas `/api/lake/*`) _(RF-IEX-010 · CT-IEX-018)_
- [x] T-IEX-10.2 `metas.py` como proxy do FedHub, contrato do front preservado _(RF-IEX-010 · CT-IEX-016)_
- [x] T-IEX-10.3 `views.py`: sigla/abreviatura ao serviço; 503 nomeado quando o lake não responde _(RF-IEX-010 · CT-IEX-016, CT-IEX-018)_
- [x] T-IEX-10.4 `agregacao.py`: metas do lake; realizado da meta em `preliq`; `metas_indisponiveis` _(RF-IEX-010 · CT-IEX-017, CT-IEX-018)_
- [x] T-IEX-10.5 `fedhub_falso.py` ligado em `_ComCarga`; `test_metas.py` reescrito — **74 testes OK** em 2026-09-23 _(RNF-IEX-006 · CT-IEX-019)_
- [x] T-IEX-10.6 Ponta a ponta local em 2026-09-23: POST pela tela → FedHub → `casa_meta_mensal`; meta visível no resumo (38,5 %) e no painel de TV (69,82 %) _(RF-IEX-010)_

## Fase 2 — Produção (depende de outros)

- [ ] T-IEX-10.7 FedHub de produção com as rotas de metas (publicação do módulo `lake`, 24/09) _(RF-IEX-010)_
- [ ] T-IEX-10.8 Recadastrar na tela as metas vigentes que estavam em `MetaMensal` _(RF-IEX-010)_

## Verificação Final

- [x] CT-IEX-016..019 passando (`manage.py test indicadores`, 2026-09-23)
- [x] `bash specs/verificar.sh` sem violações novas
- [x] Spec e código não divergem
- [x] STATUS.md atualizado
