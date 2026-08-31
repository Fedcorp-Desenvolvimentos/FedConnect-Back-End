# FedConnect-Back-End

Backend principal (Django 5 + DRF + PostgreSQL/Supabase), em produção na DigitalOcean. Serve o frontend React e faz proxy das operações Firebird para o **FedHub-Backend** (FastAPI, roda local atrás de ngrok — indisponibilidade do túnel é rotina, não exceção). Rodar local: `python manage.py runserver` (porta 8000, precisa de `.env`).

## Spec-Driven Design (obrigatório)

Este projeto segue o padrão SDD do Grupo FedCorp. Fluxo em [specs/README.md](specs/README.md); **regras de escrita obrigatórias em [specs/CONVENCOES.md](specs/CONVENCOES.md)** (marcas `[E]/[D]/[P]`, IDs `RF-<CTX>-###`, matriz por feature, ADRs em `specs/adr/`, questões em `specs/00-registro-de-questoes.md`); templates em `specs/_templates/`.

**Antes de implementar qualquer mudança, classifique-a:**

- **Exige spec** — endpoint novo/contrato alterado com o frontend, modelo/migração, integração externa (FedHub, BigDataCorp, FedBnk, Monday), autenticação/permissões, mudança cruzando apps, fluxo financeiro. Fluxo: `requirements.md` → aprovação → `design.md` (decisões não óbvias viram ADR) → aprovação → `tasks.md` + `matriz.csv` → implementar tarefa a tarefa.
- **Não exige spec** — fix pontual, refactor interno pequeno, logging, typo. Implemente direto.

Regras: status `aprovado` explícito antes de avançar de fase (cabeçalho **e** `specs/STATUS.md` — divergindo, STATUS.md vence); enunciado sem marca de origem = pendente; entendimento mudou → spec primeiro, ou abra `PA-###` e continue com a hipótese declarada; contratos com frontend/FedHub mudando → spec **nos dois repositórios** (citação cross-repo por caminho); **rode `bash specs/verificar.sh` a cada gravação em `specs/`**.

## Contexto crítico

- **Views/services duplicados**: vários endpoints existem em `consultas/` E em `fedhub/` (ex.: `EmitirVoucherComissaoView`, `CancelarComissaoView`). **O ativo é o que `bigcorp/urls.py` importa** (hoje, majoritariamente `consultas/views.py`). Ao alterar um, atualize a duplicata em sincronia ou elimine-a.
- `consultas/services/fedhub_service.py` é um god-object com `base_url` **hardcoded** (ngrok); os services de `fedhub/services/*` usam `FEDHUB_URL` via env — padrão correto. Não criar métodos novos no god-object.
- A rota "V2" de comissões (`/comissoes/por-data-v2/`) chama na verdade o endpoint **v1** do FedHub (`/api/vouchers/buscar-faturas-comissoes`) — não existe v2 lá.
- Timeouts para o FedHub seguram workers do gunicorn: requisição lenta em série derruba o site inteiro com 504 (incidente de 14/08/2026). Toda chamada nova precisa de timeout explícito e justificado.
- Segredos **somente via env** — o repositório já teve SECRET_KEY/API keys como default no `settings.py` (risco registrado na auditoria; não repetir o padrão).
- Histórico de decisões e correções: `../WORK_LOG.md` e `../PROJECT_CONTEXT.md` (raiz do workspace).
