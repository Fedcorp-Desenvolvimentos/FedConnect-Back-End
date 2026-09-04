# Requisitos — Histórico, consulta e documentos do CIPA (fase 2)

> **Rastreabilidade** — RF: RF-HIS-001..002 · RNF: RNF-HIS-001 · ADR: ADR-0004 · Questões: PA-007
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-04

## Contexto e Problema

`[E]` A spec `curso-cipa` entrega a **agenda**: `GET cursos-cipa/?mes&ano` devolve o mês inteiro sem paginação, porque o calendário pede assim (`condomed/views.py`, `pagination_class = None`). Não há como listar seis meses de turmas nem responder "em quais turmas esta pessoa esteve" fora do `verificar-cpf`, que só aceita CPF. `[D]` O solicitante pediu, em reunião de 2026-09-04, histórico de turmas, consulta de participantes e documentos (lista de presença, presença, certificado). Mapeamento completo em `../../MAPEAMENTO_CIPA_FASE2.md`; esta spec cobre a **fase A** (histórico e consulta). Presença e certificado ficam em rascunho até as respostas de PA-007.

## Escopo

**Dentro do escopo (fase A):**
- Listagem paginada de turmas por período, com filtros de local, situação, administradora, condomínio e busca livre
- Consulta de participantes em todas as turmas, uma linha por inscrição, com o resumo da turma

**Fora do escopo desta fase:** presença, lista de presença em PDF, certificado (fases B–D do mapeamento; dependem de PA-007). A rota do calendário não muda.

## User Stories e Critérios de Aceitação

### RF-HIS-001: Histórico de turmas por período

**Como** operador da Condomed, **quero** listar as turmas de um período com filtros, **para** ver o que já aconteceu sem folhear o calendário mês a mês.

- **QUANDO** consulto `cursos-cipa/historico/`, **ENTÃO** o sistema **DEVE** devolver as turmas paginadas, da mais recente para a mais antiga, sem a lista de inscritos e com contagens e as listas derivadas de administradoras e condomínios. `[D]` ADR-0004 (as listas derivadas existem para isso)
- **QUANDO** informo `data_inicio`, `data_fim`, `local` ou `status`, **ENTÃO** a lista **DEVE** respeitar cada filtro. `[E]` `condomed/views.py` `historico`
- **QUANDO** informo `administradora` (código) ou `condominio` (trecho), **ENTÃO** a lista **DEVE** trazer as turmas que têm **inscritos** daquela administradora ou condomínio — o vínculo é do participante. `[D]` ADR-0004
- **QUANDO** informo `busca`, **ENTÃO** o sistema **DEVE** casar nome, CPF (com ou sem máscara), condomínio e administradora dos inscritos e a observação da turma, **sem repetir** uma turma em que vários inscritos casam. `[E]` `distinct()` em `historico`
- **QUANDO** a agenda consulta `GET cursos-cipa/?mes&ano`, **ENTÃO** a resposta **DEVE** continuar sendo a lista do mês, sem paginação. `[E]` rota separada de propósito

### RF-HIS-002: Consulta de participantes

**Como** operador, **quero** procurar uma pessoa, um condomínio ou uma administradora e ver em quais turmas apareceram, **para** responder ao condomínio e preparar as fases de presença e certificado.

- **QUANDO** consulto `cursos-cipa/participantes/`, **ENTÃO** o sistema **DEVE** devolver inscrições paginadas, **uma linha por inscrição**, cada uma com o resumo da turma (id, data, local, situação). `[E]` presença e certificado serão por inscrição (mapeamento, seção 3)
- **QUANDO** informo `cpf`, `administradora`, `condominio`, `data_inicio` ou `data_fim`, **ENTÃO** a lista **DEVE** respeitar cada filtro. `[E]` `participantes`
- **QUANDO** informo `busca`, **ENTÃO** o sistema **DEVE** casar nome, condomínio e administradora, e o **início** do CPF quando o termo tiver dígitos — "Maria" não é CPF. `[E]` `participantes`

## Requisitos Não Funcionais

### RNF-HIS-001: Paginação com teto

25 por página por padrão; `page_size` até 100. Acima disso o servidor corta. `[E]` `PaginacaoHistorico`

## Questões em Aberto

- PA-007: perguntas ao solicitante sobre presença e certificado (carga horária, texto, assinatura, numeração, prazo de presença). Travam as fases C e D; não travam esta.
