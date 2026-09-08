# Design — Histórico e consulta do CIPA (fase A)

> **Rastreabilidade** — RF: RF-HIS-001..003 · INV: — · ADR: ADR-0004, ADR-0007 · Questões: PA-007
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-04
> **Baseado em:** `requirements.md` (aprovado)

## Visão Geral da Solução

Duas actions novas no `TurmaCipaViewSet` existente, ambas paginadas com uma classe própria (`PaginacaoHistorico`), sem tocar em `GET cursos-cipa/` — o calendário depende dele devolver lista sem envelope. Dois serializers derivados dos que existem: `TurmaResumoSerializer` (turma sem `inscricoes`) e `InscricaoComTurmaSerializer` (inscrição com o resumo da turma). Nenhuma migração.

## Arquitetura

| Arquivo | Mudança |
|---|---|
| `condomed/views.py` | `PaginacaoHistorico` (25/página, `page_size` até 100); actions `historico` e `participantes` |
| `condomed/serializers.py` | `TurmaResumoSerializer` herda de `TurmaCipaSerializer` tirando `inscricoes`; `InscricaoComTurmaSerializer` herda de `InscricaoCipaSerializer` e acrescenta `turma` (id, data, local, local_nome, status) |
| `condomed/documentos.py` (novo, ADR-0007) | `linhas_lista_presenca` (ordem e linhas extras — função pura, testável), `cabecalho_lista_presenca` (unidade, instrutor, totais), `gerar_lista_presenca` (ReportLab platypus, A4 paisagem, tabela com coluna de assinatura, rodapé com autor/página) |
| `condomed/views.py` — `lista_presenca` (novo) | `GET cursos-cipa/{id}/lista-presenca/` → PDF com `Content-Disposition` e `Access-Control-Expose-Headers` |

## Modelo de Dados e Contratos

Sem alteração de modelo.

- `GET cursos-cipa/historico/?data_inicio&data_fim&local&status&administradora&condominio&busca&page&page_size` → `{count, next, previous, results: [TurmaResumo]}`, ordenado por `-data, local`
- `GET cursos-cipa/participantes/?cpf&administradora&condominio&data_inicio&data_fim&busca&page&page_size` → `{count, next, previous, results: [InscricaoComTurma]}`, ordenado por `-turma__data, condominio_nome, nome`
- `GET cursos-cipa/{id}/lista-presenca/` → `application/pdf`; `Content-Disposition: attachment; filename="lista-presenca-cipa-AAAA-MM-DD-<local>.pdf"`; `Access-Control-Expose-Headers: Content-Disposition`. Sem parâmetros; sem cache; gerado a cada chamada

`administradora` e `condominio` no histórico atravessam `inscricoes__*` e exigem `distinct()`, porque a junção multiplica a turma pelo número de inscritos que casam.

## Fluxo Principal

1. Tela pede `historico/` com o período padrão (últimos 6 meses) e pagina.
2. Operador clica numa turma → `GET cursos-cipa/{id}/` (já existe) para o detalhe com inscritos.
3. Na aba de participantes, a tela pede `participantes/?busca=` e mostra uma linha por inscrição; o clique leva ao detalhe da turma da linha.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| `page_size` acima de 100 | cortado em 100 | RNF-HIS-001 |
| Busca livre casando vários inscritos da mesma turma | uma linha por turma (`distinct`) | RF-HIS-001 |
| Termo de busca sem dígitos | não compara com CPF | RF-HIS-002 |
| Usuário sem nível | 403, como o resto do viewset | — |

## Decisões

- Rota separada para o histórico, em vez de paginar `GET cursos-cipa/`: o calendário pede o mês inteiro como lista; mudar o contrato quebraria a agenda por um ganho que só o histórico precisa. Decisão local, sem ADR.
- `TurmaResumo` sem `inscricoes`: o histórico pode listar centenas de turmas; a lista completa de inscritos de cada uma é dado que a tela não usa ali.
- ADR-0007: documentos gerados do registro a cada download, nunca armazenados; lista de presença sempre disponível, ordenada por condomínio, com linhas extras.

## Divergência vs. produção

Nenhuma — rotas novas.

## Estratégia de Testes

| CT | Requisito | Caso |
|---|---|---|
| CT-HIS-001 | RF-HIS-001 | Lista ordenada por data desc sem `inscricoes`; filtros de período, local, situação, administradora e condomínio; busca livre sem turma repetida; busca por CPF com máscara |
| CT-HIS-002 | RNF-HIS-001, RF-HIS-001 | `page_size` respeitado e cortado em 100; `GET cursos-cipa/?mes&ano` segue devolvendo lista |
| CT-HIS-003 | RF-HIS-002 | Uma linha por inscrição com o resumo da turma; busca por nome, condomínio, administradora e início de CPF; filtro por período |
| CT-HIS-004 | — | `usuario` recebe 403 nas duas rotas |
| CT-HIS-005 | RF-HIS-003 | Linhas ordenadas por condomínio→nome com 5 extras numeradas em sequência e CPF formatado; cabeçalho resolve unidade Rio, instrutor com MTE ou "a definir"; endpoint devolve `%PDF-` com os headers; turma futura/vazia também gera; `usuario` → 403 |

## Impacto e Riscos

Sem migração, sem mudança de contrato existente. Risco baixo: as consultas com `inscricoes__*` + `distinct()` podem ficar lentas com dezenas de milhares de inscrições — hoje são dezenas. Se crescer, o caminho é anotar contagens em vez de `prefetch_related`.
