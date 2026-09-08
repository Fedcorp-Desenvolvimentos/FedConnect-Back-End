# Análise — os certificados CIPA em Word e o que falta no cadastro

**Fontes:** `CERTIFICADOS 03.12.docx` (instrutor Felipe) e `CERTIFICADOS CIPA - VINICIUS.docx` (instrutor Vinicius), originalmente na raiz do workspace (fora de qualquer git)
**Lida em:** 04/09/2026 · CPFs e nomes dos participantes mascarados neste documento (dados pessoais; os originais estão só nos .docx) · **Para:** decidir o que muda em `TurmaCipa`/`InscricaoCipa` antes da fase D (certificado) do `MAPEAMENTO_CIPA_FASE2.md`
**Status:** análise concluída e decisões tomadas (seção 7). O cadastro da seção 5 (CNPJ, instrutores fixos, unidade por local) está **implementado no working tree** dos dois repos em 04/09 — sem commit, por instrução do dono. A emissão do PDF (fase D) não começou.

---

## 1. O que o certificado é, fisicamente

Os dois arquivos são o **mesmo modelo** com dados diferentes. Cada certificado tem **duas páginas**, formato **paisagem 16:9** (33,9 × 19,1 cm — proporção de slide, não A4):

| Página | Conteúdo | Cabeçalho (texto branco sobre faixa) |
|---|---|---|
| **1 — Frente** | Logo CondoMed, logo CondoCorp, selo dourado "CondoMed", título "Certificado", texto principal, data e local, bloco do instrutor com **assinatura digitalizada** | CONDOMED **SÃO PAULO** — Rua Coronel Oscar Porto, 800, 1º andar, Paraíso/SP — condocorp@grupofedcorp.com.br |
| **2 — Verso** | "CONTEÚDO PROGRAMÁTICO:" com 8 itens fixos | CONDOMED **RIO** — Rua da Alfândega, 108, 7º andar, Centro/RJ — (21) 2516-6001 — condocorp@grupofedcorp.com.br |

**Texto principal** (idêntico nos dois, só os dados mudam):

> Certificamos que **{NOME}** portador do CPF **{CPF}** funcionário da **{CONDOMÍNIO}** de CNPJ **{CNPJ}** concluiu os treinamentos para Representante Nomeado da NR5 - CIPA, NR6 Equipamento de Proteção Individual - EPI e Noções Básicas de Primeiros Socorros conforme as exigências estabelecidas pela Portaria MTP nº 4.219, de 20 de Dezembro de 2022.

> **{CIDADE}**, **{DATA POR EXTENSO}**.
> INSTRUTOR DO CURSO **{NOME DO INSTRUTOR}**
> Técnico em Segurança no Trabalho
> MTE **{REGISTRO}**

**Conteúdo programático** (fixo, os 8 itens da NR-5 — igual nos dois arquivos):

1. estudo do ambiente, das condições de trabalho, bem como dos riscos originados do processo produtivo;
2. noções sobre acidentes e doenças relacionadas ao trabalho decorrentes das condições de trabalho e da exposição aos riscos existentes no estabelecimento e suas medidas de prevenção (NOÇÕES BÁSICAS DE PRIMEIROS SOCORROS)
3. metodologia de investigação e análise de acidentes e doenças relacionadas ao trabalho;
4. princípios gerais de higiene do trabalho e de medidas de prevenção dos riscos (APR/EPI/EPC);
5. noções sobre as legislações trabalhista e previdenciária relativas à segurança e saúde no trabalho;
6. noções sobre a inclusão de pessoas com deficiência e reabilitados nos processos de trabalho;
7. organização da CIPA e outros assuntos necessários ao exercício das atribuições da Comissão; e
8. prevenção e combate ao assédio sexual e a outras formas de violência no trabalho.

**Imagens embutidas:** logo CondoMed (com o slogan "Medicina Ocupacional e Segurança do Trabalho"), logo CondoCorp Serviços, o selo dourado, e a **assinatura digitalizada do instrutor** — uma por documento, diferente entre Felipe e Vinicius.

---

## 2. Dado a dado: o que o certificado pede × o que o sistema tem

| Dado no certificado | Exemplo (Felipe) | Exemplo (Vinicius) | Onde está hoje | Situação |
|---|---|---|---|---|
| Nome do participante | A. L. S. (participante 1) | M. F. C. C. (participante 2) | `InscricaoCipa.nome` | ✅ temos |
| CPF | 992.***.***-04 | 012.***.***-20 | `InscricaoCipa.cpf` (11 dígitos; a máscara é da tela) | ✅ temos |
| Nome do condomínio | CONDOMINIO DO EDIFICIO SION | COND. EURICO LISBOA | `InscricaoCipa.condominio_nome` (digitado) | ✅ temos — mas ver §3.1 |
| **CNPJ do condomínio** | 01.998.690/0001-82 | 01.580.092/0001-99 | — | 🔴 **não temos** |
| Nome dos treinamentos | fixo | fixo | — | texto fixo do modelo |
| Base legal | Portaria MTP nº 4.219, de 20/12/2022 | idem | — | texto fixo do modelo |
| **Cidade da emissão** | Rio de Janeiro | Rio de Janeiro | — | 🔴 **não temos** (ver §3.3) |
| **Data da emissão** | 28 de Agosto de 2026 | 11 de Agosto de 2026 | — | 🟡 é a data da turma ou a da emissão? (ver §3.4) |
| **Nome do instrutor** | FELIPE BARBOZA DE OLIVEIRA | VINICIUS DOS SANTOS PINTO | — | 🔴 **não temos** (retirado do escopo em PA-002) |
| **Título do instrutor** | Técnico em Segurança no Trabalho | idem | — | 🔴 não temos (parece fixo, mas é do instrutor) |
| **Registro MTE** | MTE/RJ/0060169 | MTE: 0056876/RJ | — | 🔴 **não temos** — e o formato varia entre os dois |
| **Assinatura digitalizada** | imagem (PNG) | imagem (JPEG) | — | 🔴 **não temos** — arquivo por instrutor |
| Conteúdo programático | 8 itens | 8 itens | — | texto fixo do modelo |
| Logos e selo | 3 imagens | 3 imagens | — | assets fixos do modelo |
| **Unidade CondoMed (SP/RJ)** | frente SP, verso RJ | frente SP, verso RJ | — | 🟡 ver §3.3 — parece defeito do modelo |
| Número do certificado | — | — | — | o modelo **não tem** numeração |
| Carga horária | — | — | — | o modelo **não tem** carga horária |

Resumo: dos dados variáveis, **temos 3 (nome, CPF, condomínio) e faltam 6** (CNPJ, cidade, instrutor, título, registro MTE, assinatura). Data depende de decisão.

---

## 3. O que precisa mudar no cadastro

### 3.1 CNPJ do condomínio — na inscrição, com preenchimento assistido

O certificado cita o condomínio **com CNPJ**. Hoje o condomínio é só um nome digitado por inscrição (ADR-0004; e a PA-003 registra que não existe fonte de condomínios no FedHub/Firebird).

**Proposta:** `InscricaoCipa` ganha `condominio_cnpj` (14 dígitos, validado). Para não virar mais um campo digitado à mão 30 vezes:

- o formulário do inscrito e a planilha ganham a coluna CNPJ;
- a **repetição do vínculo** que já existe (o próximo inscrito herda administradora e condomínio do anterior) passa a repetir também o CNPJ — na prática se digita uma vez por condomínio;
- o sistema já tem **consulta de CNPJ** (`/consultas/realizar/`, usada pela tela Consulta CNPJ): digitou o CNPJ, o sistema busca e **sugere a razão social** no campo de condomínio. Isso ainda resolve um problema que o certificado deixa evidente: "CONDOMINIO DO EDIFICIO SION" e "COND. EURICO LISBOA" são grafias livres — com o CNPJ, o nome pode vir da Receita e sair padronizado no documento.

O CNPJ deve ser **obrigatório?** Para o certificado, sim. Para a inscrição em si, depende: se for obrigatório, ninguém entra sem CNPJ — inclusive o funcionário extra de última hora que motivou o ADR-0006. **Recomendação:** opcional na inscrição, **obrigatório para emitir o certificado** — a fase D lista quem está sem CNPJ antes de emitir, como já vai listar quem está sem presença.

### 3.2 Instrutor — cadastro próprio, com assinatura

O certificado leva nome, título, registro MTE e **assinatura digitalizada** do instrutor. Isso não cabe em três campos de texto na turma, por três motivos: a assinatura é um arquivo; o mesmo instrutor dá dezenas de turmas; e o registro MTE hoje está grafado de dois jeitos nos dois modelos (`MTE/RJ/0060169` × `MTE: 0056876/RJ`) — cadastro é o que padroniza.

**Proposta:** modelo `InstrutorCipa` — `nome`, `titulo` (padrão "Técnico em Segurança no Trabalho"), `registro_mte` (número), `registro_uf` (RJ), `assinatura` (imagem), `ativo`. `TurmaCipa` ganha `instrutor` (FK, opcional na criação, **obrigatório para emitir certificado**). Tela: um select de instrutor no formulário da turma; o cadastro de instrutores fica no Django admin nesta fase (são duas ou três pessoas), com tela própria só se a operação pedir.

Isso **reabre a PA-002 do backend** — o campo de técnico instrutor foi retirado do escopo pelo dono em 31/08. O certificado é o motivo concreto para voltar.

### 3.3 Unidade emissora e cidade — provável defeito do modelo

Os dois arquivos têm o cabeçalho **CONDOMED SÃO PAULO** na frente e **CONDOMED RIO** no verso, e a data diz **"Rio de Janeiro"**. Instrutores com registro no RJ, curso no auditório da matriz — o certificado é do Rio; a página da frente está com o cabeçalho de São Paulo. Tudo indica que o modelo foi montado a partir de um arquivo de SP e ninguém trocou a faixa da frente.

**Para o sistema:** a unidade (endereço da faixa) e a cidade da data devem vir de um lugar só — `LOCAIS_CIPA` já é o registro dos locais (auditório e sala, ambos na matriz). Proposta: acrescentar a cada local `unidade` (nome, endereço, telefone, e-mail) e `cidade`, e o certificado usa o do local da turma. Frente e verso com a **mesma** unidade. **Confirmar com o solicitante** se a frente em SP é intencional (improvável) — Q12, abaixo.

### 3.4 Data — da turma ou da emissão?

Nos exemplos, "Rio de Janeiro, 28 de Agosto de 2026" e "11 de Agosto de 2026". Não dá para saber, só pelo arquivo, se é a data em que o curso aconteceu ou a data em que o certificado foi feito. Para o sistema a diferença importa: emitir três meses depois muda o que sai impresso.

**Recomendação:** data da **turma** (é o que o certificado atesta: que a pessoa fez o curso naquele dia), guardando `emitido_em` no registro do certificado para auditoria. Confirmar — Q13.

### 3.5 O que o modelo **não** tem — e que o mapeamento previa

- **Número do certificado** — o modelo não numera. O mapeamento propôs `CIPA-2026-000123` + código de verificação; continua valendo como melhoria (a Condomed não tem hoje como provar que emitiu um certificado específico), mas é decisão do solicitante acrescentar algo que o documento atual não tem. Q4 do mapeamento fica em pé.
- **Carga horária** — o modelo não menciona horas. Isso **responde a Q1**: se o certificado atual não traz carga horária, o sistema não precisa inventar uma. Fica opcional; se quiserem incluir, é uma linha no texto.

---

## 4. O que os arquivos respondem das 11 perguntas do mapeamento

| Pergunta | Situação depois de ler os arquivos |
|---|---|
| Q1 — Carga horária | **Respondida por omissão:** o modelo não tem. Não inventar. |
| Q2 — Texto e base legal | **Respondida:** texto integral acima; base legal Portaria MTP 4.219/2022; conteúdo programático com 8 itens. Tudo fixo. |
| Q3 — Assinatura | **Respondida:** o instrutor da turma assina, com **assinatura digitalizada** (imagem). Reabre PA-002. |
| Q4 — Numeração | **Aberta:** o modelo não numera. Acrescentar é decisão. |
| Q5 — Logo e layout | **Respondida:** CondoMed + CondoCorp + selo; paisagem 16:9; duas páginas. Assets extraídos em scratchpad para reproduzir. |
| Q6–Q8 — Presença | Não tratam de presença; seguem abertas. |
| Q9 — Envio por e-mail | Segue aberta. |
| Q10 — Lista de presença | Segue aberta. |
| Q11 — Retenção | Segue aberta. |
| **Q12 (nova)** — A frente com cabeçalho SÃO PAULO e a data "Rio de Janeiro" é intencional? | Provável defeito do modelo. Confirmar. |
| **Q13 (nova)** — A data impressa é a do curso ou a da emissão? | Confirmar. Recomendação: do curso. |
| **Q14 (nova)** — CNPJ do condomínio obrigatório na inscrição, ou só para emitir? | Recomendação: só para emitir. |

---

## 5. Ordem sugerida — o que dá para fazer já

Sem resposta a Q12–Q14 e sem reabrir PA-002, a fase D não anda. Mas há trabalho de cadastro que **não depende de resposta**, e que a fase D vai precisar de qualquer jeito:

1. **`condominio_cnpj` na inscrição** (opcional), na tela, na planilha modelo e na importação, com preenchimento assistido pela consulta de CNPJ existente. É a mudança de cadastro que o solicitante citou.
2. **`InstrutorCipa` + `TurmaCipa.instrutor`** (opcional na criação). Cadastro no Django admin. Isso é a reabertura formal da PA-002, com o certificado como motivo.
3. **`unidade`/`cidade` em `LOCAIS_CIPA`**, com os dois locais apontando para a matriz no Rio — corrigível se Q12 disser o contrário.

Os três são aditivos (migração sem risco para o que existe) e deixam a emissão do certificado a um passo: ler o registro, montar as duas páginas com ReportLab sobre os assets extraídos. As decisões que faltam (Q4, Q12–Q14, Q6–Q8 de presença) são do solicitante.

---

## 6. Observações de qualidade nos modelos atuais

Vale levar ao solicitante junto com as perguntas, porque o sistema vai reproduzir o que for decidido:

- Cabeçalho SP na frente e RJ no verso (§3.3).
- Registro MTE em dois formatos (`MTE/RJ/0060169` × `MTE: 0056876/RJ`).
- No modelo do Vinicius, "CPF" e "CNPJ" têm espaços a mais antes do número — resquício de preencher à mão.
- "Noções Basicas" sem acento no texto principal (nos dois arquivos).
- Nomes de condomínio em grafia livre e abreviada ("COND. EURICO LISBOA"). Com CNPJ, o nome pode vir padronizado.

---

## 7. Decisões do dono — 04/09/2026

| # | Pergunta | Decisão |
|---|---|---|
| Q4 | Numeração | **Sim**: número sequencial por ano (`CIPA-2026-000123`) e código de verificação no rodapé |
| Q12 | Unidade emissora | Frente e verso da **mesma unidade**, vinda do local da turma (matriz = Rio). A frente em SP era defeito do modelo |
| Q13 | Data impressa | **Data do curso**; `emitido_em` guardado para auditoria |
| Q14 | CNPJ do condomínio | **Opcional para inscrever, obrigatório para emitir** |
| Q3 | Instrutor | **Sem cadastro editável** — evita cadastro errado. Os instrutores dos certificados existentes (Felipe Barboza de Oliveira, MTE/RJ 0060169; Vinicius dos Santos Pinto, MTE/RJ 0056876) entram **fixos no código**, com assinatura como asset do repositório, e o usuário escolhe num select da turma qual sai no certificado |
| Q9 | Envio | **Só download**; sem envio por e-mail por enquanto (não há base de envio) |

**Consequência para o modelo:** em vez de `InstrutorCipa` como tabela, `INSTRUTORES_CIPA` como constante em `condomed/models.py` (mesmo padrão de `LOCAIS_CIPA`) e `TurmaCipa.instrutor` como `CharField` com choices. Um instrutor novo é uma linha no código e uma imagem no repo — decisão de desenvolvimento, não de operação, que é o que o dono quer.

**Atenção à assinatura do Vinicius:** a imagem embutida no Word tem 3 KB (177×70 px) — baixa resolução para impressão. Vale pedir o arquivo original antes da fase D.
