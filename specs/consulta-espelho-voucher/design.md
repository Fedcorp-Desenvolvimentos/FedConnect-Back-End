# Design — Consulta de voucher devolve exatamente o que entrou no documento

> **Rastreabilidade** — RF: RF-VOU-002..005 · RNF: RNF-VOU-001 · ADR: ADR-0008 · Questões: PA-016
> **Status:** em revisão · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-18
> **Baseado em:** `requirements.md` (aprovado em 2026-09-18)

## Arquitetura

O Django, que já é o proxy da emissão e da consulta, passa a ter **memória da emissão**: dois modelos no app `fedhub` (que até aqui só tinha views e por isso entrou em `INSTALLED_APPS`). A emissão grava; a consulta por voucher filtra; o cancelamento marca.

```
POST emitir-voucher/recibo ──► FedHub (PDF + carimbo em COMISSAO.VOUCHER)
                               └─► sucesso ──► espelho.registrar_emissao(numero, payload)   RF-VOU-002
GET  consultar/?voucher=N   ──► FedHub (todas as parcelas com o número N)
                               └─► espelho.aplicar_espelho(N, linhas) ──► só o que entrou     RF-VOU-003
POST cancelar/              ──► FedHub (voucher inteiro)
                               └─► espelho.marcar_cancelamento(numeros)                        RF-VOU-004
```

| Arquivo | Papel |
|---|---|
| `fedhub/models.py` | `VoucherEmitido` (número único, tipo, favorecido, empresa pagadora, totais, emitido por/em, cancelado em) e `VoucherEmitidoItem` (fatura, tipo_fat, favor, tipo, parcela, parcela_comissao, documento, valor; único por voucher + chave natural). |
| `fedhub/migrations/0001_voucher_emitido.py` | Primeira migração do app. |
| `fedhub/services/espelho_voucher_service.py` | `registrar_emissao`, `aplicar_espelho`, `marcar_cancelamento`, `chave_da_linha`. Sem chamada ao FedHub. |
| `fedhub/views/comissao_view.py` | Emissão de voucher e recibo chamam o registro após o PDF; consulta aplica o espelho quando há `voucher`; cancelamento marca. |
| `bigcorp/settings.py` | `"fedhub"` em `INSTALLED_APPS`. |

## Modelo de Dados e Contratos

**Chave natural de uma parcela** (a mesma nos dois formatos): `fatura` sem zeros à esquerda, `favorecido` sem zeros à esquerda, `tipo` em maiúsculas (padrão `BENEFICIO`), `parcela` do boleto sem zeros, `documento` como texto. É o que identifica a linha tanto no payload do front (`fatura`, `favorecido`, `tipo`, `parcela`, `documento`) quanto na resposta do FedHub (`FATURA`, `FAVOR`, `TIPO`, `PARCELA`, `DOCUMENTO`).

**Resposta de `GET /comissoes/consultar/` com `voucher`** — sem mudança no que já existia (`sucesso`, `dados.data`, `dados.total_registros`, `filtros_aplicados`) e com dois campos novos, só quando o filtro de voucher foi usado:

```json
{ "sucesso": true, "dados": {"data": [...], "total_registros": 169}, "filtros_aplicados": {...},
  "espelho": true }
{ "sucesso": true, "dados": {...}, "filtros_aplicados": {...},
  "espelho": false, "aviso": "Documento emitido antes do registro de composição: ..." }
```

O front atual ignora campos que não conhece; mostrar o `aviso` é tarefa dele (spec `planilha-espelho-voucher` no repositório do frontend).

## Fluxo Principal

1. Operador emite o voucher. O FedHub gera o PDF, carimba as comissões e devolve o número.
2. O Django grava o `VoucherEmitido` com os totais do `resumo` e um item por comissão do payload. Reutilização de número só acrescenta o que faltava.
3. Na consulta por número, o FedHub devolve todas as parcelas com aquele carimbo. O Django cruza pela chave natural e devolve só as registradas, com `espelho: true`.
4. Número sem registro (anterior à spec): lista inteira, `espelho: false`, `aviso`.
5. Cancelamento: `cancelado_em` preenchido; itens preservados.

## Tratamento de Erros

- Registro falha (banco indisponível, payload sem número): a emissão responde sucesso mesmo assim, e o erro vai para o log com o número do documento. Nunca se desfaz um PDF já entregue e um carimbo já gravado (RNF-VOU-001).
- Registro tem N parcelas e a consulta devolve menos de N (baixa estornada, comissão cancelada no ERP): as linhas devolvidas são as que casaram; fica um `warning` no log. Não é erro do espelho.
- Número inexistente: FedHub devolve vazio; o espelho não altera vazio.

## Decisões

- **Memória no Django, não no Firebird (ADR-0008).** O ERP legado não tem coluna por parcela e não se altera o schema dele. O Django já intermedeia emissão e consulta, tem Postgres e migrações.
- **Filtrar, não substituir.** A consulta continua devolvendo as linhas como o FedHub as monta (com todos os campos que a tela usa); o registro só decide quais passam. Assim a tela não precisa de novo contrato.
- **Falha do registro não derruba a emissão.** A alternativa (transação que reverte o carimbo) exigiria uma chamada de desfazer no FedHub e deixaria um PDF órfão no cliente.
- **Vouchers antigos são reconstituíveis por comando, nunca automaticamente.** A inferência usa as parcelas hoje baixadas — foi assim que o 20131244 fechou em 169 —, mas a lista de baixas cresce ao longo do dia (PA-016, complemento), então o registro nasce marcado `reconstituido` e a consulta avisa. Sem rodar o comando, a resposta segue dizendo que não é espelho.

## Divergência vs. produção

- O app `fedhub` não estava em `INSTALLED_APPS`; suas views eram roteadas sem o app instalado. Passa a estar, com migração. Nenhum modelo pré-existente é afetado.
- Favorecido chega com zeros à esquerda do FedHub (`0000005912`) e sem zeros do front (`5912`); a chave normaliza os dois. `FATURA` vem como inteiro do FedHub e como texto do front.

## Verificação

| Caso | Requisitos | O que prova |
|---|---|---|
| CT-VOU-002 | RF-VOU-002, RNF-VOU-001 | Registro grava documento, totais e 3 itens com a chave natural; reemissão do mesmo número soma 1 item sem duplicar; sem número levanta erro; a view de emissão grava com o usuário logado |
| CT-VOU-003 | RF-VOU-003, INV-VOU-001 | De 5 linhas do FedHub (2 registradas da fatura 176779, 1 não paga, 1 paga depois, 1 de outra fatura registrada) voltam exatamente as 3 registradas; favorecido `5912` casa com `0000005912` e fatura `0000176779` com `176779`; voucher sem registro volta inteiro com `espelho: false` e `aviso`; consulta sem `voucher` não ganha os campos |
| CT-VOU-005 | RF-VOU-005 | Comando simula por padrão; `--confirmar` grava marcando `reconstituido`, com bruto somado e retenções zeradas; não toca registro gravado na emissão; `--refazer` só vale para reconstituído; sem parcela baixada não grava; `--favorecido` descobre os números; consulta de registro reconstituído avisa |
| CT-VOU-004 | RF-VOU-004 | Cancelamento marca `cancelado_em` uma vez, mantém os 3 itens, é idempotente; a view de cancelamento marca após sucesso do FedHub |

`fedhub/test_consulta_espelho_voucher.py`: 12 testes, FedHub falsificado por `unittest.mock.patch`, banco sqlite em memória (`--settings=settings_sqlite`).

## Impacto e Riscos

- **Migração em produção**: `python manage.py migrate fedhub` cria duas tabelas novas; nada altera tabelas existentes. Rollback: `migrate fedhub zero` e remover `"fedhub"` de `INSTALLED_APPS`.
- Vouchers emitidos entre o deploy do front e o do Django não têm registro. Ordem de deploy: **Django primeiro**, depois o front.
- Contrato com o front: campos novos são aditivos.
- A regra de negócio "parcela sem baixa entra na lista de emissão" continua como está; este documento só garante que o que saiu no PDF é o que a consulta mostra.
