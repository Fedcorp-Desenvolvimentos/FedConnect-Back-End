# Tarefas — Indicadores executivos da produção (espelho da CORP e agregações)

> **Rastreabilidade** — RF: RF-IEX-001..007 · CT: CT-IEX-001..008
> **Status:** em revisão · **Dono:** Hamilton (gestor comercial), via Lucas Guidi · **Atualizado:** 2026-09-22
> **Baseado em:** `design.md` (em revisão em 2026-09-22; implementação autorizada pelo dono por mensagem para a usuária "mexer e ver")

## Fase 1 — Espelho e carga

- [x] T-IEX-1.1 App `indicadores`: `apps.py`, modelos do design, `admin.py`, migração `0001_espelho_corp`, registro em `INSTALLED_APPS` _(RF-IEX-001 · CT-IEX-001)_
- [x] T-IEX-1.2 `services/carga.py`: leitura do contrato do snapshot, conversão de datas com `datemi_bruta`, upsert em lote, rejeitos nomeados, `CargaCorp` _(RF-IEX-001, RNF-IEX-004 · CT-IEX-001)_
- [x] T-IEX-1.3 Classificação de renovação na carga (`nosnum_ren` ou apólice anterior do mesmo CPF/CNPJ, empate por `nosnum`) _(RF-IEX-001 · CT-IEX-002)_
- [x] T-IEX-1.4 `management/commands/carregar_snapshot_corp.py` com saída resumida e `CommandError` no contrato quebrado _(RF-IEX-001 · CT-IEX-001)_

## Fase 2 — Endpoints de leitura

- [x] T-IEX-2.1 `services/periodos.py`: parâmetros comuns, janelas de período e período anterior, fuso local, validação → 400 _(RF-IEX-003 · CT-IEX-003)_
- [x] T-IEX-2.2 `services/agregacao.py`: queryset base, Bloco com cobertura, resumo, por seguradora, séries por dia e mês _(RF-IEX-003, RF-IEX-004, RF-IEX-005, RNF-IEX-002, RNF-IEX-003 · CT-IEX-003, CT-IEX-004, CT-IEX-005)_
- [x] T-IEX-2.3 `services/nao_fechadas.py`: regra da janela, novas apólices por cadeia e por CPF, rótulos de situação, mascaramento, corte em 400 _(RF-IEX-006 · CT-IEX-006)_
- [x] T-IEX-2.4 Composição: três listas a partir das mesmas querysets dos cartões _(RF-IEX-007 · CT-IEX-007)_
- [x] T-IEX-2.5 `views.py` (seis `APIView` com `IsAuthenticated` e `extend_schema`), `serializers.py` dos parâmetros, rotas em `bigcorp/urls.py` _(RF-IEX-002..007, RNF-IEX-001 · CT-IEX-003..008)_
- [x] T-IEX-2.6 `tests.py` cobrindo CT-IEX-001..008 com dados sintéticos _(CT-IEX-001..008)_

## Fase 3 — Dados reais (depende de PA-021, spec própria)

- [ ] T-IEX-3.1 Carregador do lake gravando nas mesmas tabelas com `origem = lake` _(RNF-IEX-004)_

## Verificação Final

- [x] Todos os CT da matriz passando (`python manage.py test indicadores`)
- [x] Views duplicadas (consultas/ × fedhub/) em sincronia, se tocadas — nenhuma tocada
- [x] `bash specs/verificar.sh` sem violações
- [ ] Spec e código não divergem (se divergiu, a spec foi atualizada primeiro)
- [ ] STATUS.md atualizado
