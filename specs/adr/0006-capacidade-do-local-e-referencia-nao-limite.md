# ADR-0006 — Capacidade do local é referência, não limite

> **Status:** decidido · **Dono:** Ingrid Aylana · **Data:** 2026-09-04
> **Pode ser adiada:** não (é regra de negócio em produção; enquanto vale, a operação fica sem registrar quem participou)
> **Contexto(s):** `FCB` · **Specs:** `specs/curso-cipa/`
> **Revoga:** INV-CIP-003 na forma original ("o número de inscritos nunca excede a capacidade do local")

## Contexto

O modelo assumia que a capacidade do local é um limite: 30 no auditório, 10 na sala de reunião, e a inscrição de número 31 recebia 400. A capacidade veio de PA-001, fechada com a operação em 2026-08-31, e foi implementada como invariante (INV-CIP-003), com `select_for_update` na turma para nem em corrida estourar.

A operação informou em 2026-09-04 que não é assim que o dia acontece: **chegam funcionários extras de última hora** e o curso os recebe. Trazem mais uma cadeira, imprimem mais material, e a turma segue. Com o limite valendo, o sistema recusa exatamente quem apareceu — e a pessoa faz o curso sem estar na lista. O registro fica errado, o que é pior do que um número acima do previsto.

## Decisão

A capacidade passa a ser **referência**, não limite:

- A inscrição individual não é mais recusada por capacidade.
- A importação por planilha aceita lista maior que a capacidade (revoga a decisão do ADR-0005 de recusar).
- A resposta da turma ganha `acima_da_capacidade`: quantas pessoas passam da capacidade, `0` quando está dentro. A tela sinaliza a partir daí, sem recontar a regra.
- INV-CIP-003 deixa de ser "nunca excede" e passa a ser "o excesso é sempre visível": a garantia não é mais impedir, é não deixar acontecer sem ninguém saber.

O `select_for_update` sai junto: existia só para a capacidade não ser estourada em corrida. A unicidade de CPF por turma continua garantida pelo `unique_together` no banco, que é onde ela sempre esteve.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Manter o limite | baixo | É o estado atual e produz registro errado: a pessoa faz o curso e não consta na lista |
| Limite com margem fixa (capacidade + 10%) | baixo | Número inventado; três a mais no auditório passa e o quarto não, sem nenhuma razão de operação |
| Campo "capacidade excepcional" por turma | médio | Mais um dado para o operador preencher antes de saber quantos vão aparecer; resolve por burocracia o que é só um aviso |
| Capacidade como referência, com o excesso sinalizado (escolhida) | baixo | O sistema descreve o que aconteceu e avisa quem precisa providenciar cadeira |

## Consequências

`acima_da_capacidade` é calculado no serializer, sobre os inscritos já carregados — a listagem do mês usa `prefetch_related`, então não custa consulta a mais.

A tela precisa avisar em três lugares (contador do painel de inscritos, prévia da importação e alertas do mês) e não bloquear em nenhum: é o par desta decisão no registro de ADRs do `FedConnect-FrontEnd-Prod` (número 0008 de lá).

O que **não** muda: CPF válido, CPF único por turma, vínculo obrigatório, conflito de local/dia e espelho na agenda. Nenhuma dessas dependia da capacidade.

Fica um efeito colateral aceito: a ocupação por local pode passar de 100% no painel. É informação correta — a turma está acima do previsto —, e esconder isso seria voltar a fingir que o limite existe.
