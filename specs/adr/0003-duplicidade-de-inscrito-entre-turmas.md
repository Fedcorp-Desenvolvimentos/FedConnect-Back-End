# ADR-0003 — Duplicidade de inscrito entre turmas avisa, não bloqueia

> **Status:** decidido · **Dono:** Ingryd Aylana · **Data:** 2026-09-01
> **Pode ser adiada:** não (define se o operador consegue ou não concluir um cadastro legítimo)
> **Contexto(s):** `FCB` · **Specs:** `specs/curso-cipa/`

## Contexto

O mesmo CPF inscrito duas vezes costuma ser engano do operador, mas nem sempre: o curso CIPA se repete (mandato novo, reciclagem), e a mesma pessoa pode aparecer em turmas de condomínios diferentes. Dentro de **uma** turma a repetição nunca faz sentido — é lista de presença do mesmo dia. Entre turmas, faz.

Como a tela carrega um mês por vez e apenas os inscritos da turma aberta, o operador não tem como saber que aquele CPF já está em outro lugar.

## Decisão

Duplicidade **na mesma turma** continua bloqueada (HTTP 400, mais `unique_together (turma, cpf)` no banco). Duplicidade **entre turmas** é permitida: a API aceita, e a tela avisa antes de gravar, listando onde o CPF já consta, para o operador confirmar ou desistir.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Bloquear em qualquer turma | baixo | Impede reciclagem e a mesma pessoa em condomínios diferentes; o operador ficaria sem saída pela tela |
| Bloquear só no mesmo dia | baixo | Cobre o impossível (duas turmas 09:00–17:30), mas não pega o engano comum, que é repetir dias depois |
| Avisar e deixar o operador decidir (escolhida) | baixo | Pega o engano sem criar parede; exige uma consulta a mais antes de gravar |

## Consequências

Nasce `GET cursos-cipa/verificar-cpf/`, que devolve as turmas onde o CPF aparece (condomínio, local, data, situação), com `excluir_turma` para tirar a turma aberta da resposta. A tela consulta antes de gravar, e só quando o CPF é novo ou mudou numa edição.

A regra de decisão fica na tela, não na API — quem chamar a API direto grava sem aviso. É intencional: a API continua permitindo o caso legítimo, e o aviso é do fluxo de trabalho. Se um dia o bloqueio tiver de valer para todo mundo, ele sobe para o serializer e este ADR é substituído.

A consulta falhando não trava o cadastro: o hook devolve lista vazia e a gravação segue. Perder o aviso é aceitável; perder o cadastro, não.
