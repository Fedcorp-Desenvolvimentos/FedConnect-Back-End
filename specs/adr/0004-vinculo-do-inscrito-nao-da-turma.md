# ADR-0004 — Administradora e condomínio são do inscrito, não da turma

> **Status:** decidido · **Dono:** Ingrid Aylana · **Data:** 2026-09-04
> **Pode ser adiada:** não (é o modelo de dados; adiar significa cadastrar turma errada)
> **Contexto(s):** `FCB` · **Specs:** `specs/curso-cipa/`
> **Substitui parcialmente:** ADR-0001 (a parte "cliente da turma: administradora + condomínio")

## Contexto

O modelo original assumia que **uma turma atende um cliente**: `TurmaCipa` guardava `administradora_codigo`, `administradora_nome` e `condominio_nome`, e cada inscrito era um funcionário daquele condomínio. Essa premissa veio do levantamento inicial e não se sustentou: a Condomed abre uma turma por dia em cada local e **preenche as vagas com funcionários de várias administradoras e vários condomínios** — a turma é um dia de curso, não o curso de um cliente.

Com o vínculo na turma, o operador não tem onde registrar de quem é cada participante: ou cria uma turma por condomínio (e desperdiça as 30 vagas do auditório), ou registra todos sob a administradora errada. A informação existe no nível do funcionário, não da turma.

Não há dado a preservar: a tela nunca ficou utilizável em produção — nenhum usuário tinha o nível `condomed` para acessá-la (confirmado com o dono em 2026-09-04).

## Decisão

`administradora_codigo`, `administradora_nome` e `condominio_nome` saem de `TurmaCipa` e entram em `InscricaoCipa`, obrigatórios por inscrito. A turma passa a ser o que ela é: **local, data, horário, situação e observação**, mais a lista de inscritos.

Como consequência de identidade: a turma deixa de ter nome. Onde a interface mostrava o condomínio (etiqueta no calendário, painel lateral, título da lista de inscritos), passa a mostrar **local + ocupação** — "Auditório · 12/30". Decisão do dono em 2026-09-04, entre um campo livre de identificação da turma e a lista derivada das administradoras presentes.

A migração é destrutiva: remove os três campos de `TurmaCipa` e cria os três em `InscricaoCipa` sem copiar nada.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Manter na turma e abrir uma turma por condomínio | baixo | Desperdiça as vagas do local (30 no auditório) e multiplica turmas em dias que só cabem uma; é o problema relatado |
| Duplicar: manter na turma **e** acrescentar no inscrito | alto | Duas fontes para o mesmo fato; a da turma vira mentira na primeira turma mista |
| Mover para o inscrito (escolhida) | médio | Migração destrutiva e retrabalho na tela; é o único que representa a operação real |
| Tabela de clientes da turma (N:N turma↔condomínio) | alto | Modela o mesmo fato duas vezes: o vínculo já vem por inscrito, e o conjunto é derivável |

## Consequências

**Modelo.** `InscricaoCipa` ganha `administradora_codigo`, `administradora_nome` e `condominio_nome`. `TurmaCipa` perde os três; `__str__` passa a usar local e data. O espelho na agenda (ADR-0001) tinha `tema="Curso CIPA — <condomínio>"` e passa a `tema="Curso CIPA — <local>"`, já que não há mais um condomínio da turma.

**Contrato.** A resposta da turma ganha `administradoras` e `condominios`: as listas **derivadas** e sem repetição do que os inscritos declaram. São somente-leitura e existem para a interface poder rotular, filtrar e buscar sem baixar todos os inscritos de todas as turmas do mês. Turma vazia devolve as duas listas vazias.

**Regras que não mudam.** Conflito por local+dia, espelho atômico na sala de reunião, capacidade por local, CPF válido, unicidade de CPF por turma e o aviso de CPF em outra turma (ADR-0003) seguem iguais — nenhuma delas dependia do cliente da turma. O `verificar-cpf` passa a devolver também a administradora e o condomínio de cada inscrição encontrada, que é o que dá sentido ao aviso quando a mesma pessoa aparece por dois condomínios.

**Interface.** O seletor de administradora sai do formulário de turma e entra no formulário de inscrito, junto de um condomínio digitado. A busca da barra de filtros passa a olhar as listas derivadas da turma, e ganha sentido novo: "quais turmas têm gente da administradora X".

**Risco assumido.** Digitar administradora e condomínio a cada inscrito é mais trabalho de digitação do que uma vez por turma. Mitigação prevista: o formulário repete o vínculo do último inscrito adicionado na mesma sessão, porque na prática as pessoas entram em blocos por condomínio. Se isso não bastar, o próximo passo é um seletor "aplicar a todos os selecionados" na lista — não um campo de volta na turma.
