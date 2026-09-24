# Tarefas — A tela Produção CORP lê o Data Lake CORP

> **Rastreabilidade** — RF: RF-IEX-011 · CT: CT-IEX-020..022
> **Status:** aprovado (2026-09-23) · **Dono:** Ingryd Aylana · **Atualizado:** 2026-09-23
> **Baseado em:** `design.md` (aprovado em 2026-09-23)

<!-- Aprovação em bloco pela dona em 23/09/2026 ("vamos manter o que está no lake"; "pode mexer, só não publica nada"). -->

## Fase 1 — Lake e FedHub (repositórios deles)

- [x] T-IEX-11.1 Lake: `vw_documento_indicador` e `fn_ind_*` no contrato do financeiro, `SECURITY DEFINER`; 6 testes _(RF-IEX-011)_
- [x] T-IEX-11.2 FedHub: rotas `/api/lake/indicadores/*` (RF-LAK-006); 6 testes _(RF-IEX-011)_

## Fase 2 — FedConnect

- [x] T-IEX-11.3 `agregacao.py` e `nao_fechadas.py` como montadores sobre o FedHub _(RF-IEX-011, RNF-IEX-007 · CT-IEX-021)_
- [x] T-IEX-11.4 Views: 503 nomeado quando o lake não responde _(RF-IEX-011 · CT-IEX-022)_
- [x] T-IEX-11.5 `fedhub_falso.py` com as rotas `indicadores/*` sobre o banco de teste; expectativas de `tests.py` na regra do lake — **78 testes OK** em 2026-09-23 _(RNF-IEX-007 · CT-IEX-020, CT-IEX-021)_
- [x] T-IEX-11.6 Ponta a ponta local em 2026-09-23: sete endpoints com o dado do lake; Allianz × condomínio igual ao painel de TV _(RF-IEX-011)_

## Fase 3 — Produção (depende de outros; NADA publicado em 23/09)

- [ ] T-IEX-11.7 Teste local com a dona em 24/09; depois FedHub de produção com o módulo novo e lake do servidor com o contrato republicado _(RF-IEX-011)_
- [ ] T-IEX-11.8 Comunicar ao gestor comercial a mudança de base (vigência e prêmio líquido) _(RF-IEX-011)_
- [ ] T-IEX-11.9 Aposentar o espelho (`Producao` e cargas) com migração própria, quando a tela estiver validada em produção (ADR-0010) _(RNF-IEX-007)_

## Verificação Final

- [x] CT-IEX-020..022 passando (`manage.py test indicadores`, 2026-09-23)
- [x] `bash specs/verificar.sh` sem violações novas
- [x] Spec e código não divergem
- [x] STATUS.md atualizado
