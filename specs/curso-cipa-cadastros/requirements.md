# Requisitos — Cadastro de palestrantes e de locais do CIPA

> **Rastreabilidade** — RF: RF-CIP-006..007 · RNF: RNF-CIP-004 · ADR: ADR-0001, ADR-0006, ADR-0007 · Questões: PA-010, PA-011
> **Status:** rascunho · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-08

## Contexto e Problema

`[E]` Hoje os instrutores que assinam o certificado e os locais onde o curso acontece são constantes no código: `INSTRUTORES_CIPA` e `LOCAIS_CIPA` em `condomed/models.py`, servidas ao frontend por `GET cursos-cipa/instrutores/` e `GET cursos-cipa/locais/` (`condomed/views.py`). Um palestrante novo ou uma sala nova exige deploy. `[D]` Isso foi decisão do dono em duas ocasiões: PA-001 (locais, 2026-08-31) e PA-008 (instrutores fixos "para não cadastrar errado", 2026-09-04). `[P]` Em 2026-09-08 o dono pediu o contrário: uma área na Condomed onde o próprio usuário cadastre palestrantes e locais. Esta spec registra a reversão (PA-010) e o que ela exige. Lado frontend em `FedConnect-FrontEnd-Prod/specs/curso-cipa-cadastros/`.

## Escopo

**Dentro do escopo:**
- Instrutor (palestrante) como registro editável: nome, título, registro MTE, UF, assinatura digitalizada, ativo.
- Local como registro editável: nome, prédio, capacidade, unidade emissora, se compartilha a sala de reunião da agenda, ativo.
- Migração dos dois instrutores e dos dois locais atuais sem mudar nenhuma turma existente.
- Endpoints CRUD sob o mesmo gate `IsCondomedOrAdmin`.

**Fora do escopo:**
- Cadastro de condomínios e de funcionários (segue por inscrição — ADR-0004).
- Unidade emissora editável: continua `CondoMed Rio`, escolhida por local entre as unidades conhecidas no código. Uma unidade nova é deploy.
- Qualquer mudança na agenda atual (`agenda.Reserva`).

## User Stories e Critérios de Aceitação

### RF-CIP-006: Cadastro de palestrantes

**Como** operador da Condomed, **quero** cadastrar quem ministra e assina o curso, **para** escalar um instrutor novo sem depender de desenvolvimento.

- **QUANDO** consulto `GET cursos-cipa/instrutores/`, **ENTÃO** o sistema **DEVE** devolver os instrutores **ativos** com `id`, `nome`, `titulo`, `registro` (formatado `MTE/UF número`) e `tem_assinatura`; com `?todos=1`, também os inativos. A resposta não expõe o arquivo da assinatura. `[E]` contrato atual em `condomed/views.py` `instrutores` (campos `nome`, `titulo`, `registro`)
- **QUANDO** envio `POST cursos-cipa/instrutores/` com `nome`, `registro_mte`, `registro_uf` e, opcionalmente, `titulo` (padrão "Técnico em Segurança no Trabalho") e `assinatura` (imagem PNG ou JPEG, até 500 KB), **ENTÃO** o sistema **DEVE** criar o instrutor ativo e devolvê-lo com 201. `[P]` PA-010
- **SE** já existe instrutor com o mesmo `registro_mte` + `registro_uf`, **ENTÃO** o sistema **DEVE** recusar com 400 — o registro é a identidade do profissional. `[P]` PA-010
- **QUANDO** envio `PATCH cursos-cipa/instrutores/{id}/`, **ENTÃO** o sistema **DEVE** aceitar alterar qualquer campo, inclusive trocar a assinatura e desativar (`ativo=false`). `[P]` PA-010
- **SE** tento excluir (`DELETE`) um instrutor com turma vinculada, **ENTÃO** o sistema **DEVE** recusar com 400 e orientar a desativar — certificado emitido cita esse nome. `[D]` ADR-0007 (o certificado é regenerado do registro; o registro precisa existir)
- **QUANDO** crio ou edito uma turma, **ENTÃO** `instrutor` **DEVE** aceitar apenas instrutor ativo; turma existente com instrutor depois desativado continua válida e continua emitindo certificado. `[P]` PA-010
- **SE** o instrutor da turma não tem assinatura cadastrada, **ENTÃO** a emissão de certificado **DEVE** recusar apontando o instrutor — o certificado sai assinado ou não sai. `[E]` `docs/curso-cipa/ANALISE_CERTIFICADO_CIPA.md` §1 (assinatura digitalizada é parte do documento)
- **QUANDO** a migração roda, **ENTÃO** os dois instrutores de `INSTRUTORES_CIPA` **DEVEM** virar registros, com as assinaturas de `condomed/assets/` carregadas, e toda turma com `instrutor="FELIPE"` ou `"VINICIUS"` **DEVE** apontar para o registro correspondente. `[E]` `condomed/models.py` `INSTRUTORES_CIPA`; `condomed/assets/README.md`

### RF-CIP-007: Cadastro de locais

**Como** operador da Condomed, **quero** cadastrar os locais onde o curso acontece, **para** abrir turma numa sala nova ou corrigir a capacidade sem deploy.

- **QUANDO** consulto `GET cursos-cipa/locais/`, **ENTÃO** o sistema **DEVE** devolver os locais **ativos** com `id`, `nome`, `predio`, `capacidade`, `unidade` (nome, endereço, telefone, e-mail, cidade) e `compartilha_sala_reuniao`; com `?todos=1`, também os inativos. `[E]` contrato atual em `condomed/views.py` `locais`
- **QUANDO** envio `POST cursos-cipa/locais/` com `nome`, `predio`, `capacidade` (inteiro ≥ 1) e `unidade` (código de uma unidade conhecida; hoje só `RIO`), **ENTÃO** o sistema **DEVE** criar o local ativo. `[P]` PA-010
- **SE** já existe local ativo com o mesmo `nome`, **ENTÃO** o sistema **DEVE** recusar com 400. `[P]` PA-010
- **QUANDO** um local tem `compartilha_sala_reuniao=true`, **ENTÃO** turma nele **DEVE** continuar espelhada em `agenda.Reserva` e validada contra as reservas do dia, exatamente como a sala de reunião hoje. **No máximo um** local ativo pode ter essa marca — a agenda atual só conhece uma sala. `[D]` ADR-0001
- **QUANDO** altero a `capacidade` de um local, **ENTÃO** as turmas existentes **DEVEM** passar a calcular `acima_da_capacidade` pelo valor novo — capacidade é referência, não limite. `[D]` ADR-0006
- **SE** tento excluir um local com turma vinculada, **ENTÃO** o sistema **DEVE** recusar com 400 e orientar a desativar. `[P]` PA-010
- **QUANDO** desativo um local, **ENTÃO** ele **DEVE** sumir das opções de turma nova e das abas do calendário, mas turmas passadas nele **DEVEM** continuar legíveis no histórico e nos documentos. `[P]` PA-010
- **QUANDO** a migração roda, **ENTÃO** `AUDITORIO` e `SALA_REUNIAO` **DEVEM** virar registros (30 e 10 lugares, unidade Rio, a sala com `compartilha_sala_reuniao=true`) e toda turma **DEVE** apontar para o registro correspondente. `[E]` `condomed/models.py` `LOCAIS_CIPA`

## Requisitos Não Funcionais

### RNF-CIP-004: Contrato com o frontend muda de código para id

`local` e `instrutor` na turma, na importação por planilha e nos filtros (`?local=`) passam a ser ids numéricos. Os campos derivados que o frontend já lê (`local_nome`, `instrutor_nome`, `capacidade`, `acima_da_capacidade`) continuam com o mesmo nome e significado. A planilha modelo passa a aceitar o **nome** do local e do instrutor, resolvidos no servidor. `[E]` `condomed/serializers.py` `TurmaCipaSerializer`, `ImportarTurmaSerializer`

### RNF-CIP-005: Assinatura não vive em disco efêmero

A imagem da assinatura fica no banco (`BinaryField` com tipo MIME), não em `MEDIA_ROOT`: o backend roda em container na DigitalOcean App Platform, cujo sistema de arquivos é descartado a cada deploy, e o repositório não tem `STORAGES`/`MEDIA_ROOT` configurados. `[E]` `bigcorp/settings.py` (só `STATIC_ROOT`); verificação em 2026-09-08. Limite de 500 KB por imagem. `[P]` PA-011

### RNF-CIP-006: Acesso

Todos os endpoints de cadastro ficam sob `IsCondomedOrAdmin`, como o resto do módulo. `[E]` `users/permissions.py` `IsCondomedOrAdmin`. Se o dono quiser restringir a criação/edição a `admin`, é resposta da PA-010.

**Verificação prevista (detalhada no design, após aprovação):**
- CT-CIP-021 — instrutores: CRUD, registro duplicado → 400, exclusão com turma → 400, desativado sai da lista e da escolha em turma nova, migração preserva as turmas existentes, emissão recusa instrutor sem assinatura.
- CT-CIP-022 — locais: CRUD, nome duplicado → 400, segundo local com `compartilha_sala_reuniao` → 400, espelho na agenda segue funcionando pelo flag, capacidade alterada reflete em `acima_da_capacidade`, migração preserva as turmas.
- CT-CIP-023 — contrato: turma, importação e filtros aceitam id; planilha aceita nome; `usuario` → 403.

## Questões em Aberto

- PA-010: reversão das decisões de instrutores e locais fixos — quem pode cadastrar, excluir × desativar, assinatura obrigatória no cadastro — trava RF-CIP-006, RF-CIP-007
- PA-011: onde guardar a assinatura (disco efêmero) — trava RNF-CIP-005
