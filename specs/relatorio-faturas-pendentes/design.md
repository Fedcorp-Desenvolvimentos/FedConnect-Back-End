# Design — Relatório de faturas pendentes (proxy e exportações)

> **Rastreabilidade** — RF: RF-FAT-001..003 · RNF: RNF-FAT-001..002 · INV: — · Questões: PA-014, PA-015
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
> **Baseado em:** `requirements.md` (aprovado em 2026-09-09) · implementado no mesmo dia por instrução do dono ("segue")

## Visão Geral da Solução

Três views novas no app `fedhub` sob uma permissão própria (RNF-FAT-001): `GET faturas/pendentes/` repassa os filtros ao FedHub e devolve a resposta dele sem recontar (RF-FAT-001); as duas exportações chamam o mesmo FedHub e formatam com funções puras em `fedhub/relatorios_documentos.py` — planilha openpyxl com uma linha por documento (RF-FAT-002) e PDF ReportLab no layout do legado (RF-FAT-003, PA-014). Erros do FedHub viram 502/504/400 com mensagem legível; relatório vazio é resultado, não erro.

## Arquitetura

| Arquivo | Mudança |
|---|---|
| `users/permissions.py` | `IsFinanceiroOuFaturamentoOuAdmin` (níveis `financeiro`, `faturamento`, `admin`) |
| `fedhub/services/relatorios_service.py` (novo) | `filtrar_parametros(query_params)` (só o contrato, sem vazios); `RelatoriosFedhubService.faturas_pendentes(filtros)` com timeout 60 s; exceções `FedHubIndisponivel`, `FedHubDemorou`, `FedHubRecusou(status_code, detalhe)` |
| `fedhub/relatorios_documentos.py` (novo) | `gerar_planilha(dados)`, `gerar_pdf(dados)`, `linhas_da_tabela`, `descrever_filtros`, `moeda_br`, `nome_arquivo`; `_CanvasNumerado` escreve "Página N de M" e o cabeçalho em toda página |
| `fedhub/views/relatorios_view.py` (novo) | `FaturasPendentesView`, `FaturasPendentesExcelView`, `FaturasPendentesPDFView` (base comum `buscar()` que traduz os erros); `Content-Disposition` exposto ao CORS |
| `bigcorp/urls.py` | `faturas/pendentes/`, `faturas/pendentes/exportar-excel/`, `faturas/pendentes/exportar-pdf/` |
| `fedhub/test_relatorio_faturas_pendentes.py` (novo) | CT-FAT-001..003 — 17 testes com o service do FedHub mockado |

## Modelo de Dados e Contratos

Sem alteração de modelo. Contrato de entrada: os filtros do FedHub (`fatura`, `seguradora`, `cedente`, `administradora`, `apolice`, `vencimento_ini`, `vencimento_fim`, `vigencia_ini`, `situacao`, `classificacao`, `ordenar_por`), repassados sem tradução; qualquer outro parâmetro é ignorado.

- `GET faturas/pendentes/` → `200 {sucesso: true, status, filtros, referencia, totais, data, timestamp}` (o corpo do FedHub mais `sucesso`).
- `GET faturas/pendentes/exportar-excel/` → `.xlsx`, `Content-Disposition: attachment; filename="faturas-pendentes-<referencia>.xlsx"`, `Access-Control-Expose-Headers: Content-Disposition`. Aba "Faturas pendentes": cabeçalho, uma linha por documento (vencimento como data, valor como número com formato `R$`), linha de totais; aba "Filtros" com geração, referência e filtros por extenso.
- `GET faturas/pendentes/exportar-pdf/` → `application/pdf`, mesmo padrão de headers. A4 retrato; cabeçalho em toda página (data de geração, título, "Página N de M", "DATA: de A até", filtros por extenso); tabela com cabeçalho em duas linhas repetido por página e dois renglões por documento (fatura, documento, sacado, vigência, vencimento, valor; produto/OBS, parcela, administradora), separador pontilhado; rodapé "N Fatura(s) · N documento(s) · TOTAL GERAL · pago".

## Fluxo Principal

1. A tela chama `faturas/pendentes/` com os filtros aplicados; a view filtra os parâmetros, chama o FedHub e devolve o corpo com `sucesso`.
2. Gerar planilha/PDF chama a rota de exportação com os mesmos filtros; a view busca no FedHub de novo (o relatório é sempre do dado atual) e formata.
3. O navegador salva com o nome do `Content-Disposition`.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| FedHub não responde (conexão/DNS/túnel) | 502 `{sucesso: false, erro}` | RF-FAT-001 |
| FedHub passa de 60 s | 504 | RF-FAT-001 |
| FedHub responde 400 (filtro fora do vocabulário) | 400 com o `detail` dele | RF-FAT-001 |
| FedHub responde outro erro (503, 500) | 502 com o detalhe | RF-FAT-001 |
| Nível sem permissão | 403 nas três rotas | RNF-FAT-001 |
| Nenhum documento | planilha com cabeçalho e totais zerados; PDF com a frase "Nenhuma fatura pendente..." e totais zerados | RF-FAT-002, RF-FAT-003 |
| Parâmetro fora do contrato (`produtor`, `page`...) | ignorado, não repassado | RNF-FAT-002 |

## Decisões

- Funções de documento puras e separadas das views (`relatorios_documentos.py`), no padrão de `condomed/documentos.py`: os testes cobrem a formatação sem HTTP.
- A exportação **não** reaproveita o JSON que a tela já tem: busca no FedHub de novo. Simples, sempre atual, e evita mandar milhares de linhas do navegador para o servidor.
- Sem `pandas` nas exportações novas (as antigas usam): openpyxl direto dá controle de tipo por célula (data e número de verdade, não texto).
- Layout do PDF pelo legado (PA-014): retrato, dois renglões, sem subtotais por grupo. O agrupamento por administradora fica só na tela.

## Divergência vs. produção

As exportações antigas de faturas com boletos (`consultas/faturas/com-boletos/exportar-*`) continuam como estão, inclusive o 404 em resultado vazio; a nova devolve documento vazio. Não há duplicata entre `consultas/` e `fedhub/` para estas rotas — nasceram só em `fedhub/`.

## Estratégia de Testes

| CT | Requisito | Caso |
|---|---|---|
| CT-FAT-001 | RF-FAT-001, RNF-FAT-001, RNF-FAT-002 | Repassa só os filtros do contrato e devolve linhas/totais sem recontar; parâmetros estranhos ignorados; FedHub fora → 502, demorou → 504, 400 do FedHub → 400, outro erro → 502; permissões por nível nas três rotas; sem login → 401; service traduz `Timeout`/`ConnectionError`/status ≠ 200 |
| CT-FAT-002 | RF-FAT-002 | xlsx abre; colunas, tipos (data, número) e linha de totais batem com o JSON; vazio devolve planilha com cabeçalho e totais zerados; nome do arquivo e header CORS |
| CT-FAT-003 | RF-FAT-003 | PDF começa com `%PDF-`, nome e header; vazio gera; 140 documentos produzem mais de uma página; dois renglões por documento com produto/OBS, parcela `n/total` e administradora; filtros descritos e moeda |

Verificação visual do PDF: amostra com 60 documentos sintéticos gerada em 2026-09-09 e conferida contra o PDF do legado (cabeçalho, duas linhas, pontilhado, rodapé).

## Impacto e Riscos

Rotas e arquivos novos; nada existente muda. Risco: o PDF de milhares de documentos leva alguns segundos no ReportLab — dentro do timeout do gunicorn para a base atual (centenas). O FedHub corta em 5.000 linhas.

## Redesenho do PDF (PA-017, 2026-09-21)

O PDF era cópia fiel do relatório do legado e o dono pediu o padrão visual do voucher de comissão. O voucher é HTML renderizado pelo Chromium no FedHub; aqui é ReportLab no Django, então a linguagem foi **traduzida**, não reaproveitada.

| Elemento do voucher | Como ficou no ReportLab |
|---|---|
| Faixa navy do topo, com marca e título | Retângulos desenhados no canvas, em 48 faixas finas para simular o degradê; repete em toda página porque está no canvas, não no fluxo |
| Cartões de metadados | `Table` de duas linhas (rótulo pequeno em cinza, dado grande), fundo claro e divisórias brancas |
| Tabela com cabeçalho navy e zebrado | `TableStyle` com `BACKGROUND` no cabeçalho, zebra nas ímpares e linha fina embaixo |
| Valores em verde e monoespaçados | `Courier-Bold` com a cor do voucher |
| Bloco de total em destaque | Faixa azul de largura total no fim do fluxo |

**Uma linha por documento.** O legado usava dois renglões porque espremia dez colunas, duas delas (data e valor de pagamento) sempre vazias num relatório de pendentes. Removidas, sobra largura para uma linha só: produto e OBS viram texto secundário sob o sacado, e os dias em atraso sob o vencimento.

**Larguras.** Medidas contra o texto mais largo de cada coluna — documento e vencimento têm dez caracteres em Courier 7,2, cerca de 43 pt — porque o ReportLab quebra a palavra em silêncio quando não cabe, e foi o que aconteceu na primeira tentativa.

| Caso | Requisitos | O que prova |
|---|---|---|
| CT-FAT-004 | RF-FAT-003 | `linhas_da_tabela` devolve uma linha por documento, cabeçalho de oito colunas sem "PAGAMENTO"/"PAGO", produto e OBS na célula do sacado, vencimento com o atraso; amostras renderizadas: 26 linhas em 2 páginas com cabeçalho repetido e faixa de total na última, e o caso vazio em bloco próprio |
