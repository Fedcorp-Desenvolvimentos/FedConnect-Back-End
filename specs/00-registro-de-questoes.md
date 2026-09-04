# Registro de questões abertas

> **Atualizado:** 2026-08-31

Toda `PA-###` citada em qualquer spec deste repositório nasce e vive aqui. Questão fechada não some: recebe status `fechada`, a resposta e a data. O número nunca é reciclado.

Formato de cada entrada: título, status (`aberta` | `fechada`), dono, severidade (`bloqueia` | `alta` | `média` | `baixa`), o que trava, e — quando fechada — a resposta.

---

## PA-001 — Capacidade real dos locais

- **Status:** fechada (2026-08-31) · **Dono:** Ingrid Aylana · **Severidade:** alta
- **Trava:** RF-CIP-003 (limite de inscritos por turma).
- **Questão:** quantas pessoas cabem no auditório e na sala de reunião? Hipótese de trabalho: constante `LOCAIS_CIPA` com valores provisórios a confirmar com a Condomed.
- **Resposta (2026-08-31):** auditório 30 lugares, sala de reunião 10. Valores fixados em `condomed/models.py` (`LOCAIS_CIPA`).

## PA-002 — Campos do inscrito e identidade do técnico

- **Status:** fechada (2026-08-31) · **Dono:** Ingrid Aylana · **Severidade:** média
- **Trava:** RF-CIP-003 (formulário de inscritos), RF-CIP-001 (campo técnico).
- **Questão:** os campos do funcionário do condomínio são nome, CPF, função, e-mail e telefone — falta algum (RG, data de nascimento para certificado)? O técnico instrutor é usuário do sistema (nível `condomed`) ou nome livre? Hipótese: usuário do sistema, nullable.
- **Resposta (2026-08-31):** os cinco campos bastam (nome, CPF, função, e-mail, telefone); não há cadastro de funcionários. O campo de técnico instrutor foi **retirado** do escopo (decisão do dono, 2026-08-31) — assim como o código do condomínio, que passa a ser só o nome digitado.

## PA-003 — Notificação ao cliente / lista de presença / certificado

- **Status:** aberta · **Dono:** Ingrid Aylana · **Severidade:** baixa
- **Trava:** nada no escopo inicial.
- **Questão:** a turma agendada deve gerar e-mail ao condomínio/administradora, lista de presença ou certificado? Se sim, é spec própria; padrão de e-mail a copiar é `questionarios/views.py:_enviar_email` (via FedHub, timeout curto).

## PA-004 — Agenda atual sem validação de conflito no servidor

- **Status:** aberta · **Dono:** Ingrid Aylana · **Severidade:** média
- **Trava:** nada no CIPA (que valida no servidor e consulta as Reservas); é dívida pré-existente da `agenda`.
- **Questão:** `agenda/serializers.py` não tem `validate()` e o model não tem constraint — duas reservas conflitantes entram por POST direto ou abas simultâneas. Corrigir na agenda (spec própria) ou aceitar?

## PA-005 — Vínculo do curso com a comercialização

- **Status:** aberta · **Dono:** Ingrid Aylana · **Severidade:** baixa
- **Trava:** nada no escopo inicial.
- **Questão:** o curso CIPA é produto vendido — a turma precisa se ligar a proposta/contrato/fatura (Firebird) para controle de faturamento? Fora do escopo até decisão.

## PA-006 — Uma turma atende um condomínio ou vários?

- **Status:** fechada (2026-09-04) · **Dono:** Ingrid Aylana · **Severidade:** bloqueia
- **Trava:** o modelo de dados de `TurmaCipa` e `InscricaoCipa`.
- **Questão:** o levantamento inicial tratou a turma como "o curso de um condomínio", com administradora e condomínio na turma. Uma turma pode receber funcionários de administradoras diferentes?
- **Resposta:** sim, e é a regra, não a exceção. A turma é um dia de curso em um local; as vagas são preenchidas com funcionários de várias administradoras e condomínios. Administradora e condomínio passam para a inscrição, obrigatórios (ADR-0004). A turma deixa de ter nome e passa a ser identificada por local + ocupação.
