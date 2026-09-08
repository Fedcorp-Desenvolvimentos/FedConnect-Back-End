# Mapeamento — Cursos CIPA, fase 2: histórico, consulta e documentos

**Origem:** reunião com o solicitante da ferramenta, 04/09/2026
**Status:** proposta para discussão — nada aqui é spec aprovada; vira `requirements.md` nos dois repos depois das respostas da seção 7
**Repos:** FedConnect-Back-End (Django) · FedConnect-FrontEnd-Prod (React)

---

## 1. O pedido, traduzido

| # | Pedido | O que já existe | O que falta |
|---|---|---|---|
| 1 | Histórico de turmas anteriores | Turmas ficam no banco com situação (`agendada`/`realizada`/`cancelada`); a tela mostra **um mês por vez** e o filtro é só de local/situação | Uma lista por período, paginada, com filtros que a agenda não tem (administradora, condomínio, nome/CPF de participante) |
| 2 | Local de consulta de turmas e funcionários | `verificar-cpf` já responde "em quais turmas este CPF está"; a turma já devolve `administradoras` e `condominios` derivados | Uma página de consulta, e o `verificar-cpf` generalizado para buscar por nome, condomínio e administradora |
| 3.1 | Lista de presença para assinatura no dia | Todos os dados (nome, CPF, condomínio, administradora, função) já estão na inscrição | O PDF |
| 3.2 | Confirmação de presença no sistema, depois do curso | Nada — a inscrição não sabe se a pessoa foi | Campo de presença, tela para marcar e a regra de quando a turma vira `realizada` |
| 3.3 | Emissão de certificado | Nada | Modelo de certificado (número, data, quem emitiu), o PDF e as regras de quem recebe |

A ordem de dependência é rígida: **certificado depende de presença, presença depende de a turma ter acontecido, e tudo isso precisa de um lugar para ser feito — a página de histórico/detalhe.** Por isso a proposta começa pela página.

---

## 2. Onde isso mora: páginas e atalhos

A tela atual (`/condomed/cursos-cipa`) é uma **agenda**: calendário do mês, criar turma, inscrever. Ela é boa para o antes do curso e ruim para o depois — não tem onde listar seis meses de turmas nem onde marcar presença. Encaixar histórico e documentos no modal de inscritos deixaria o modal com quatro responsabilidades.

Proposta: **uma segunda página, com detalhe por turma.**

```
/condomed                          home da área (já existe)
├── card "Cursos CIPA"             → /condomed/cursos-cipa      agenda (já existe)
└── card "Turmas e participantes"  → /condomed/turmas           NOVO: histórico + consulta
                                      └── /condomed/turmas/:id   NOVO: detalhe da turma
                                            abas: Participantes · Presença · Documentos
```

**`/condomed/turmas` — histórico e consulta, na mesma página, em duas abas:**

- **Turmas**: lista paginada, filtros de período (padrão: últimos 6 meses), local, situação, administradora, condomínio. Cada linha: data, local, ocupação, situação, quantos presentes, quantos certificados. Clique → detalhe.
- **Participantes**: busca por nome, CPF, condomínio ou administradora. Resultado é uma linha por **inscrição** (a mesma pessoa em três turmas são três linhas), com data, local, presença e certificado. Clique → detalhe da turma, com a pessoa destacada.

**`/condomed/turmas/:id` — detalhe da turma:**

- **Participantes**: a mesma lista do modal de hoje, sem modal. Adicionar/editar/remover continua funcionando aqui (a agenda não perde nada; ganha um segundo caminho).
- **Presença**: aparece a partir do dia da turma. Lista com marcação presente/ausente, "marcar todos", salvar em lote. Ao salvar pela primeira vez, a turma passa a `realizada`.
- **Documentos**: baixar lista de presença (sempre); emitir certificados (só com presença registrada, só para presentes); baixar certificados já emitidos, individual ou em lote.

**Atalhos:**

- Na **home da Condomed**: o card novo — é o padrão da área e custa um objeto no array.
- Na **agenda**: a etiqueta da turma no calendário e o painel de inscritos ganham "Ver detalhe" → `/condomed/turmas/:id`. É de lá que o operador vai sair para marcar presença no dia seguinte.
- Na **home principal do sistema** (`/home`): ela é um carrossel de banners, não uma grade de atalhos — um "atalho" ali seria um banner. Não recomendo; o menu lateral "Condomed" já leva à home da área em um clique. Se o solicitante quiser mesmo, é um banner no carrossel apontando para `/condomed/turmas`.

---

## 3. Modelo de dados

### `InscricaoCipa` ganha presença

| Campo | Tipo | Regra |
|---|---|---|
| `presenca` | `BooleanField(null=True)` | `null` = não registrada, `True` presente, `False` ausente. Três estados, porque "não marcado" é diferente de "faltou" |
| `presenca_registrada_em` | `DateTimeField(null=True)` | quando marcou |
| `presenca_registrada_por` | FK `Usuario` (null) | quem marcou |

### `CertificadoCipa` (novo)

Um registro por certificado emitido, e não só um PDF gerado na hora: a Condomed precisa saber **que** certificado existe, com **que número**, emitido **por quem** — e reemitir o mesmo documento meses depois sem mudar o número.

| Campo | Tipo | Regra |
|---|---|---|
| `inscricao` | OneToOne `InscricaoCipa` | uma pessoa, uma turma, um certificado |
| `numero` | `CharField`, único | sequencial por ano: `CIPA-2026-000123` |
| `codigo_verificacao` | `UUIDField`, único | impresso no rodapé; permite conferir autenticidade sem expor o número sequencial |
| `carga_horaria_horas` | `DecimalField` | copiada da turma no momento da emissão — se a regra mudar, certificados antigos não mudam |
| `emitido_em`, `emitido_por` | data e FK | auditoria |

O PDF **não** é armazenado: é regenerado a partir do registro. Mudança de layout se aplica a reemissões; o conteúdo (número, nome, data, carga) é o do registro.

### `TurmaCipa` — dois campos a decidir

| Campo | Por quê | Depende de |
|---|---|---|
| `carga_horaria_horas` | O certificado precisa dizer. Hoje o horário é fixo 09:00–17:30 (8h30 corridas) — a carga oficial descontando almoço é decisão do solicitante | Q1 |
| `instrutor` (nome + registro) | Lista de presença e certificado costumam levar assinatura do responsável. O campo foi **retirado do escopo pelo dono em 31/08** (PA-002) — os documentos reabrem a questão | Q3 |

**Migração:** os três campos de presença e a tabela de certificado são aditivos, sem risco para o que existe. Os dois campos da turma dependem das respostas.

---

## 4. Endpoints

### Histórico e consulta

| Rota | O que faz | Observação |
|---|---|---|
| `GET cursos-cipa/historico/?data_inicio&data_fim&local&status&administradora&condominio&page` | Lista paginada de turmas com contagens (inscritos, presentes, certificados) | **Rota nova, não mexer na atual**: a agenda depende de `GET cursos-cipa/` devolver o mês inteiro sem paginação |
| `GET cursos-cipa/participantes/?busca&cpf&condominio&administradora&page` | Inscrições em todas as turmas, com dados da turma e presença/certificado | Generaliza o `verificar-cpf`, que continua existindo para a tela de inscrição |

### Presença

| Rota | O que faz | Regras |
|---|---|---|
| `POST cursos-cipa/{id}/presenca/` | `{presencas: [{inscricao_id, presente}]}` em lote, atômico | Só a partir do dia da turma; recusa em turma `cancelada`; primeira gravação muda a turma para `realizada`; regrava sem apagar histórico (`registrada_em`/`por` atualizam) |

### Documentos

| Rota | O que faz | Regras |
|---|---|---|
| `GET cursos-cipa/{id}/lista-presenca.pdf` | Lista para assinatura no dia | Sempre disponível, inclusive antes do curso (é para levar impressa). Ordenada por condomínio, depois nome — a assinatura acontece em bloco por condomínio. **Linhas extras em branco no fim**, porque chegam funcionários de última hora (ADR-0006 do back): o que entrou à mão vira inscrição depois |
| `POST cursos-cipa/{id}/certificados/` | Emite para todos os presentes que ainda não têm certificado; devolve a lista | Recusa se não há presença registrada; nunca emite para ausente ou não marcado; idempotente (chamar de novo não duplica) |
| `GET cursos-cipa/{id}/certificados.pdf` | Todos os certificados da turma, um por página | Para imprimir de uma vez |
| `GET certificados/{numero}.pdf` | Um certificado, reemissão | Mesmo número, mesmo conteúdo |
| `GET certificados/verificar/{codigo}/` | Confere autenticidade pelo código do rodapé | Candidato a ficar **fora** desta fase — exige rota sem login e política própria |

Todos sob `IsCondomedOrAdmin`, como o resto.

### PDF: com o que gerar

O back já usa **ReportLab** (`fedhub/views/faturas_view.py`, boletos, e-mails) — é o padrão do repo, e serve para os dois documentos. O FedHub tem um módulo de PDF com Chromium, mas ele é para os documentos do Firebird e fica atrás do túnel; não vale a dependência por dois PDFs simples.

---

## 5. Regras que precisam ficar escritas

1. **Presença só existe depois do curso.** A aba aparece a partir da data da turma; antes disso, não há o que marcar.
2. **Turma vira `realizada` ao registrar presença**, não à mão. Hoje o operador pode marcar `realizada` no formulário sem ninguém ter ido — a fase 2 tira essa opção do formulário e deixa o sistema inferir.
3. **Certificado só para presente.** Não marcado (`null`) não recebe: a omissão não pode virar certificado.
4. **Um certificado por inscrição, número imutável.** Reemitir é baixar de novo, não gerar outro.
5. **Turma cancelada não emite nada** — nem lista de presença faz sentido, mas a lista é inofensiva; o certificado não.
6. **Quem chegou de última hora e assinou a lista à mão** precisa virar inscrição no sistema antes da presença — senão não tem certificado. A lista de presença impressa com linhas extras é o lembrete disso.
7. **Excluir turma com certificados emitidos:** bloquear, ou exigir confirmação mais forte. Apagar turma `realizada` com certificados apaga o rastro de um documento que a pessoa tem na mão. Proposta: **bloquear** — cancela-se, não se exclui.

---

## 6. Fases de entrega, na ordem

Cada fase é um PR nos dois repos e fica utilizável sozinha.

| Fase | Entrega | Depende de | Tamanho |
|---|---|---|---|
| **A** | Página `/condomed/turmas` (histórico + consulta), detalhe com aba Participantes, card na home, "ver detalhe" na agenda; `historico/` e `participantes/` no back | — | ~2 dias |
| **B** | Lista de presença em PDF (aba Documentos, só esse botão) | A | ~½ dia |
| **C** | Presença: campos, `presenca/`, aba Presença, turma `realizada` automática, opção manual sai do formulário | A | ~1 dia |
| **D** | Certificados: modelo, numeração, emissão em lote, reemissão, PDF individual e em lote; bloqueio de exclusão com certificado | C + respostas Q1–Q4 | ~2 dias |
| **E** (opcional) | Verificação pública de certificado por código | D + decisão sobre rota sem login | ~½ dia |

A e B saem sem nenhuma resposta do solicitante. **C e D travam nas perguntas abaixo.**

---

## 7. Perguntas para o solicitante (antes de escrever a spec)

> **Decisões do dono, 04/09 (seção 7 de `ANALISE_CERTIFICADO_CIPA.md`):** numeração sim; unidade única vinda do local; data do curso; CNPJ obrigatório só para emitir; instrutores fixos no código com select na turma (sem cadastro editável); certificado só para download. Respondem Q3, Q4, Q9, Q12, Q13 e Q14.
>
> **Atualização 04/09, fim do dia:** os dois modelos de certificado em Word (`CERTIFICADOS 03.12.docx`, `CERTIFICADOS CIPA - VINICIUS.docx`) foram lidos — análise completa em `ANALISE_CERTIFICADO_CIPA.md`. Eles **respondem Q1, Q2, Q3 e Q5** (não há carga horária no modelo; o texto, a base legal e o conteúdo programático são fixos; o instrutor assina com assinatura digitalizada; layout paisagem 16:9 em duas páginas com logos CondoMed e CondoCorp) e **abrem três perguntas novas**, Q12–Q14, ao fim desta seção. O cadastro precisa de CNPJ do condomínio, instrutor com registro MTE e assinatura, e unidade/cidade por local — detalhado na análise, seção 3.

**Certificado — travam a fase D**

- **Q1. Carga horária.** O curso é 09:00–17:30. Quantas horas vão no certificado — 8h, 8h30, 8h descontando almoço? É sempre a mesma?
- **Q2. Texto.** O que o certificado precisa dizer? Nome do curso ("Curso de capacitação para membros da CIPA"?), menção a norma (NR-5?), conteúdo programático? Existe um modelo em papel hoje que sirva de referência?
- **Q3. Assinatura.** Quem assina — o técnico que ministrou, o responsável técnico da Condomed, os dois? Isso reabre o campo de instrutor na turma (retirado em 31/08). Assinatura digitalizada no PDF ou espaço para assinar à mão?
- **Q4. Numeração.** Sequencial por ano (`CIPA-2026-000123`) serve? Já existe uma numeração em uso que precise continuar?
- **Q5. Logo e layout.** Marca da Condomed, da Fedcorp, ou as duas? Retrato ou paisagem?

**Presença — travam a fase C**

- **Q6. Prazo.** Presença pode ser marcada em qualquer momento depois do curso, ou há limite (ex.: 30 dias)?
- **Q7. Presença parcial.** Existe "veio só de manhã"? Se sim, conta como presente para o certificado?
- **Q8. Quem marca.** Qualquer usuário `condomed`, ou só quem ministrou?

**Documentos em geral**

- **Q9. Envio.** Certificado é só para baixar/imprimir, ou vai por e-mail para o participante (o e-mail é opcional na inscrição hoje)?
- **Q10. Lista de presença.** Quantas linhas em branco extras no fim — 5? 10? E precisa de campo para horário de chegada/saída?

**Histórico**

- **Q11. Retenção.** Tudo fica para sempre, ou turmas com mais de X anos saem da lista padrão?

---

**Abertas pela leitura dos modelos de certificado**

- **Q12. Unidade emissora.** Os dois modelos têm cabeçalho CONDOMED SÃO PAULO na frente, CONDOMED RIO no verso, e a data diz "Rio de Janeiro". A frente em SP é intencional? (Tudo indica defeito do modelo.)
- **Q13. Data impressa.** É a data em que o curso aconteceu ou a data em que o certificado foi emitido? Recomendação: a do curso, guardando a de emissão para auditoria.
- **Q14. CNPJ do condomínio.** Obrigatório para inscrever, ou só para emitir o certificado? Recomendação: só para emitir — senão o funcionário extra de última hora não entra.

## 7b. Fechamento de 04/09 — o que foi decidido e o que segue como hipótese

Respondidas pelo dono: Q1–Q5 (pelos modelos em Word) e Q12–Q14 (seção 7 de `ANALISE_CERTIFICADO_CIPA.md`). Recomendações adotadas com "pode seguir": turma vira `realizada` ao registrar presença e a opção manual sai do formulário (Q10); turma com certificado emitido **não pode ser excluída**, só cancelada (item 14 da lista de pendências); sem banner na home principal (15); PA-003 fechada — o CNPJ com consulta à Receita resolve o condomínio (16).

Sem resposta, seguem como **hipótese declarada** até o solicitante dizer o contrário (convenção: `[P]` na spec, PA aberta):

| # | Pergunta | Hipótese de trabalho |
|---|---|---|
| Q6 | Prazo para marcar presença | Sem prazo; a data de registro fica gravada |
| Q7 | Presença parcial | Não existe: presente ou ausente. Quem veio meio período é decisão do instrutor na hora de marcar |
| Q8 | Quem marca | Qualquer usuário `condomed` ou `admin` — o mesmo gate do resto da área |
| Q10 (lista) | Linhas em branco extras na lista de presença | 5 linhas, sem coluna de horário |
| Q11 | Retenção do histórico | Tudo fica; o filtro padrão é só de exibição |

**Implementado em 04/09 (working tree, sem commit):** CNPJ do condomínio na inscrição, na planilha e na prévia; instrutores fixos com select na turma e na importação; unidade emissora por local; assets do certificado versionados em `condomed/assets/`. Pronto para a fase D começar pela emissão do PDF.

## 8. O que este mapeamento não cobre, de propósito

- Integração com faturamento/comercialização do curso (PA-005, fora do escopo desde a primeira spec).
- Cadastro de funcionários reaproveitável entre turmas — os dados seguem por inscrição. Se o histórico mostrar a mesma pessoa em muitas turmas com dados divergentes, aí vale reabrir.
- Notificação automática (lembrete do curso, aviso de certificado pronto) — PA-003, fora do escopo.
