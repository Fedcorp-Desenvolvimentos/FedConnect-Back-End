# ADR-0007 — Documentos do CIPA são gerados do registro a cada download, nunca armazenados

> **Status:** decidido · **Dono:** Ingrid Aylana · **Data:** 2026-09-08
> **Pode ser adiada:** não (define como a lista de presença e, depois, o certificado existem)
> **Contexto(s):** `FCB` · **Specs:** `specs/curso-cipa-historico/`

## Contexto

A fase 2 do CIPA pede três documentos: lista de presença para assinatura no dia, e depois certificado por participante. Havia dois caminhos: gerar o PDF uma vez e guardar o arquivo (em disco ou no banco), ou gerar a cada download a partir do que está no registro.

O repositório já gera PDF em outros módulos (boletos, faturas, vistorias) com ReportLab, sempre sob demanda, sem armazenar. E o dado do CIPA muda até o dia do curso: chega inscrito, sai inscrito, troca o instrutor. Um PDF guardado na criação da turma estaria errado no dia de imprimir.

## Decisão

**Gerar sob demanda, do registro; não armazenar.** `GET cursos-cipa/{id}/lista-presenca/` monta o PDF na hora com ReportLab (platypus) a partir da turma e dos inscritos. Mudança de layout vale para o próximo download; o conteúdo é sempre o do banco. O mesmo vale para o certificado (fase D), com uma diferença que fica para lá: o certificado terá um **registro** próprio (número, data de emissão) — o PDF continua sendo regenerado, mas o número não muda.

**Lista sempre disponível**, inclusive para turma futura ou sem inscritos: é para levar impressa; a data do curso não é condição.

**Ordem por condomínio, depois nome.** A assinatura acontece em bloco: os funcionários de um condomínio chegam juntos e assinam juntos.

**Linhas em branco numeradas no fim** (cinco, por hipótese — PA-007), porque chegam funcionários de última hora (ADR-0006) e a lista impressa é onde eles assinam. O que entrou à mão vira inscrição no sistema depois.

**A regra fica separada do desenho.** `linhas_lista_presenca` e `cabecalho_lista_presenca` são funções puras (ordem, extras, resolução de unidade e instrutor) e são o que os testes cobrem; `gerar_lista_presenca` só desenha.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Gerar e armazenar o PDF na criação da turma | médio | Fica errado a cada inscrição nova; precisaria de invalidação e de um lugar para guardar arquivo |
| Gerar sob demanda (escolhida) | baixo | Padrão do repositório; conteúdo sempre atual; custo de CPU irrelevante para dezenas de turmas |
| Gerar no navegador (jsPDF) | baixo | O front já lê planilha, mas assets (logo, assinatura) e fonte da verdade estão no servidor; dois geradores para o mesmo documento é o certificado desalinhar da lista |
| Ordem por nome | baixo | Simples, mas quebra o fluxo real de assinatura por condomínio |

## Consequências

`condomed/documentos.py` nasce como o módulo de documentos do CIPA; o certificado entra nele. Assets em `condomed/assets/` são lidos do disco na geração — se faltar o logo, o cabeçalho sai só com texto (não quebra).

O `Content-Disposition` é exposto ao CORS (`Access-Control-Expose-Headers`) porque o front usa o nome de arquivo que o servidor decide: `lista-presenca-cipa-<data>-<local>.pdf`. Sem expor, o navegador esconde o header e o download sairia com nome genérico.

A4 paisagem: são sete colunas, a de assinatura precisa de largura. O certificado terá o próprio formato (16:9, ADR próprio na fase D).
