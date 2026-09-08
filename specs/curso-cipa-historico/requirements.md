# Requisitos — Histórico, consulta e documentos do CIPA (fase 2)

> **Rastreabilidade** — RF: RF-HIS-001..004 · RNF: RNF-HIS-001..002 · ADR: ADR-0004, ADR-0007 · Questões: PA-007, PA-009
> **Fase 3 (presença): `RF-HIS-004`, `RNF-HIS-002` em revisão — aguardando aprovação do dono antes do design.**
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-08

## Contexto e Problema

`[E]` A spec `curso-cipa` entrega a **agenda**: `GET cursos-cipa/?mes&ano` devolve o mês inteiro sem paginação, porque o calendário pede assim (`condomed/views.py`, `pagination_class = None`). Não há como listar seis meses de turmas nem responder "em quais turmas esta pessoa esteve" fora do `verificar-cpf`, que só aceita CPF. `[D]` O solicitante pediu, em reunião de 2026-09-04, histórico de turmas, consulta de participantes e documentos (lista de presença, presença, certificado). Mapeamento completo em `../../docs/curso-cipa/MAPEAMENTO_CIPA_FASE2.md`; esta spec cobre a **fase A** (histórico e consulta). Presença e certificado ficam em rascunho até as respostas de PA-007.

## Escopo

**Dentro do escopo (fase A):**
- Listagem paginada de turmas por período, com filtros de local, situação, administradora, condomínio e busca livre
- Consulta de participantes em todas as turmas, uma linha por inscrição, com o resumo da turma

**Dentro do escopo (fase B):**
- Lista de presença da turma em PDF, para assinatura no dia

**Dentro do escopo (fase C — fase 3 para o dono):**
- Registro de presença por inscrição, em lote, com auditoria; turma passa a `realizada` ao primeiro registro

**Fora do escopo por enquanto:** certificado (fase D; decisões tomadas em PA-008, aguarda a presença existir). A rota do calendário não muda.

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

### RF-HIS-003: Lista de presença em PDF

**Como** operador da Condomed, **quero** imprimir a lista de presença da turma, **para** os participantes assinarem no dia do curso.

- **QUANDO** consulto `cursos-cipa/{id}/lista-presenca/`, **ENTÃO** o sistema **DEVE** devolver um PDF (`application/pdf`, `Content-Disposition` com nome `lista-presenca-cipa-<data>-<local>.pdf`, header exposto ao CORS) gerado do registro na hora — nada armazenado. `[D]` ADR-0007
- **QUANDO** a lista é montada, **ENTÃO** os inscritos **DEVEM** vir ordenados por condomínio e, dentro dele, por nome — a assinatura acontece em bloco por condomínio. `[D]` ADR-0007
- **QUANDO** a lista é montada, **ENTÃO** ela **DEVE** trazer linhas em branco numeradas no fim, para quem chegar de última hora; hoje 5. `[P]` PA-007 (quantidade e coluna de horário a confirmar)
- **QUANDO** peço a lista de uma turma futura ou sem inscritos, **ENTÃO** o sistema **DEVE** gerá-la mesmo assim — é para levar impressa. `[D]` ADR-0007
- **QUANDO** a lista é montada, **ENTÃO** o cabeçalho **DEVE** trazer unidade emissora (do local), data por extenso, local, horário, instrutor (ou "a definir") e total de inscritos; o rodapé, quem gerou e quando. `[E]` `condomed/documentos.py`
- **SE** o usuário não tem nível `condomed`/`admin`, **ENTÃO** o sistema **DEVE** responder 403. `[E]` mesmo `IsCondomedOrAdmin` do viewset

### RF-HIS-004: Registro de presença

**Como** operador da Condomed, **quero** registrar quem esteve no curso, **para** a turma virar fato realizado e o certificado sair só para quem participou.

- **QUANDO** envio `POST cursos-cipa/{id}/presenca/` com `{presencas: [{inscricao_id, presente}]}`, **ENTÃO** o sistema **DEVE** gravar, para cada inscrição da lista, `presenca` (verdadeiro/falso), `presenca_registrada_em` e `presenca_registrada_por`, tudo em uma transação — ou grava todas, ou nenhuma. `[D]` PA-007 (não existe presença parcial: é presente ou ausente)
- **SE** alguma `inscricao_id` não pertence à turma, **ENTÃO** o sistema **DEVE** recusar o lote inteiro com 400, apontando o id. `[E]` mesmo padrão de erro por índice da importação
- **QUANDO** é a primeira gravação de presença da turma, **ENTÃO** a turma **DEVE** passar a `realizada` na mesma transação. `[D]` PA-007 (situação inferida; opção manual sai do formulário)
- **QUANDO** já existe presença registrada, **ENTÃO** o sistema **DEVE** aceitar regravar a qualquer tempo, atualizando `registrada_em`/`por` — não há prazo. `[D]` PA-007
- **SE** a turma está `cancelada`, **ENTÃO** o sistema **DEVE** recusar com 400 — não há presença em curso que não aconteceu. `[E]` `STATUS_ATIVOS` em `condomed/services.py`
- **SE** a data da turma ainda não chegou, **ENTÃO** o sistema **DEVE** recusar com 400. `[P]` PA-009
- **QUANDO** consulto a turma, a listagem, o histórico ou os participantes, **ENTÃO** cada inscrição **DEVE** trazer `presenca` (`true`/`false`/`null` = não registrada), `presenca_registrada_em` e o nome de quem registrou; e a turma **DEVE** trazer `presentes`, `ausentes` e `sem_registro`. `[E]` regra do repo: contagens vêm do backend
- **QUANDO** um inscrito é adicionado a uma turma já `realizada` (chegou de última hora e foi registrado depois), **ENTÃO** ele **DEVE** nascer com `presenca = null`, e o operador marca em seguida. `[D]` PA-007
- **SE** o usuário não tem nível `condomed`/`admin`, **ENTÃO** o sistema **DEVE** responder 403 — qualquer um dos dois níveis pode marcar, não só quem ministrou. `[D]` PA-007

## Requisitos Não Funcionais

**Verificação prevista (detalhada no design, após aprovação):** CT-HIS-006 — lote grava presente/ausente com auditoria e vira a turma `realizada`; id fora da turma → 400 sem gravar nada; regravar aceito; `cancelada` → 400; data futura → 400; contagens `presentes`/`ausentes`/`sem_registro` na turma; inscrito novo em turma realizada nasce `null`; `usuario` → 403.

### RNF-HIS-002: Presença é fato auditável

Toda gravação de presença registra quem e quando; regravar sobrescreve o valor mas mantém a auditoria da última gravação. Nada de presença é apagado por retenção: o histórico guarda tudo. `[D]` PA-007



### RNF-HIS-001: Paginação com teto

25 por página por padrão; `page_size` até 100. Acima disso o servidor corta. `[E]` `PaginacaoHistorico`

## Questões em Aberto

- PA-007: perguntas ao solicitante sobre presença e certificado (carga horária, texto, assinatura, numeração, prazo de presença). Travam as fases C e D; não travam esta.
