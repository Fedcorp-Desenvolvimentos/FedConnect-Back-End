# Requisitos — Agendamento de cursos CIPA (Condomed)

> **Rastreabilidade** — RF: RF-CIP-001..004 · RNF: RNF-CIP-001..003 · ADR: ADR-0001, ADR-0003..0005 · Questões: PA-001..006
> **Status:** em revisão · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-04

## Contexto e Problema

`[E]` A Condomed (setor de medicina e segurança do trabalho da Fedcorp) comercializa o curso CIPA para condomínios das administradoras; técnicos do setor ministram o curso no auditório (prédio próximo à matriz) ou na sala de reunião da empresa (relato do operacional, 2026-08-26). Hoje não há onde agendar turmas nem registrar os funcionários do condomínio participantes. `[E]` A agenda atual só conhece a sala de reunião como premissa embutida — `agenda/models.py:7-24` (`Reserva` sem campo de local) — e não valida conflito no servidor (`agenda/serializers.py`, sem `validate()`). `[D]` Decisão da operação: tela e API próprias para o CIPA, com dois calendários, cruzando com a agenda da sala de reunião (ADR-0001).

**Correção de premissa (2026-09-04).** A primeira versão assumia uma turma por cliente: a turma guardava a administradora e o condomínio, e os inscritos eram funcionários daquele condomínio. `[D]` Não é assim que a operação funciona: a turma é um dia de curso em um local, e as vagas são preenchidas com funcionários de **várias** administradoras e condomínios. O vínculo é do funcionário, não da turma (ADR-0004).

## Escopo

**Dentro do escopo:**
- Turmas CIPA por local (auditório | sala de reunião), um dia por turma, 09:00–17:30
- Lista de inscritos com limite de capacidade, cada um com seu vínculo: administradora (do Firebird) e nome do condomínio
- Conjunto de administradoras e condomínios da turma **derivado** dos inscritos, para rotular e filtrar
- Criação de turma com a lista de inscritos de uma vez, a partir de planilha, e a planilha modelo para download
- Espelho da turma na agenda atual quando o local é a sala de reunião
- Acesso restrito a `condomed` + `admin`

**Fora do escopo:**
- Vínculo com faturamento/comercialização (PA-005), notificação/certificado/lista de presença (PA-003)
- Correção da validação de conflito da agenda atual (PA-004)
- Cadastro de funcionários de condomínio (dados são digitados por turma)

## User Stories e Critérios de Aceitação

### RF-CIP-001: Agendar turma por local e dia

**Como** operador da Condomed, **quero** agendar uma turma CIPA em um local e dia, **para** organizar a operação dos cursos.

- **QUANDO** informo local e data válidos, **ENTÃO** o sistema **DEVE** criar a turma com `hora_inicio=09:00` e `hora_fim=17:30` e status `agendada`. A turma não tem cliente: administradora e condomínio são de cada inscrito. `[D]` ADR-0004
- **SE** já existe turma ativa no mesmo local e dia com horário sobreposto, **ENTÃO** o sistema **DEVE** rejeitar com HTTP 409 indicando a turma conflitante. `[D]` ADR-0001
- **QUANDO** consulto turmas por mês/ano e local, **ENTÃO** o sistema **DEVE** listar apenas as turmas daquele local no período, cada uma com as administradoras e os condomínios dos seus inscritos, sem repetição. `[D]` ADR-0004

### RF-CIP-002: Sala de reunião compartilhada com a agenda

**Como** operador, **quero** que um curso na sala de reunião bloqueie a sala na agenda atual (e vice-versa), **para** nunca haver curso e reunião ao mesmo tempo.

- **QUANDO** uma turma é criada com `local=SALA_REUNIAO`, **ENTÃO** o sistema **DEVE** criar, na mesma transação, uma `agenda.Reserva` vinculada cobrindo 09:00–17:30 daquele dia. `[D]` ADR-0001
- **SE** existe `agenda.Reserva` no dia cujo intervalo sobrepõe 09:00–17:30, **ENTÃO** a criação da turma na sala **DEVE** ser rejeitada com HTTP 409. `[D]` ADR-0001
- **QUANDO** a turma na sala é cancelada ou excluída, **ENTÃO** a Reserva espelho **DEVE** ser removida na mesma transação. `[D]` ADR-0001
- **QUANDO** excluo uma turma, **ENTÃO** o sistema **DEVE** remover em cascata as inscrições dela e liberar o dia do local para uma turma nova. `[D]` ADR-0001
- **QUANDO** marco a turma como cancelada, **ENTÃO** o sistema **DEVE** preservar as inscrições e ainda assim liberar a sala na agenda — é a alternativa não destrutiva à exclusão. `[D]` ADR-0001

### RF-CIP-003: Inscritos da turma

**Como** operador, **quero** registrar os funcionários inscritos com o condomínio e a administradora de cada um, **para** controlar presença, capacidade e de quem é cada participante.

- **QUANDO** informo nome, CPF, função, e-mail e telefone de um inscrito, **ENTÃO** o sistema **DEVE** gravá-lo vinculado à turma. `[P]` PA-002
- **QUANDO** informo a administradora (da lista do Firebird) e o nome do condomínio do inscrito, **ENTÃO** o sistema **DEVE** gravá-los na inscrição, e **DEVE** recusar a inscrição sem esses dois campos. `[D]` ADR-0004
- **SE** o mesmo CPF aparece em outra turma, **ENTÃO** a resposta de `verificar-cpf` **DEVE** informar também a administradora e o condomínio de cada inscrição encontrada. `[D]` ADR-0004
- **SE** o CPF já está inscrito na mesma turma, **ENTÃO** o sistema **DEVE** rejeitar com HTTP 400 — a tela avisa antes, mas o servidor é a garantia. `[D]` ADR-0001
- **SE** o CPF já está inscrito em **outra** turma, **ENTÃO** o sistema **DEVE** aceitar a inscrição e informar em quais turmas ele consta — o bloqueio é só dentro da mesma turma. `[D]` ADR-0003
- **SE** a turma já atingiu a capacidade do local, **ENTÃO** o sistema **DEVE** rejeitar a inscrição com HTTP 400. `[P]` PA-001
- **SE** o CPF é inválido (dígitos verificadores), **ENTÃO** o sistema **DEVE** rejeitar com HTTP 400. `[D]` ADR-0001
- **QUANDO** edito um inscrito já cadastrado, **ENTÃO** o sistema **DEVE** aceitar a alteração mesmo com a turma na capacidade, aplicando as mesmas regras de CPF válido e não duplicado — o CPF dele próprio não conta como duplicidade. `[D]` ADR-0001

### RF-CIP-004: Acesso restrito

**Como** administrador, **quero** que só o setor Condomed e admins agendem cursos, **para** proteger a agenda de uso indevido.

- **QUANDO** o usuário tem `nivel_acesso` em {`condomed`, `admin`}, **ENTÃO** os endpoints `cursos-cipa/*` **DEVEM** responder normalmente. `[E]` níveis existentes em `users/models.py:39-49` (sem `condomed` hoje — será adicionado)
- **SE** o usuário autenticado tem outro nível, **ENTÃO** os endpoints **DEVEM** responder HTTP 403. `[E]` padrão `users/permissions.py` (`IsAdminOrModerador`)

### RF-CIP-005: Turma e inscritos de uma planilha

**Como** operador da Condomed, **quero** criar a turma já com a lista de participantes vinda de uma planilha, **para** não digitar 30 pessoas uma a uma.

- **QUANDO** envio local, data e uma lista de inscritos válidos, **ENTÃO** o sistema **DEVE** criar a turma, o espelho na agenda (se for a sala) e todas as inscrições **na mesma transação**. `[D]` ADR-0005
- **SE** qualquer linha é inválida, **ENTÃO** o sistema **DEVE** recusar a importação inteira e devolver o erro por índice de linha, sem gravar nada. `[D]` ADR-0005
- **SE** o mesmo CPF aparece duas vezes na lista, **ENTÃO** o sistema **DEVE** recusar apontando a linha anterior. `[D]` ADR-0005
- **SE** a lista tem mais pessoas do que a capacidade do local, **ENTÃO o** sistema **DEVE** recusar a importação inteira dizendo quantas são e quantas cabem — nunca cortar a lista por conta própria. `[D]` ADR-0005
- **SE** o local e o dia já estão ocupados, **ENTÃO** o sistema **DEVE** responder 409 como em qualquer criação de turma, sem gravar inscrição nenhuma. `[D]` ADR-0005
- **QUANDO** peço a planilha modelo, **ENTÃO** o sistema **DEVE** devolver um `.xlsx` com os cabeçalhos dos campos do inscrito e uma linha de exemplo, **sem** colunas de local e data. `[D]` ADR-0005

## Requisitos Não Funcionais

### RNF-CIP-001: Conflito validado no servidor

Toda regra de conflito (RF-CIP-001, RF-CIP-002) é aplicada no serializer/serviço, independentemente do frontend — diferente da agenda atual. `[E]` lacuna documentada em `agenda/serializers.py` (sem `validate()`)

### RNF-CIP-002: Espelho atômico

Criação/remoção da turma e da Reserva espelho ocorrem em `transaction.atomic()`; falha em qualquer lado desfaz ambos. `[D]` ADR-0001

### RNF-CIP-003: Dados pessoais

Os dados dos inscritos (CPF, e-mail, telefone) só são expostos aos níveis autorizados (RF-CIP-004) e nunca aparecem em logs. `[D]` ADR-0001

## Questões em Aberto

- PA-001: **fechada (2026-08-31)** — auditório 30, sala de reunião 10
- PA-002: **fechada (2026-08-31)** — cinco campos do inscrito; o campo de técnico instrutor foi retirado do escopo pelo dono em 2026-08-31, junto com o código do condomínio
- PA-003, PA-004, PA-005: fora do escopo inicial (registradas)
