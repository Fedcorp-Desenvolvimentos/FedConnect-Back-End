# Requisitos — Consulta de voucher devolve exatamente o que entrou no documento

> **Rastreabilidade** — RF: RF-VOU-002..005 · RNF: RNF-VOU-001 · ADR: ADR-0008 · Questões: PA-016
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-18
> **Aprovado em 2026-09-18 pela decisão do dono, registrada em PA-016: "não tem que trazer parcelas sem baixa, tem que trazer EXATAMENTE o que tem no voucher".**

## Contexto e Problema

`[E]` O único lugar onde o número do voucher fica gravado no ERP é `COMISSAO.VOUCHER`, um campo por **lançamento** de comissão. Numa comissão recorrente com lançamento geral, o FedHub expande o mesmo lançamento em uma linha por parcela do boleto (`voucher_controller.py`, bloco 2 de `consultar_faturas_comissoes`). Todas as parcelas herdam o número — as que não estavam pagas na emissão e as que forem pagas depois.

`[E]` Caso medido em 2026-09-18: o voucher 20131244 (favorecida ACPL) saiu com **169** parcelas, R$ 7.391,23; a consulta por esse número devolvia **186** linhas, R$ 8.086,09. As 17 a mais eram parcelas sem baixa de três lançamentos gerais; com o filtro de baixadas a consulta voltava exatamente 169. Entre os 46 vouchers da mesma favorecida, 30 tinham parcelas pagas depois do repasse aparecendo na consulta. `[E]` Este voucher não tem data de repasse gravada, então nem um corte por essa data o reproduziria.

`[D]` PA-016: a consulta por voucher devolve exatamente o que entrou no documento. Para isso o FedConnect precisa **lembrar** o que entrou, porque o ERP não tem onde guardar isso por parcela (ADR-0008).

## Escopo

**Dentro do escopo:**
- Registrar, na emissão de voucher e de recibo, as parcelas que compuseram o documento, com os totais impressos.
- A consulta por número de voucher devolve só essas parcelas.
- Voucher emitido antes deste registro: a consulta avisa que a lista não é o espelho.
- Cancelamento marca o registro, sem apagá-lo.

**Fora do escopo:**
- Mudar o carimbo no Firebird (por parcela em vez de por lançamento) — mexe no ERP legado.
- Reconstituir a composição de vouchers antigos.
- A lista da tela de emissão trazer parcelas sem baixa (regra de negócio à parte, PA-016 pergunta em aberto).
- Tela: o front já lê `dados.data`/`total_registros`; mostrar o `aviso` é ajuste dele (`FedConnect-FrontEnd-Prod/specs/planilha-espelho-voucher/`).

## User Stories e Critérios de Aceitação

### RF-VOU-002: Registro da composição na emissão

**Como** financeiro, **quero** que o sistema guarde quais parcelas entraram em cada voucher ou recibo, **para** a consulta e a planilha poderem reproduzir o documento depois.

- **QUANDO** `POST /comissoes/emitir-voucher/` ou `POST /comissoes/emitir-recibo/` recebe do FedHub o PDF e o número do documento, **ENTÃO** o sistema **DEVE** gravar um `VoucherEmitido` (número, tipo, favorecido, empresa pagadora, totais bruto, retenções e líquido, quem emitiu, quando) e um `VoucherEmitidoItem` por comissão do payload (fatura, tipo da fatura, favorecido, tipo da comissão, parcela do boleto, parcela do lançamento, documento, valor). `[E]` payload de `useComissoes.js`; `[D]` ADR-0008
- **QUANDO** o FedHub devolve o mesmo número para uma nova emissão (voucher reutilizado), **ENTÃO** o registro **DEVE** apenas acrescentar as parcelas que faltavam — nunca duplicar nem apagar. `[E]` `_buscar_voucher_existente` no FedHub
- **SE** a gravação do registro falhar, **ENTÃO** a emissão **NÃO DEVE** ser desfeita (o PDF existe e o Firebird já foi carimbado); o erro vai para o log. `[D]` ADR-0008

### RF-VOU-003: Consulta por voucher é o espelho

- **QUANDO** `GET /comissoes/consultar/` recebe `voucher=<número>` e existe registro para ele, **ENTÃO** a resposta **DEVE** conter só as linhas do FedHub cuja chave (fatura, favorecido, tipo, parcela do boleto, documento) está no registro, com `total_registros` igual à quantidade devolvida e `espelho: true`. `[D]` PA-016
- **QUANDO** a comparação envolve favorecido ou fatura, **ENTÃO** ela **DEVE** ignorar zeros à esquerda e espaços: o FedHub devolve `0000005912`, o payload manda `5912`. `[E]` conferido nos dados da ACPL
- **QUANDO** não existe registro para o número, **ENTÃO** a resposta **DEVE** devolver as linhas do FedHub inteiras, com `espelho: false` e um `aviso` dizendo que o documento é anterior ao registro. `[D]` PA-016
- **QUANDO** a consulta não filtra por voucher, **ENTÃO** nada muda: sem `espelho`, sem `aviso`, lista como veio do FedHub.

### RF-VOU-004: Cancelamento preserva o registro

- **QUANDO** `POST /comissoes/cancelar/` cancela com sucesso no FedHub, **ENTÃO** o sistema **DEVE** gravar `cancelado_em` nos registros dos vouchers envolvidos e manter os itens, para auditoria. `[E]` o FedHub cancela o voucher inteiro (`WHERE VOUCHER = ?`)

### RF-VOU-005: Reconstituir documentos anteriores ao registro

**Como** financeiro, **quero** poder recompor o registro de vouchers antigos, **para** que a consulta deles também reproduza o documento.

- **QUANDO** rodo `manage.py reconstituir_espelho_voucher <números>` ou `--favorecido <código>`, **ENTÃO** o sistema **DEVE** montar o registro a partir das parcelas hoje **baixadas** de cada voucher e marcar `reconstituido`. `[D]` ADR-0008
- **QUANDO** o comando roda sem `--confirmar`, **ENTÃO** ele **DEVE** apenas simular, listando o que gravaria.
- **SE** o voucher já tem registro gravado na emissão, **ENTÃO** o comando **NÃO DEVE** tocá-lo; registro reconstituído só é refeito com `--refazer`.
- **QUANDO** a consulta devolve um registro reconstituído, **ENTÃO** a resposta **DEVE** avisar que a composição foi inferida e que as retenções não são recuperáveis. `[E]` retenções eram escolha da tela, não ficam no ERP
- **SE** uma parcela que não estava no documento for paga antes da reconstituição, **ENTÃO** ela entrará no registro: a inferência vale para o estado de hoje, e a lista de baixas cresce ao longo do dia (PA-016, complemento). `[P]` PA-016

## Requisitos Não Funcionais

### RNF-VOU-001: Emissão não depende do registro

A gravação do registro acontece depois da resposta do FedHub e nunca bloqueia nem reverte a emissão; sua falha é logada. `[D]` ADR-0008

## Invariantes

- **INV-VOU-001** — Para um voucher com registro, a consulta por número nunca devolve linha que não esteja no registro. Garantido na **aplicação** (`espelho_voucher_service.aplicar_espelho`).

**Verificação prevista:** CT-VOU-002 — emissão grava documento e um item por comissão; reemissão do mesmo número só acrescenta; CT-VOU-003 — consulta por voucher devolve só as parcelas registradas (parcela não paga e parcela paga depois ficam fora), casa favorecido com e sem zeros, voucher sem registro passa inteiro com aviso, consulta sem filtro de voucher não muda; CT-VOU-004 — cancelamento marca a data e mantém os itens.
