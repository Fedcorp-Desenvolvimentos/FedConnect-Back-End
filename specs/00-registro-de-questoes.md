# Registro de questões abertas

> **Atualizado:** 2026-08-31

Toda `PA-###` citada em qualquer spec deste repositório nasce e vive aqui. Questão fechada não some: recebe status `fechada`, a resposta e a data. O número nunca é reciclado.

Formato de cada entrada: título, status (`aberta` | `fechada`), dono, severidade (`bloqueia` | `alta` | `média` | `baixa`), o que trava, e — quando fechada — a resposta.

---

## PA-001 — Capacidade real dos locais

- **Status:** fechada (2026-08-31) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** RF-CIP-003 (limite de inscritos por turma).
- **Questão:** quantas pessoas cabem no auditório e na sala de reunião? Hipótese de trabalho: constante `LOCAIS_CIPA` com valores provisórios a confirmar com a Condomed.
- **Resposta (2026-08-31):** auditório 30 lugares, sala de reunião 10. Valores fixados em `condomed/models.py` (`LOCAIS_CIPA`).

## PA-002 — Campos do inscrito e identidade do técnico

- **Status:** fechada (2026-08-31) · **Dono:** Ingrid Aylana · **Severidade:** média
- **Trava:** RF-CIP-003 (formulário de inscritos), RF-CIP-001 (campo técnico).
- **Questão:** os campos do funcionário do condomínio são nome, CPF, função, e-mail e telefone — falta algum (RG, data de nascimento para certificado)? O técnico instrutor é usuário do sistema (nível `condomed`) ou nome livre? Hipótese: usuário do sistema, nullable.
- **Resposta (2026-08-31):** os cinco campos bastam (nome, CPF, função, e-mail, telefone); não há cadastro de funcionários. O campo de técnico instrutor foi **retirado** do escopo (decisão do dono, 2026-08-31) — assim como o código do condomínio, que passa a ser só o nome digitado.

## PA-003 — Notificação ao cliente / lista de presença / certificado

- **Status:** aberta · **Dono:** Ingrid Aylana · **Severidade:** baixa
- **Trava:** nada no escopo inicial.
- **Questão:** a turma agendada deve gerar e-mail ao condomínio/administradora, lista de presença ou certificado? Se sim, é spec própria; padrão de e-mail a copiar é `questionarios/views.py:_enviar_email` (via FedHub, timeout curto).

## PA-004 — Agenda atual sem validação de conflito no servidor

- **Status:** aberta · **Dono:** Ingrid Aylana · **Severidade:** média
- **Trava:** nada no CIPA (que valida no servidor e consulta as Reservas); é dívida pré-existente da `agenda`.
- **Questão:** `agenda/serializers.py` não tem `validate()` e o model não tem constraint — duas reservas conflitantes entram por POST direto ou abas simultâneas. Corrigir na agenda (spec própria) ou aceitar?

## PA-005 — Vínculo do curso com a comercialização

- **Status:** aberta · **Dono:** Ingrid Aylana · **Severidade:** baixa
- **Trava:** nada no escopo inicial.
- **Questão:** o curso CIPA é produto vendido — a turma precisa se ligar a proposta/contrato/fatura (Firebird) para controle de faturamento? Fora do escopo até decisão.

## PA-006 — Uma turma atende um condomínio ou vários?

- **Status:** fechada (2026-09-04) · **Dono:** Ingrid Aylana · **Severidade:** bloqueia
- **Trava:** o modelo de dados de `TurmaCipa` e `InscricaoCipa`.
- **Questão:** o levantamento inicial tratou a turma como "o curso de um condomínio", com administradora e condomínio na turma. Uma turma pode receber funcionários de administradoras diferentes?
- **Resposta:** sim, e é a regra, não a exceção. A turma é um dia de curso em um local; as vagas são preenchidas com funcionários de várias administradoras e condomínios. Administradora e condomínio passam para a inscrição, obrigatórios (ADR-0004). A turma deixa de ter nome e passa a ser identificada por local + ocupação.

## PA-007 — Presença e certificado: regras que só o solicitante pode dar

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Resposta (presença, 2026-09-08):** sem prazo para marcar; não existe presença parcial (presente ou ausente); qualquer usuário `condomed` ou `admin` marca; a turma passa a `realizada` ao registrar presença e a opção manual sai do formulário; a lista de presença mantém as linhas em branco, sem coluna de horário; o histórico guarda tudo, sem retenção. **Resposta (certificado, 2026-09-04):** ver PA-008.
- **Pergunta original:** (mantida abaixo para contexto)
- **Trava:** fases C (presença) e D (certificado) do `../docs/curso-cipa/MAPEAMENTO_CIPA_FASE2.md`. Não trava a fase A (`specs/curso-cipa-historico/`).
- **Questão:** carga horária do certificado; texto e base legal; quem assina (reabre o instrutor da turma, retirado em PA-002); numeração; layout; prazo para marcar presença; presença parcial; quem pode marcar; envio por e-mail; linhas extras na lista de presença. Lista completa na seção 7 do mapeamento.

## PA-008 — O que o certificado exige do cadastro

- **Status:** fechada (2026-09-04) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** a emissão do certificado (fase D do mapeamento).
- **Questão:** os dois modelos de certificado em Word (`../docs/curso-cipa/ANALISE_CERTIFICADO_CIPA.md`) citam o condomínio com CNPJ e levam nome, registro MTE e assinatura digitalizada do instrutor — nada disso existia no cadastro. O instrutor tinha sido retirado do escopo em PA-002.
- **Resposta:** CNPJ do condomínio entra na inscrição, **opcional para inscrever e obrigatório para emitir** (o funcionário extra de última hora entra sem ele). Instrutor volta, mas **sem cadastro editável**: lista fixa no código com os dois instrutores dos certificados existentes (Felipe Barboza de Oliveira, MTE/RJ 0060169; Vinicius dos Santos Pinto, MTE/RJ 0056876), assinaturas como assets do repositório, e um select na turma. Unidade emissora e cidade vêm do local (CondoMed Rio nos dois locais — a frente em São Paulo dos modelos era defeito). Data impressa é a do curso; certificado numerado (`CIPA-AAAA-000000`) com código de verificação; só download, sem e-mail.

## PA-009 — Presença antes do dia da turma

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** baixa
- **Resposta (2026-09-08):** presença **nunca antes** da data da turma. A API recusa com 400.
- **Trava:** um critério de RF-HIS-004; não trava a implementação.
- **Questão:** o solicitante disse "sem prazo" para marcar presença **depois** do curso. Não foi perguntado sobre **antes**: pode-se registrar presença numa turma cuja data ainda não chegou? Hipótese de trabalho: não — a API recusa presença antes da data da turma, porque presença é fato do dia e marcar antes só produz registro falso. Se a operação precisar (ex.: curso adiantado), vira um dia de tolerância.

## PA-010 — Palestrantes e locais passam a ser cadastro editável

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Resposta (2026-09-08):** (a) qualquer usuário **`condomed`** cadastra e edita (e `admin`, como em todo o módulo); (b) registro com turma vinculada **desativa e mantém no histórico**, nunca exclui; (c) assinatura **opcional no cadastro** — o formulário já oferece o campo para anexá-la — e **obrigatória para emitir** o certificado, mesmo tratamento do CNPJ do condomínio.
- **Trava:** RF-CIP-006 e RF-CIP-007 (`specs/curso-cipa-cadastros/`).
- **Questão:** em 2026-09-08 o dono pediu área na Condomed para cadastrar palestrantes e locais, revertendo PA-001 (locais fixos) e a decisão Q3 de PA-008 (instrutores fixos "para não cadastrar errado"). Falta decidir: (a) quem cadastra — qualquer `condomed` ou só `admin`? (b) registro com turma vinculada não se exclui, só se desativa — confirmar; (c) a assinatura é obrigatória já no cadastro do palestrante ou só para emitir certificado? Hipótese de trabalho: (a) `condomed` e `admin`, como o resto do módulo; (b) sim; (c) opcional no cadastro, obrigatória para emitir — mesmo padrão do CNPJ (PA-008).

## PA-011 — Onde guardar a assinatura digitalizada

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** média
- **Resposta (2026-09-08):** a empresa tem acesso a **AWS S3**; a assinatura vai para um bucket S3 (django-storages), com as chaves em variáveis de ambiente. "Deixar na rede" foi descartado: o backend na DigitalOcean não alcança a rede interna.
- **Trava:** RNF-CIP-005.
- **Questão:** o backend roda em container na DigitalOcean App Platform, com disco descartado a cada deploy, e o repositório não configura `MEDIA_ROOT` nem `STORAGES` (verificado em `bigcorp/settings.py`, 2026-09-08). Upload em disco perderia as assinaturas no próximo deploy. Hipótese de trabalho: imagem no banco (`BinaryField` + tipo MIME, limite 500 KB) — são poucas imagens pequenas e não há bucket (Spaces) contratado. Se a operação já tiver um bucket, o design troca para ele.

## PA-012 — Emissão em lote com inscritos impedidos

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** média
- **Resposta (2026-09-08):** **emite só os aptos** e a tela **avisa quais não foram emitidos** e por quê. Falta de instrutor ou de assinatura continua recusando o lote inteiro.
- **Trava:** um critério de RF-HIS-005.
- **Questão:** numa turma com 18 presentes em que 2 estão sem CNPJ do condomínio (PA-008: obrigatório para emitir), a emissão em lote emite os 16 aptos e devolve os 2 como impedidos, ou recusa o lote inteiro até tudo estar completo? Hipótese de trabalho: **emite os aptos e lista os impedidos com o motivo** — a operação corrige o CNPJ e emite de novo só para eles (a emissão é idempotente). Falta de instrutor ou de assinatura do instrutor, por afetar todos, recusa o lote.

## PA-013 — Turma com certificado emitido é intocável

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** um critério de RF-HIS-005.
- **Questão:** a hipótese anterior (mapeamento, 7b) era "não se exclui, só se cancela". Perguntado ao dono em 2026-09-08 se cancelar também deveria ser bloqueado.
- **Resposta (2026-09-08):** **nem cancelar**. Turma com certificado emitido não pode ser excluída nem ter a situação alterada para `cancelada`; permanece `realizada`. A inscrição com certificado também não pode ser removida.

## PA-013 — Turma com certificado emitido é intocável

- **Status:** fechada (2026-09-08) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** um critério de RF-HIS-005.
- **Questão:** a hipótese anterior (mapeamento, 7b) era "não se exclui, só se cancela". Perguntado ao dono em 2026-09-08 se cancelar também deveria ser bloqueado.
- **Resposta (2026-09-08):** **nem cancelar**. Turma com certificado emitido não pode ser excluída nem ter a situação alterada para `cancelada`; permanece `realizada`. A inscrição com certificado também não pode ser removida.

## PA-014 — Layout do PDF e da planilha de faturas pendentes

- **Status:** fechada (2026-09-09) · **Dono:** Ingrid Aylana · **Severidade:** média
- **Resposta (2026-09-09):** o dono enviou o PDF "rel-faturas-pendentes-coimbra.pdf" gerado pelo legado em 09/09/2026 (6 páginas, 138 documentos, total R$ 45.581,23), enviado pelo dono em 2026-09-09. Layout a reproduzir: **A4 retrato**; cabeçalho com data de geração à esquerda, título "RELATÓRIO DE FATURAS PENDENTES" centralizado, "Página N de M" à direita e a linha "DATA: __/__/__ A __/__/__" com o período de vencimento filtrado; tabela com cabeçalho em duas linhas (FATURA · DOCUMENTO · PRODUTO/OBS · VIGÊNCIA · DATA VENCIMENTO · VALOR DOCUMENTO · DATA PAGAMENTO · VALOR PAGO); **cada documento ocupa duas linhas**: na primeira, fatura, documento, sacado, vigência MM/AAAA, vencimento e valor; na segunda, produto/OBS, periodicidade e parcela (MENSAL 12/1) e a administradora em negrito; separador pontilhado entre documentos; rodapé "N Fatura(s) · TOTAL GERAL R$ x · R$ pago". Sem subtotais por grupo. A planilha segue as mesmas colunas, uma linha por documento, mais uma linha de totais.
- **Trava:** RF-FAT-002 e RF-FAT-003 (`specs/relatorio-faturas-pendentes/`).
- **Questão:** o legado gera "relatório" (PDF) e "planilha". Não temos o modelo impresso do legado para reproduzir. Hipótese de trabalho: PDF A4 paisagem, cabeçalho com os filtros aplicados e a data de geração, agrupado pela ordenação escolhida quando ela é administradora ou cedente (subtotal por grupo), total geral no fim; planilha com uma linha por fatura, colunas iguais às da resposta do FedHub e linha de totais. Se a operação quiser o layout idêntico ao legado, precisamos de um PDF gerado por ele como referência.

## PA-015 — Relatório de faturas pendentes: pedido e quem acessa

- **Status:** fechada (2026-09-09) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** RF-FAT-001, RNF-FAT-001 (`specs/relatorio-faturas-pendentes/`).
- **Questão:** registrada já com a resposta, para servir de decisão citável nas regras do relatório de faturas pendentes.
- **Resposta (2026-09-09):** o dono pediu o relatório de faturas pendentes no Financeiro, em Excel e PDF, reproduzindo o legado. **Acesso: financeiro, faturamento e admin.** A definição de pendente (vencimento passado há pelo menos 1 dia e sem baixa) vive no registro do FedHub.

## PA-016 — Consulta por voucher traz parcelas que não estavam no documento

- **Status:** parcialmente fechada (2026-09-18) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** RF-VOU-002..004 (`specs/consulta-espelho-voucher/`).
- **Questão:** o voucher 20131244 (favorecida ACPL ADMINISTRADORA DE IMÓVEIS) saiu com 169 parcelas e R$ 7.391,23; a consulta pelo número devolvia 186 linhas e R$ 8.086,09. As 17 a mais eram parcelas **sem baixa** de três lançamentos gerais — dezesseis já vencidas em 17/09, uma vencendo em 18/09 —, que herdam o número carimbado em `COMISSAO.VOUCHER` porque o carimbo é por lançamento e a consulta expande o lançamento em uma linha por parcela. Com o filtro de baixadas a consulta devolvia exatamente 169. O voucher não tem data de repasse gravada. Entre os 46 vouchers da mesma favorecida, 30 mostravam parcelas pagas depois do repasse (medição de 2026-09-18; a questão de mesmo teor no registro do frontend, em `FedConnect-FrontEnd-Prod/specs/00-registro-de-questoes.md`, traz o levantamento completo).
- **Resposta (2026-09-18):** **"não tem que trazer parcelas sem baixa, tem que trazer EXATAMENTE o que tem no voucher."** Decisão: o Django registra a composição de cada documento na emissão e a consulta por voucher devolve só isso (ADR-0008). Filtrar por baixa foi recusado como solução.
- **Complemento (2026-09-18, fim do dia):** a lista de emissão **muda ao longo do dia**, porque a baixa do retorno bancário entra aos poucos. Medido na ACPL no mesmo dia: 129 parcelas baixadas às 11h10, 169 no momento da emissão do voucher 20131244, 171 às 15h22 — as 42 que entraram no intervalo venceram em 17/09 e foram baixadas em 17/09, mas só apareceram no sistema durante o dia 18. Cancelado o voucher, as comissões voltaram à lista e ela mostrou 171. **Não é divergência: é o conjunto de parcelas pagas crescendo.** É exatamente por isso que o documento precisa de composição registrada, e não de um filtro recalculado.
- **Em aberto:** parcela sem baixa deve continuar entrando na **lista de emissão** (80 das 209 pendentes da ACPL, R$ 3.995,90)? É regra de negócio; enquanto não decidida, a lista fica como está e o espelho garante que o que saiu no PDF é o que a consulta mostra.

