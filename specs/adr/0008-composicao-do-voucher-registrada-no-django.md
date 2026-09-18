# ADR-0008 — A composição de cada voucher fica registrada no Django, não inferida do Firebird

> **Status:** aceito · **Data:** 2026-09-18 · **Spec:** `consulta-espelho-voucher` · **Questões:** PA-016

## Contexto

O ERP guarda o número do voucher em `COMISSAO.VOUCHER`, um campo por lançamento. Numa comissão recorrente com lançamento geral, um lançamento vira dezenas de parcelas na consulta, e todas herdam o número — as não pagas na emissão e as pagas depois. Em 2026-09-18 o voucher 20131244 saiu com 169 parcelas e a consulta mostrava 186. O dono decidiu que a consulta por voucher devolve exatamente o que está no documento.

## Decisão

No momento em que o FedHub confirma a emissão (PDF gerado, Firebird carimbado), o Django grava a composição do documento — número, totais e uma linha por parcela, com a chave natural que identifica a parcela também na consulta do FedHub. A consulta por número cruza as linhas do FedHub com esse registro e devolve só o que casou. Voucher sem registro passa inteiro, avisado.

A gravação é **acessória**: falhar nela não desfaz a emissão. E o registro **não substitui** a consulta: as linhas continuam vindo do FedHub, com todos os campos que a tela usa; o registro só decide quais passam.

## Alternativas consideradas

- **Carimbar o voucher por parcela no Firebird.** Solução de raiz, mas exige coluna nova numa tabela do ERP legado, que outro sistema lê e escreve, e muda o cancelamento por voucher. Fora do alcance deste repositório.
- **Filtrar por baixa até a data de repasse.** Aproximação: parte dos vouchers não tem data de repasse gravada (o 20131244 não tem), e parcela paga no mesmo dia da emissão ficaria ambígua. Não é "exatamente".
- **Filtrar só parcelas baixadas.** Fecha hoje e quebra na próxima parcela paga. Foi o que o dono recusou.

## Consequências

- Duas tabelas novas no Postgres do Django; `fedhub` entra em `INSTALLED_APPS`; migração no deploy, antes do front.
- Vouchers emitidos antes do registro não têm espelho e a resposta diz isso. Não há reconstituição.
- A planilha da tela de consulta, quando existir, herda a exatidão de graça: ela lê a mesma resposta.
