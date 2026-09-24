# Tarefas — Painel de TV alimentado pelo Data Lake CORP (via FedHub)

> **Rastreabilidade** — RF: RF-IEX-009 · CT: CT-IEX-011..015
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana · **Atualizado:** 2026-09-23
> **Baseado em:** `design.md` (aprovado em 2026-09-23)

<!-- Aprovação de requirements, design e tasks dada em bloco pela dona em 23/09/2026
     ("o painel tv foi pra ser alimentado também"); por isso os três carregam a mesma data. -->

## Fase 1 — Backend

- [x] T-IEX-9.1 `indicadores/services/painel_tv.py`: `linhas()` e `LakeIndisponivel` _(RF-IEX-009, RNF-IEX-005 · CT-IEX-015)_
- [x] T-IEX-9.2 `PainelTvView` + URL `indicadores/painel-tv/` _(RF-IEX-009 · CT-IEX-011..014)_
- [x] T-IEX-9.3 `indicadores/test_painel_tv.py` — 5 testes OK em 2026-09-23 _(CT-IEX-011..015)_

## Fase 2 — Frontend

- [x] T-IEX-9.4 `public/tv/painel.html`: dados fixos fora; `carregar()`/`agrupar()`; recarga 10 min; avisos por estado _(RF-IEX-009)_
- [x] T-IEX-9.5 `IndicadoresHome.jsx`: card passa `?api=` _(RF-IEX-009)_
- [x] T-IEX-9.6 Ponta a ponta local em 2026-09-23: página → Django 8002 → FedHub 8000 → lake; 45 linhas, 0,45 s _(RF-IEX-009)_

## Fase 3 — Produção (depende de outros)

- [x] T-IEX-9.7 FedHub de produção com `LAKE_DSN` em 2026-09-23 — `/api/lake/painel-tv` respondendo 44 linhas pelo túnel; o cliente de escopo `/api/lake` em `AUTH_CLIENTS` fica para quando `AUTH_ENFORCE` ligar _(RF-IEX-009)_
- [x] T-IEX-9.8 Contrato do financeiro publicado no servidor do lake em 2026-09-23, por autorização da gestão antes do TLS _(RNF-IEX-005)_

## Verificação Final

- [x] CT-IEX-011..015 passando (`manage.py test indicadores.test_painel_tv`, 2026-09-23)
- [x] `bash specs/verificar.sh` sem violações novas
- [x] Spec e código não divergem
- [x] STATUS.md atualizado
