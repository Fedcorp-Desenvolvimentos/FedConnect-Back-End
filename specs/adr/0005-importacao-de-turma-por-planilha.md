# ADR-0005 — Importação por planilha: uma transação, tudo-ou-nada, sem local e data na planilha

> **Status:** decidido · **Dono:** Ingrid Aylana · **Data:** 2026-09-04
> **Pode ser adiada:** não (define o contrato da importação e o formato do modelo)
> **Contexto(s):** `FCB` · **Specs:** `specs/curso-cipa/`

## Contexto

Uma turma no auditório são até 30 participantes, cada um com cinco campos obrigatórios (administradora, condomínio, nome, CPF e função). Digitar isso a cada turma é o trabalho que a tela deveria poupar, e as listas já chegam à Condomed em planilha, mandadas pelos condomínios.

O repositório já tem um padrão para planilha: o app `planilha` gera o modelo com openpyxl e recebe o arquivo para processar (`planilha-modelo-cpf`, `processar-cpf-planilha`). Mas ali o processamento é uma consulta em massa que devolve outro arquivo — aqui o resultado é **escrita** no banco, com regras de negócio (capacidade, CPF único por turma, conflito de dia) que não existem numa consulta.

## Decisão

**Um endpoint, uma transação.** `POST cursos-cipa/importar/` recebe `{local, data, observacao, inscricoes: [...]}` e cria a turma, o espelho na agenda (se for a sala) e todas as inscrições dentro de `transaction.atomic()`. Criar a turma numa requisição e a lista em outra deixaria turma vazia no sistema quando a segunda metade falhasse — e turma vazia por acidente é pior que erro nenhum, porque ocupa o dia do local.

**Tudo-ou-nada no servidor.** Qualquer linha inválida recusa a importação inteira, com o erro por índice de linha. A tela valida antes e só envia o que passou, então um 400 aqui significa divergência entre as duas validações — não é o caminho normal, e nesse caso gravar metade seria o pior resultado.

**Capacidade excedida recusa, não corta.** Lista com 35 pessoas para um local de 30 devolve 400 dizendo quantas são e quantas cabem. Cortar as cinco últimas faria a ordem das linhas da planilha decidir quem participa do curso — isso é decisão da operação, não do software.

**A planilha não traz local nem data.** O modelo tem só as sete colunas do inscrito. Local e dia são escolhidos na tela: data em célula é o erro mais caro de achar depois (cria turma em dia errado, que passa a bloquear aquele dia), e "uma planilha = uma turma" mantém o conflito de dia/local sendo resolvido de uma vez, não linha a linha.

**O CPF é texto no modelo.** A coluna vem formatada como texto porque o Excel come o zero à esquerda de CPF que comece com zero, e a linha volta inválida sem o operador entender por quê.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Upload do arquivo para o Django, como no app `planilha` | médio | O servidor teria de ler xlsx e devolver relatório; a tela perde a pré-visualização e o operador só descobre o problema depois de enviar |
| Duas requisições (criar turma, depois inscrever em lote) | baixo | Simples de escrever e deixa turma vazia quando a segunda falha; a turma vazia ainda ocupa o dia |
| Uma requisição atômica com a lista pronta (escolhida) | baixo | A tela lê e valida a planilha; o servidor recebe JSON e aplica as mesmas regras |
| Local e data como colunas da planilha (várias turmas por arquivo) | alto | Mais poderoso e bem mais perigoso: erro de data cria turma em dia errado e o 409 passa a ser por linha |
| Cortar a lista na capacidade e reportar o excedente | baixo | A ordem das linhas decidiria quem faz o curso |

## Consequências

O `ImportarTurmaSerializer` reusa `TurmaCipaSerializer` para a turma e `InscricaoCipaSerializer` para cada linha: a importação não afrouxa nenhuma regra, e o 409 de conflito de dia sobe igual ao da criação normal. A duplicidade de CPF **dentro da planilha** ganha validação explícita — o `unique_together` do banco pegaria, mas sem dizer em qual linha.

`COLUNAS_MODELO`, em `condomed/views.py`, é o contrato com o parser da tela: o frontend casa as colunas pelo texto do cabeçalho. Mudar um cabeçalho aqui é mudar lá, e a spec do frontend registra isso.

Fica um caminho não coberto de propósito: importar planilha para uma turma **que já existe**. A rota de inscrição individual continua sendo a única forma de crescer uma turma criada antes — se a operação pedir, é um endpoint irmão (`inscricoes/lote/`) reusando o mesmo serializer de linha.
