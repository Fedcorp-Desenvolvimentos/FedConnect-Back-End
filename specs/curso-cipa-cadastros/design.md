# Design — Cadastro de palestrantes e de locais do CIPA

> **Rastreabilidade** — RF: RF-CIP-006..007 · RNF: RNF-CIP-004..006 · INV: — · ADR: ADR-0001, ADR-0006, ADR-0007 · Questões: PA-010, PA-011
> **Status:** aprovado · **Dono:** Ingrid Aylana · **Atualizado:** 2026-09-09
> **Baseado em:** `requirements.md` (aprovado em 2026-09-08 — respostas do dono a PA-010/PA-011 e instrução "segue o que dá pra fazer")

## Visão Geral da Solução

Dois modelos novos, `LocalCipa` e `InstrutorCipa`, no lugar das constantes `LOCAIS_CIPA` e `INSTRUTORES_CIPA`; `TurmaCipa.local` e `TurmaCipa.instrutor` viram FK. **O contrato com o frontend não muda:** `local` e `instrutor` continuam viajando como `codigo` (string estável — `AUDITORIO`, `SALA_REUNIAO`, `FELIPE`, `VINICIUS`, e os gerados para registros novos), via `SlugRelatedField`. Dois viewsets de cadastro sob o mesmo `IsCondomedOrAdmin`, registrados no router **antes** de `cursos-cipa` para `cursos-cipa/locais/` não cair no `pk` do viewset de turmas. A assinatura é `ImageField` no storage padrão, que passa a ser S3 quando `AWS_STORAGE_BUCKET_NAME` existe.

## Arquitetura

| Arquivo | Mudança |
|---|---|
| `condomed/models.py` | `UNIDADES`/`UNIDADE_CHOICES` (unidade emissora continua no código); `LocalCipa` (`codigo` único, `nome`, `predio`, `capacidade`, `unidade`, `compartilha_sala_reuniao`, `ativo`); `InstrutorCipa` (`codigo` único, `nome`, `titulo`, `registro_mte`+`registro_uf` únicos juntos, `assinatura` ImageField, `ativo`); `gerar_codigo(nome, existentes)`; `TurmaCipa.local` FK `PROTECT`, `TurmaCipa.instrutor` FK `SET_NULL`; `LOCAIS_CIPA`/`INSTRUTORES_CIPA` ficam só como semente da migração |
| `condomed/migrations/0005_cadastros_locais_e_instrutores.py` | cria os modelos, adiciona `local_ref`/`instrutor_ref` e **semeia** (RunPython): dois locais, dois instrutores com a assinatura copiada de `condomed/assets/` para o storage, e cada turma apontando para o registro. Reversível |
| `condomed/migrations/0006_turma_aponta_para_cadastros.py` | remove os `CharField` antigos, renomeia as FKs para `local`/`instrutor`, recria o índice `local+data` |
| `condomed/services.py` | espelho na agenda e conflito de sala passam a olhar `turma.local.compartilha_sala_reuniao`; `capacidade_do_local(local)` lê do registro; `sala_compartilhada_em_uso()` |
| `condomed/serializers.py` | `CodigoField` (`SlugRelatedField` por `codigo`, `""`→`None` e `None`→`""`); `LocalCipaSerializer` (nome único entre ativos, capacidade ≥ 1, no máximo uma sala da agenda, `codigo` gerado no create, `turmas` contadas); `InstrutorCipaSerializer` (assinatura write-only PNG/JPEG ≤ 500 KB, `tem_assinatura`, `registro` formatado, MTE+UF únicos com mensagem no campo, `ativo` com default também em multipart); `TurmaCipaSerializer`/`ImportarTurmaSerializer` usam `CodigoField` e recusam cadastro desativado em turma nova ou na troca |
| `condomed/views.py` | saem as actions `locais`/`instrutores`; entram `CadastroCipaViewSet` (lista só ativos salvo `?todos=1`; `DELETE` com turma → 400 orientando a desativar) e as subclasses `LocalCipaViewSet`/`InstrutorCipaViewSet`; `select_related("local", "instrutor")`; filtro `?local=` por código |
| `condomed/documentos.py` | cabeçalho lê `turma.local` (nome, capacidade, `unidade_dados`) e `turma.instrutor` (nome, título, `registro`) |
| `bigcorp/urls.py` | `cursos-cipa/locais` e `cursos-cipa/instrutores` registrados antes de `cursos-cipa` |
| `bigcorp/settings.py` | `MEDIA_URL`/`MEDIA_ROOT`; com `AWS_STORAGE_BUCKET_NAME`, `STORAGES.default` = `storages.backends.s3.S3Storage` (bucket privado, sem ACL, sem querystring auth) |
| `requirements.txt` | `django-storages[s3]` |

## Modelo de Dados e Contratos

- `GET/POST cursos-cipa/locais/`, `GET/PATCH/DELETE cursos-cipa/locais/{id}/` → `{id, codigo, nome, predio, capacidade, unidade: {nome, endereco, telefone, email, cidade}, unidade_codigo, compartilha_sala_reuniao, ativo, turmas, criado_em}`. Entrada: `nome`, `predio`, `capacidade`, `unidade_codigo` (hoje só `RIO`), `compartilha_sala_reuniao`, `ativo`. `?todos=1` inclui inativos.
- `GET/POST cursos-cipa/instrutores/`, `GET/PATCH/DELETE cursos-cipa/instrutores/{id}/` → `{id, codigo, nome, titulo, registro_mte, registro_uf, registro, tem_assinatura, ativo, turmas, criado_em}`. Entrada JSON ou multipart; `assinatura` só entra (arquivo), nunca sai. `?todos=1` inclui inativos.
- Turma (`cursos-cipa/`, `historico/`, `participantes/`, `verificar-cpf/`, `importar/`): `local` e `instrutor` **continuam códigos**; `local_nome`, `instrutor_nome`, `capacidade`, `acima_da_capacidade`, `tem_espelho` continuam derivados. `?local=` filtra por código. Local desativado em turma nova → `400 {"local": ...}`; idem instrutor.
- `DELETE` de cadastro com turma vinculada → `400 {"detail": "... Desative-o ..."}`.
- Erros de validação nos cadastros sempre por campo (`nome`, `capacidade`, `compartilha_sala_reuniao`, `registro_mte`, `assinatura`), para a tela mostrar no lugar certo.

## Fluxo Principal

1. Tela de cadastros lista `locais/?todos=1` e `instrutores/?todos=1` e filtra inativos localmente.
2. Novo palestrante: `POST instrutores/` (multipart quando há assinatura) → `codigo` gerado do nome; aparece no select da turma na próxima carga.
3. Desativar: `PATCH {ativo: false}` → sai das listas sem `todos`, some das opções; turmas antigas seguem legíveis (FK intacta, `PROTECT`/`SET_NULL`).
4. Deploy: `migrate` roda 0005 (semente + upload das duas assinaturas para o storage configurado) e 0006. Nenhuma turma muda de local ou instrutor.

## Tratamento de Erros e Casos de Borda

| Falha | Comportamento | Requisito |
|---|---|---|
| Nome de local repetido entre ativos (case-insensitive) | 400 `nome` | RF-CIP-007 |
| Capacidade < 1 | 400 `capacidade` | RF-CIP-007 |
| Segundo local ativo com `compartilha_sala_reuniao` | 400 `compartilha_sala_reuniao` | RF-CIP-007 · ADR-0001 |
| MTE+UF repetidos | 400 `registro_mte` (validador automático desligado para a mensagem cair no campo) | RF-CIP-006 |
| Assinatura > 500 KB ou não PNG/JPEG | 400 `assinatura` | RF-CIP-006 · RNF-CIP-005 |
| Multipart sem `ativo` | mantém o default (`True`), não vira `False` | RF-CIP-006 |
| `DELETE` com turma vinculada | 400 orientando a desativar | RF-CIP-006/007 |
| Turma nova (ou troca) com cadastro desativado | 400 no campo; turma antiga continua válida e emite | RF-CIP-006/007 |
| Instrutor sem assinatura | aceito no cadastro; a emissão do certificado recusa (fase D) | RF-CIP-006 |
| Nível sem acesso | 403 | RNF-CIP-006 |

## Decisões

- **Contrato por `codigo`, não por id** (ajusta RNF-CIP-004): os quatro códigos originais continuam válidos, o frontend não precisa migrar chaves, os testes existentes continuam citando `AUDITORIO`/`FELIPE`, e um registro novo ganha código derivado do nome (`SALA_2`), estável mesmo se renomeado. Custo: `SlugRelatedField` faz uma consulta por campo — irrelevante para dois selects.
- **Unidade emissora fica no código** (fora do escopo do requisito): há uma só; o local escolhe entre as conhecidas.
- **`PROTECT` no local, `SET_NULL` no instrutor**: apagar um local com turma é erro de operação; apagar um instrutor sem turma é limpeza. Com turma, os dois só desativam (PA-010).
- **Assinatura em `ImageField` + storage configurável** (PA-011): mesmo código em dev (disco) e prod (S3); a migração 0005 faz o upload das duas assinaturas legadas para onde o storage apontar.
- **Migração em dois passos** (0005 semeia com FKs provisórias, 0006 troca os campos): permite reverter a 0006 sem perder o mapeamento e deixa a semente auditável.

## Divergência vs. produção

Nenhuma duplicata em `consultas/`/`fedhub/`: o módulo é só `condomed/`. Produção ainda não tem as migrações 0004–0006; o deploy precisa de `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` no App Platform **antes** do `migrate`, senão as assinaturas semeadas vão para o disco efêmero (a 0005 é idempotente: com o bucket configurado depois, basta limpar `assinatura` dos dois registros e rodar de novo, ou reenviar pela tela).

## Estratégia de Testes

| CT | Requisito | Caso |
|---|---|---|
| CT-CIP-021 | RF-CIP-006, RNF-CIP-005 | semente preserva os dois instrutores com assinatura; criar com assinatura (multipart) e listar sem expor o arquivo; criar sem assinatura e anexar depois; MTE repetido → 400 em `registro_mte`; assinatura grande → 400; excluir com turma → 400, desativar tira da lista/das opções e mantém a turma; excluir sem turma → 204 |
| CT-CIP-022 | RF-CIP-007 | semente preserva os dois locais e a marca da sala; criar local e usá-lo em turma (`tem_espelho` nulo); nome repetido, capacidade 0 e segunda sala da agenda → 400; capacidade alterada reflete em `acima_da_capacidade`; espelho na agenda segue a marca; excluir com turma → 400, desativado sai das opções e o histórico continua |
| CT-CIP-023 | RNF-CIP-004, RNF-CIP-006 | contrato por código; local inexistente → 400; `usuario` → 403; `condomed` cadastra |

16 testes em `CadastrosCipaTests`; suíte `condomed` com 112 testes OK (SQLite, 2026-09-08).

## Impacto e Riscos

- Migração com dados: 0005 escreve em disco/S3 durante o `migrate`. Se o storage S3 estiver mal configurado o `migrate` falha no upload — melhor falhar ali do que descobrir na emissão.
- Frontend: `ORDEM_LOCAIS` e `CORES_LOCAL` fixos saem; a tela passa a montar abas, legenda e cores a partir da lista. Lado frontend em `FedConnect-FrontEnd-Prod/specs/curso-cipa-cadastros/`.
- `django-storages`/`boto3` só são importados quando o bucket está configurado; sem o pacote instalado e sem a variável, nada muda.
