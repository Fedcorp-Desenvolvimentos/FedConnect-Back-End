# Design — Histórico, consulta e documentos do CIPA (fases A–D)

> **Rastreabilidade** — RF: RF-HIS-001..006 · RNF: RNF-HIS-001..003 · INV: — · ADR: ADR-0004, ADR-0007 · Questões: PA-007, PA-008, PA-009, PA-012, PA-013
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
> **Fase C (presença, RF-HIS-004): seções marcadas "fase C" abaixo, implementada em 2026-09-08 por instrução do dono ("segue o que dá pra fazer").**
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
| `condomed/models.py` — fase C | `InscricaoCipa.presenca` (`BooleanField(null=True)`), `presenca_registrada_em`, `presenca_registrada_por` (FK usuário, `SET_NULL`); `TurmaCipa.contagem_presenca()` conta presentes/ausentes/sem registro do prefetch. Migração `0004_presenca_por_inscricao` (aditiva) |
| `condomed/services.py` — fase C | `validar_turma_para_presenca(turma, hoje)` (cancelada / antes da data → mensagem) e `registrar_presenca(turma, presencas, usuario)` (lote atômico, auditoria, turma → `realizada`; devolve erros por índice sem gravar) |
| `condomed/serializers.py` — fase C | `InscricaoCipaSerializer` ganha `presenca`, `presenca_registrada_em`, `presenca_registrada_por_nome` (só leitura); `TurmaCipaSerializer` ganha `presentes`, `ausentes`, `sem_registro`; `PresencaItemSerializer`/`PresencaLoteSerializer` validam o corpo (lote não vazio, sem id repetido) |
| `condomed/views.py` — `presenca` (novo) | `POST cursos-cipa/{id}/presenca/` → turma completa (`TurmaCipaSerializer`) |
| `condomed/models.py` — fase D | `ContadorCertificado` (ano único, `ultimo`) e `CertificadoCipa` (OneToOne `PROTECT` com a inscrição, `numero` único, `codigo_verificacao` UUID único, `emitido_em`, `emitido_por`); `InscricaoCipa.certificado_ou_none`; `TurmaCipa.contagem_certificados()` e `tem_certificado`. Migração `0007_certificado_por_inscricao` |
| `condomed/services.py` — fase D | `validar_turma_para_certificado` (cancelada, sem presença, sem instrutor, instrutor sem assinatura), `proximo_numero_certificado(ano)` (contador travado com `select_for_update`), `emitir_certificados(turma, usuario)` (lote atômico, parcial: `emitidos`/`ja_existentes`/`impedidos`), `motivo_turma_intocavel` (PA-013) |
| `condomed/serializers.py` — fase D | `certificado_resumo()`; `InscricaoCipaSerializer.certificado` (só leitura); `TurmaCipaSerializer` ganha `certificados_emitidos`, `aptos_sem_certificado`, `presentes_sem_cnpj`, `instrutor_tem_assinatura`, e recusa `status=cancelada` em turma com certificado |
| `condomed/views.py` — fase D | actions `certificados` (POST) e `certificados/pdf` (GET); `perform_destroy` e `DELETE inscricoes/{id}` recusam com certificado; `resposta_pdf()`; `CertificadoPdfView` em `certificados/<numero>/pdf/` |
| `condomed/documentos.py` — fase D | `dados_certificado` (função pura), `gerar_certificados` (canvas ReportLab, 33,9 × 19,1 cm, frente: faixa da unidade, logos, selo, texto fixo com nome/CPF/condomínio/CNPJ, cidade e data do curso, bloco do instrutor com assinatura lida do storage; verso: faixa, conteúdo programático NR-5 em 8 itens; rodapé com número e código de verificação) |
| `bigcorp/urls.py` — fase D | `path("certificados/<str:numero>/pdf/", CertificadoPdfView)` |

## Modelo de Dados e Contratos

Sem alteração de modelo.

- `GET cursos-cipa/historico/?data_inicio&data_fim&local&status&administradora&condominio&busca&page&page_size` → `{count, next, previous, results: [TurmaResumo]}`, ordenado por `-data, local`
- `GET cursos-cipa/participantes/?cpf&administradora&condominio&data_inicio&data_fim&busca&page&page_size` → `{count, next, previous, results: [InscricaoComTurma]}`, ordenado por `-turma__data, condominio_nome, nome`
- `GET cursos-cipa/{id}/lista-presenca/` → `application/pdf`; `Content-Disposition: attachment; filename="lista-presenca-cipa-AAAA-MM-DD-<local>.pdf"`; `Access-Control-Expose-Headers: Content-Disposition`. Sem parâmetros; sem cache; gerado a cada chamada

`administradora` e `condominio` no histórico atravessam `inscricoes__*` e exigem `distinct()`, porque a junção multiplica a turma pelo número de inscritos que casam.

**Fase C — presença (RF-HIS-004):**

- `POST cursos-cipa/{id}/presenca/` com `{"presencas": [{"inscricao_id": 12, "presente": true}, ...]}` → `200` com a turma completa (mesmo corpo de `GET cursos-cipa/{id}/`), já `realizada` e com `presentes`/`ausentes`/`sem_registro`.
- `400 {"detail": "..."}` para turma cancelada ou com data futura (verificação antes de ler o lote); `400 {"presencas": {"<índice>": {...}}}` para lote vazio, id repetido ou inscrição de outra turma — nesse caso **nada** é gravado.
- Toda inscrição, em qualquer rota que a devolva (turma, `inscricoes/`, `participantes/`), traz `presenca` (`true`/`false`/`null`), `presenca_registrada_em` e `presenca_registrada_por_nome` (nome completo ou e-mail). `PATCH inscricoes/{id}/` ignora `presenca`: só o lote grava.
- Toda turma (calendário, detalhe, `historico/`) traz `presentes`, `ausentes`, `sem_registro`.

**Fase D — certificado (RF-HIS-005, RF-HIS-006):**

- `POST cursos-cipa/{id}/certificados/` (sem corpo) → `200 {"emitidos": [...], "ja_existentes": [...], "impedidos": [{inscricao_id, nome, motivo}], "turma": {...}}`; cada certificado como `{id, inscricao_id, numero, codigo_verificacao, emitido_em, emitido_por_nome}`. `400 {"detail"}` para turma cancelada, sem presença registrada, sem instrutor ou instrutor sem assinatura. Idempotente.
- `GET cursos-cipa/{id}/certificados/pdf/` → PDF com todos os emitidos da turma (2 páginas cada), `Content-Disposition: attachment; filename="certificados-<codigo da turma>.pdf"`, header exposto ao CORS; `404` sem certificado.
- `GET certificados/<numero>/pdf/` → o certificado, `filename="certificado-<numero>.pdf"`; `404` se não existe. Sob `IsCondomedOrAdmin`.
- Inscrição traz `certificado` (`{numero, codigo_verificacao, emitido_em, emitido_por_nome}` ou `null`); turma traz `certificados_emitidos`, `aptos_sem_certificado` (presente, sem certificado, com CNPJ), `presentes_sem_cnpj` e `instrutor_tem_assinatura` (`true`/`false`/`null`).
- `DELETE cursos-cipa/{id}/`, `PATCH {status: "cancelada"}` e `DELETE inscricoes/{id}/` → `400` quando há certificado (PA-013).

## Fluxo Principal

1. Tela pede `historico/` com o período padrão (últimos 6 meses) e pagina.
2. Operador clica numa turma → `GET cursos-cipa/{id}/` (já existe) para o detalhe com inscritos.
3. Na aba de participantes, a tela pede `participantes/?busca=` e mostra uma linha por inscrição; o clique leva ao detalhe da turma da linha.
4. **Presença (fase C):** no detalhe, a aba Presença envia um único `POST presenca/` com o lote marcado; o backend valida a turma, valida o lote, grava tudo em `transaction.atomic()` com `registrada_em`/`por`, muda a turma para `realizada` se ainda não era e devolve a turma inteira — a tela substitui o estado pelo que voltou, sem recontar.
5. **Certificado (fase D):** a aba Certificados chama `POST certificados/`; o backend valida o que afeta todos (turma, instrutor, assinatura), percorre os presentes, pula quem já tem, separa quem está sem CNPJ e cria os demais com número do contador do ano — tudo numa transação. A tela mostra o resultado e oferece "Baixar todos" (`certificados/pdf/`) e "Baixar" por linha (`certificados/<numero>/pdf/`); o PDF é montado do registro na hora.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| `page_size` acima de 100 | cortado em 100 | RNF-HIS-001 |
| Busca livre casando vários inscritos da mesma turma | uma linha por turma (`distinct`) | RF-HIS-001 |
| Termo de busca sem dígitos | não compara com CPF | RF-HIS-002 |
| Usuário sem nível | 403, como o resto do viewset | — |
| Presença em turma `cancelada` | 400 `detail` | RF-HIS-004 |
| Presença antes da data da turma (`timezone.localdate()`) | 400 `detail` com a data | RF-HIS-004 · PA-009 |
| Lote com inscrição de outra turma, vazio ou com id repetido | 400 por índice; nada gravado | RF-HIS-004 |
| Regravar presença | aceito; `registrada_em`/`por` sobrescritos | RF-HIS-004 · RNF-HIS-002 |
| Inscrito adicionado a turma `realizada` | nasce `presenca = null` | RF-HIS-004 |
| Emissão em turma cancelada / sem presença / sem instrutor / instrutor sem assinatura | 400 `detail`, nada emitido | RF-HIS-005 · PA-008 |
| Presente sem CNPJ do condomínio | vai para `impedidos`; os demais saem | RF-HIS-005 · PA-012 |
| Emissão repetida | `ja_existentes`; nada duplicado | RF-HIS-005 · ADR-0007 |
| Dois lotes simultâneos no mesmo ano | contador travado por linha; números em sequência | RF-HIS-005 |
| Excluir/cancelar turma ou remover inscrição com certificado | 400 | RF-HIS-005 · PA-013 |
| PDF da turma sem certificado / número inexistente | 404 | RF-HIS-006 |
| Inscrição corrigida após a emissão | o próximo PDF reflete o registro; número igual | RF-HIS-006 · ADR-0007 |

## Decisões

- Rota separada para o histórico, em vez de paginar `GET cursos-cipa/`: o calendário pede o mês inteiro como lista; mudar o contrato quebraria a agenda por um ganho que só o histórico precisa. Decisão local, sem ADR.
- `TurmaResumo` sem `inscricoes`: o histórico pode listar centenas de turmas; a lista completa de inscritos de cada uma é dado que a tela não usa ali.
- ADR-0007: documentos gerados do registro a cada download, nunca armazenados; lista de presença sempre disponível, ordenada por condomínio, com linhas extras.
- Presença em três estados no próprio `InscricaoCipa` (não em tabela de eventos): a operação quer o estado atual e quem gravou por último (RNF-HIS-002); um histórico de versões seria custo sem pedido. Regra fora da view (`services.registrar_presenca`) para o teste cobrir a regra, não o transporte.
- `realizada` deixa de ser digitada: é inferida da primeira gravação. O backend ainda aceita o valor no `PATCH` da turma por compatibilidade; a tela deixa de oferecê-lo (spec do frontend).
- Certificado é **registro** (número, código, auditoria) com PDF derivado (ADR-0007): reemitir é regenerar, o número não muda; correção do inscrito aparece no próximo download.
- Numeração por **contador por ano** travado com `select_for_update`, em vez de `MAX(numero)+1`: sem furo nem repetição com dois operadores emitindo ao mesmo tempo (no SQLite dos testes o lock é ignorado, mas a escrita já é serializada).
- Emissão **parcial** (PA-012): o que impede um participante (CNPJ) não trava os outros; o que impede todos (instrutor, assinatura, presença, cancelada) trava o lote.
- PDF por `canvas` (não platypus) e **sem compressão**: layout fixo de certificado pede posição absoluta, e o texto legível no arquivo permite testar conteúdo (nome, número, unidade) sem parser de PDF.
- Selo, logos e texto fixo vêm de `condomed/assets/` e de `documentos.py`; a assinatura vem do storage do instrutor (S3 em produção). Faltando um asset, o certificado sai sem a imagem — faltando a assinatura, não sai (a emissão já recusou).

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
| CT-HIS-006 | RF-HIS-004, RNF-HIS-002 | Lote grava presente/ausente com auditoria e realiza a turma; inscrição de outra turma → 400 por índice sem gravar; regravar aceito (auditoria atualizada); cancelada → 400; futura → 400; do próprio dia → 200; lote vazio/repetido → 400; contagens na turma, no histórico e `presenca` nos participantes; inscrito novo em turma realizada nasce `null`; `PATCH` não altera presença; `usuario` → 403 — 11 testes em `PresencaTests` |
| CT-HIS-007 | RF-HIS-005, RNF-HIS-003 | Emite só presentes aptos e lista impedidos; números `CIPA-AAAA-000001..`; contagens na turma e na inscrição; idempotente e emite o impedido após corrigir o CNPJ; sem presença → 400; sem instrutor / sem assinatura → 400 sem emitir; cancelada → 400; sequencial por ano da turma; turma e inscrição com certificado intocáveis (excluir, cancelar, remover → 400; inscrição sem certificado ainda sai); histórico traz as contagens; `usuario` → 403 — 9 testes |
| CT-HIS-008 | RF-HIS-006 | PDF da turma com 2 páginas por certificado, headers e conteúdo (nomes, número, instrutor, unidade); PDF individual pelo número reflete inscrição corrigida com número igual; sem certificado / número inexistente → 404; `usuario` → 403 — 4 testes |

## Impacto e Riscos

Fases A–B sem migração. Fase C: migração `0004` aditiva (três colunas anuláveis). Fase D: migração `0007` (duas tabelas novas). O contrato só acrescenta campos. Suíte `condomed`: 125 testes OK em 2026-09-09 (SQLite). Risco baixo: as consultas com `inscricoes__*` + `distinct()` podem ficar lentas com dezenas de milhares de inscrições — hoje são dezenas. Se crescer, o caminho é anotar contagens em vez de `prefetch_related`.
