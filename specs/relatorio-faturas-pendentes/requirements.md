# Requisitos — Relatório de faturas pendentes (proxy e exportações)

> **Rastreabilidade** — RF: RF-FAT-001..003 · RNF: RNF-FAT-001..002 · Questões: PA-014, PA-015
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
> **Aprovado pelo dono em 2026-09-09** (respostas às questões + confirmação da situação A vencer / Vencidas / Todas). **PA-014 fechada em 2026-09-09 com o PDF do legado como referência de layout.**

## Contexto e Problema

`[E]` O Django já faz proxy das consultas de faturas do FedHub e já exporta a consulta de faturas com boletos em Excel e PDF (`consultas/views.py`: `ExportarFaturasComBoletosExcel`, `ExportarFaturasComBoletosPDF`, com openpyxl e ReportLab do `requirements.txt`). `[D]` PA-015: o dono pediu em 2026-09-09 um relatório de faturas pendentes no Financeiro, em Excel e PDF, reproduzindo o relatório do sistema legado. Os dados vêm de uma consulta nova do FedHub (`FedHub-Backend/specs/relatorio-faturas-pendentes/`); a tela é do frontend (`FedConnect-FrontEnd-Prod/specs/relatorio-faturas-pendentes/`).

## Escopo

**Dentro do escopo:**
- Proxy da consulta de pendentes para a tela (JSON) e as duas exportações (xlsx e pdf) com os mesmos filtros.
- Permissão própria: admin, financeiro e faturamento.

**Fora do escopo:**
- Regra do que é pendente e filtros (é o FedHub). Aqui só se repassa e se formata.
- Envio por e-mail, agendamento ou histórico de relatórios gerados.

## User Stories e Critérios de Aceitação

### RF-FAT-001: Dados para a tela

**Como** analista do financeiro, **quero** ver as faturas pendentes na tela com totais, **para** conferir antes de exportar.

- **QUANDO** consulto `GET faturas/pendentes/` com os filtros da tela, **ENTÃO** o sistema **DEVE** repassá-los ao FedHub e devolver a resposta dele (linhas e totais) sem recontar nada. `[E]` padrão de `fedhub/views/faturas_view.py`
- **SE** o FedHub responde erro ou não responde em 60 s, **ENTÃO** o sistema **DEVE** devolver 502/504 com mensagem legível, sem esgotar workers. `[E]` regra do repo (FedHub indisponível é rotina; timeout explícito)
- **SE** o usuário não é `admin`, `financeiro` ou `faturamento`, **ENTÃO** o sistema **DEVE** responder 403. `[D]` PA-015

### RF-FAT-002: Planilha

**Como** analista, **quero** baixar a lista em Excel, **para** trabalhar a cobrança na planilha.

- **QUANDO** consulto `GET faturas/pendentes/exportar-excel/` com os mesmos filtros, **ENTÃO** o sistema **DEVE** devolver um `.xlsx` com **uma linha por documento** (fatura, documento, sacado, produto, OBS, vigência, vencimento, dias em atraso, valor do documento, parcela, administradora, seguradora, cedente, apólice, nosso número, depósito em C/C), cabeçalho formatado, valores como número (não texto) e uma linha de totais; `Content-Disposition` com `faturas-pendentes-AAAA-MM-DD.xlsx` exposto ao CORS. `[D]` PA-014; `[E]` mesmo padrão de `ExportarFaturasComBoletosExcel`
- **QUANDO** não há fatura pendente para os filtros, **ENTÃO** o sistema **DEVE** devolver a planilha só com cabeçalho e totais zerados — não 404 (relatório vazio é resultado). `[E]` divergência deliberada do padrão atual, que devolve 404

### RF-FAT-003: PDF

**Como** analista, **quero** o relatório em PDF, **para** imprimir ou anexar, como fazia no legado.

- **QUANDO** consulto `GET faturas/pendentes/exportar-pdf/`, **ENTÃO** o sistema **DEVE** devolver um PDF **A4 retrato** com o layout do legado: data de geração, título, "Página N de M", linha "DATA: de A até" com o período de vencimento filtrado e a situação escolhida; tabela com cabeçalho em duas linhas e **dois renglões por documento** (fatura, documento, sacado, vigência, vencimento, valor; depois produto/OBS, periodicidade e parcela, administradora), separador pontilhado; rodapé com "N Fatura(s)", TOTAL GERAL e total pago (R$ 0,00). Sem subtotais por grupo. `[D]` PA-014
- **QUANDO** o relatório passa de uma página, **ENTÃO** o cabeçalho da tabela **DEVE** repetir em cada página e o rodapé trazer "página N de M". `[E]` ReportLab platypus já faz isso em `condomed/documentos.py`
- **QUANDO** consulto sem filtros, **ENTÃO** o sistema **DEVE** gerar mesmo assim (todas as pendentes), respeitando o teto de linhas do FedHub. `[D]` PA-014

## Requisitos Não Funcionais

### RNF-FAT-001: Segurança

Nova classe de permissão `IsFinanceiroOuFaturamentoOuAdmin` em `users/permissions.py`, aplicada às três rotas. Nada de `IsAuthenticated` sozinho: o relatório expõe carteira e inadimplência. `[D]` PA-015; `[E]` padrão de `IsCondomedOrAdmin`

### RNF-FAT-002: Compatibilidade

Rotas novas; as exportações de faturas com boletos existentes não mudam. Os filtros e nomes de campos são os do FedHub, repassados sem tradução, para a tela e as exportações lerem o mesmo contrato. `[E]` `FedHub-Backend/specs/relatorio-faturas-pendentes/` RF-FAT-001

**Verificação prevista (detalhada no design, após aprovação):** CT-FAT-001 — proxy repassa filtros e devolve totais; FedHub fora → 502/504; `usuario`/`comercial` → 403, `financeiro`/`faturamento`/`admin` → 200. CT-FAT-002 — xlsx abre, colunas e totais batem com o JSON, vazio devolve planilha vazia. CT-FAT-003 — PDF retrato com o layout do legado (dois renglões por documento, cabeçalho repetido, "Página N de M", rodapé com totais).

## Questões em Aberto

- Nenhuma. PA-014 fechada em 2026-09-09 (layout = PDF do legado).
