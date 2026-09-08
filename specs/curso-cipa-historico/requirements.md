# Requisitos — Histórico, consulta e documentos do CIPA (fase 2)

> **Rastreabilidade** — RF: RF-HIS-001..006 · RNF: RNF-HIS-001..003 · ADR: ADR-0004, ADR-0007 · Questões: PA-007, PA-008, PA-009, PA-012
> **Fase 3 (presença): `RF-HIS-004`, `RNF-HIS-002` em revisão — aguardando aprovação do dono antes do design.**
> **Fase D (certificado): `RF-HIS-005`, `RF-HIS-006`, `RNF-HIS-003` em rascunho (2026-09-08) — aguardam aprovação e dependem da fase 3 e de `specs/curso-cipa-cadastros/`.**
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

**Dentro do escopo (fase D):**
- Emissão de certificados em lote para os presentes da turma, com número imutável e auditoria; PDF de todos os certificados da turma e de um certificado isolado (reemissão)

**Fora do escopo por enquanto:** verificação pública do certificado pelo código (fase E — exige rota sem login e política própria); envio por e-mail (PA-008: só download). A rota do calendário não muda.

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

### RF-HIS-005: Emissão de certificados em lote

**Como** operador da Condomed, **quero** emitir de uma vez os certificados de quem esteve na turma, **para** não montar dezoito documentos um a um depois de confirmar dezoito presenças.

- **QUANDO** envio `POST cursos-cipa/{id}/certificados/`, **ENTÃO** o sistema **DEVE** criar um `CertificadoCipa` para cada inscrição da turma com `presenca = true` que ainda não tem certificado, tudo em uma transação, e devolver `{emitidos: [...], ja_existentes: [...], impedidos: [{inscricao_id, motivo}]}`. `[E]` `docs/curso-cipa/MAPEAMENTO_CIPA_FASE2.md` seção 4 (Documentos)
- **QUANDO** uma inscrição presente está sem `condominio_cnpj`, **ENTÃO** ela **DEVE** entrar em `impedidos` com o motivo e o restante do lote **DEVE** ser emitido — corrigido o CNPJ, chama-se de novo só para ela. `[P]` PA-012
- **SE** a turma está sem instrutor, ou o instrutor está sem assinatura, **ENTÃO** o sistema **DEVE** recusar o lote inteiro com 400 apontando o que falta — o certificado sai assinado ou não sai. `[D]` PA-008
- **SE** a turma está `cancelada` ou nenhuma presença foi registrada, **ENTÃO** o sistema **DEVE** recusar com 400. `[D]` PA-007
- **ENQUANTO** uma inscrição está `ausente` ou `não registrada`, ela **NUNCA** recebe certificado — a omissão não vira documento. `[D]` PA-007
- **QUANDO** chamo a emissão de novo, **ENTÃO** o sistema **DEVE** devolver os já emitidos em `ja_existentes` sem criar nada — idempotente; reemitir é baixar de novo, não gerar outro. `[D]` ADR-0007
- **QUANDO** um certificado é criado, **ENTÃO** ele **DEVE** receber `numero` no formato `CIPA-AAAA-000000` (ano da turma, sequencial por ano, sem furo nem repetição mesmo em requisições simultâneas) e `codigo_verificacao` (UUID), além de `emitido_em` e `emitido_por`. `[D]` PA-008
- **QUANDO** consulto a turma, o histórico ou os participantes, **ENTÃO** cada inscrição **DEVE** trazer `certificado` (`numero`, `emitido_em`) ou `null`, e a turma **DEVE** trazer `certificados_emitidos` e `aptos_sem_certificado`. `[E]` regra do repo: contagens vêm do backend
- **SE** tento excluir (`DELETE`) uma turma ou uma inscrição com certificado emitido, **ENTÃO** o sistema **DEVE** recusar com 400 — turma com certificado se cancela, não se apaga; o documento está na mão da pessoa. `[E]` `docs/curso-cipa/MAPEAMENTO_CIPA_FASE2.md` seção 7b (decisão do dono, 2026-09-04)
- **SE** o usuário não tem nível `condomed`/`admin`, **ENTÃO** o sistema **DEVE** responder 403. `[E]` mesmo `IsCondomedOrAdmin` do viewset

### RF-HIS-006: PDF dos certificados e reemissão

**Como** operador, **quero** baixar os certificados da turma num único arquivo e qualquer certificado isolado depois, **para** imprimir tudo de uma vez no dia e reimprimir um quando pedirem.

- **QUANDO** consulto `GET cursos-cipa/{id}/certificados/pdf/`, **ENTÃO** o sistema **DEVE** devolver um único PDF com todos os certificados emitidos da turma, cada um em duas páginas (frente e verso), paisagem 16:9, `Content-Disposition` com nome `certificados-<codigo-da-turma>.pdf` exposto ao CORS. `[D]` ADR-0007
- **QUANDO** consulto `GET certificados/{numero}/pdf/`, **ENTÃO** o sistema **DEVE** devolver só aquele certificado, com o mesmo número e o mesmo conteúdo, regenerado do registro na hora — nada armazenado. `[D]` ADR-0007
- **QUANDO** o certificado é montado, **ENTÃO** a frente **DEVE** trazer logos e selo, o texto fixo com nome, CPF formatado, condomínio e CNPJ, cidade e **data do curso** por extenso, nome, título, registro MTE e assinatura do instrutor; o verso, o conteúdo programático de 8 itens; frente e verso com a **mesma** unidade emissora, a do local da turma; e o rodapé, `numero` e `codigo_verificacao`. `[D]` PA-008
- **QUANDO** a inscrição é corrigida depois da emissão (nome, condomínio), **ENTÃO** o próximo download **DEVE** refletir o registro atual, com o número inalterado. `[D]` ADR-0007
- **SE** a turma não tem certificado emitido, **ENTÃO** o PDF da turma **DEVE** responder 404 — diferente da lista de presença, aqui não há o que imprimir. `[E]` `docs/curso-cipa/MAPEAMENTO_CIPA_FASE2.md` seção 5, regra 3
- **SE** o usuário não tem nível `condomed`/`admin`, **ENTÃO** o sistema **DEVE** responder 403. `[E]` mesmo `IsCondomedOrAdmin`

**Verificação prevista (detalhada no design, após aprovação):** CT-HIS-007 — lote emite só presentes, pula ausente e `null`, separa impedidos por CNPJ, recusa sem instrutor/assinatura, recusa cancelada e sem presença, idempotente, número sequencial por ano sem colisão em concorrência, contagens na turma, `DELETE` de turma/inscrição com certificado → 400, `usuario` → 403. CT-HIS-008 — PDF da turma com duas páginas por certificado e nome de arquivo exposto; PDF individual pelo número; conteúdo reflete inscrição corrigida com número igual; turma sem certificado → 404.

## Requisitos Não Funcionais

**Verificação prevista (detalhada no design, após aprovação):** CT-HIS-006 — lote grava presente/ausente com auditoria e vira a turma `realizada`; id fora da turma → 400 sem gravar nada; regravar aceito; `cancelada` → 400; data futura → 400; contagens `presentes`/`ausentes`/`sem_registro` na turma; inscrito novo em turma realizada nasce `null`; `usuario` → 403.

### RNF-HIS-002: Presença é fato auditável

Toda gravação de presença registra quem e quando; regravar sobrescreve o valor mas mantém a auditoria da última gravação. Nada de presença é apagado por retenção: o histórico guarda tudo. `[D]` PA-007



### RNF-HIS-001: Paginação com teto

25 por página por padrão; `page_size` até 100. Acima disso o servidor corta. `[E]` `PaginacaoHistorico`

### RNF-HIS-003: Certificado é registro imutável e auditável

`numero` e `codigo_verificacao` são únicos no banco; `emitido_em` e `emitido_por` nunca mudam; um certificado nunca é apagado por exclusão de turma ou inscrição (a aplicação recusa a exclusão — RF-HIS-005). O PDF é derivado e pode mudar de layout; o registro não. `[D]` ADR-0007

## Questões em Aberto

- PA-007: perguntas ao solicitante sobre presença e certificado (carga horária, texto, assinatura, numeração, prazo de presença). Travam as fases C e D; não travam esta.
- PA-012: emissão em lote com inscritos impedidos (sem CNPJ) — trava um critério de RF-HIS-005.
- PA-010/PA-011 (`specs/curso-cipa-cadastros/`): o certificado passa a ler instrutor e local do cadastro; a fase D depende dessa spec.
