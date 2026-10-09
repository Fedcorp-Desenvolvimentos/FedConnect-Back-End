# Requisitos — Autorização do cadastro por objeto × aba × ação (`cadastro/*` e `users/me/`)

> **Rastreabilidade** — RF: RF-CAD-004..013 · RNF: RNF-CAD-004..006 · INV: INV-CAD-004..013 · CT: CT-CAD-007..023 · ADR: ADR-0011 (proposto), ADR-0008 · Questões: PA-027, PA-029..040
> **Status:** rascunho · **Dono:** Hamilton (produto; aprova a spec diretamente) `[D]` PA-040 · **Atualizado:** 2026-10-08
> **Par:** `FedConnect-FrontEnd/specs/cadastro-object-pages/` (abas, botões e rotas por capacidade) · `FedHub-Backend/specs/etl-object-pages/` (rotas novas do contrato e da administradora, inclusive as de pessoas decididas em 08/10 — PA-040; `X-Operador` em toda escrita) · emenda `specs/cadastro-etl/` (RF-CAD-003 e ADR-0008 decisão 5)

## Contexto e Problema

**Pedido.** `[E]` Em 07/10/2026 o dono pediu, por mensagem repassada por Lucas Guidi, "um esquema de acesso que nos permita fazer a gestão por abas, bloqueando acessos indevidos" (o texto não está na transcrição do áudio das 09:38, que trata das abas e das faturas do contrato — `FedConnect-FrontEnd/specs/cadastro-object-pages/`). O cadastro está migrando para o padrão lista + página de objeto com abas; cada aba nova é um ponto de acesso novo.

**Estado atual (verificado em 2026-10-07, Django `main@52c07e7`, Front `main@ad51004`, FedHub `main@014ffaa`).**

- `[E]` A autorização do cadastro no Django é binária e por prefixo: a rota curinga `cadastro/<path:rota>` (`bigcorp/urls.py:286`) passa por JWT + `IsAuthenticated` e por uma tupla única `NIVEIS_TELA = ("admin", "financeiro", "faturamento-analista", "comercial")` (`fedhub/views/cadastro_view.py:20`), checada antes de chamar o FedHub (`fedhub/views/cadastro_view.py:38-39`). Quem passa, vê, exporta e grava tudo sob `/api/etl/*`, inclusive o Admin de dados (`admin/linhas`, `admin/papeis/{id}/converter`).
- `[E]` O proxy sabe método, rota, query e e-mail do JWT (`fedhub/views/cadastro_view.py:43-54`); a rota relativa a `/api/etl/` identifica objeto e aba, e o método identifica a ação. Nenhuma camada usa isso hoje.
- `[E]` O FedHub só conhece o `client_id` do bearer (`FedHub-Backend/src/modules/etl/controller.py:55-62`) e exige `X-Operador` apenas em `/admin/*` (`FedHub-Backend/src/modules/etl/controller.py:354-359`).
- `[E]` `GET users/me/` devolve o `UsuarioSerializer` (`users/views.py:89-93`), com `nivel_acesso` e nada sobre capacidades.
- `[E]` `POST users/` é `AllowAny` e sem autenticação (`users/views.py:31-33,40-43`), e `nivel_acesso`, `is_active` e `is_fed` são graváveis por qualquer chamador (`users/serializers.py:17-26`): um anônimo pode criar usuário `admin`, e um usuário comum pode se promover por `PATCH users/{seu_id}/` (`IsOwnerOrAdmin`, `users/permissions.py:49-68`). Lido no código; não confirmado com requisição real.
- `[E]` O login Google cria usuário para qualquer conta Google (`users/views.py:147-153`, `get_or_create` sem checagem de domínio).
- `[E]` `CORS_ALLOW_HEADERS = list(default_headers)` (`bigcorp/settings.py:249`): `Idempotency-Key` e `X-Request-Id`, que o proxy promete repassar (ADR-0008 decisão 3), não estão liberados para o navegador; não há `CORS_EXPOSE_HEADERS`.
- `[E]` 401/403 vindos do FedHub são repassados tal qual (`fedhub/services/cadastro_service.py:49-57`); o Front trata 401 como sessão expirada.
- `[E]` **Regressão do Front, commit `e6d97e6` (01/10/2026):** `cadastroPessoas` voltou a `["admin", "ti"]` (`FedConnect-FrontEnd/src/utils/routeAccess.js:42`), com o comentário da linha 41 dizendo o contrário. Front e Django se contradizem nos dois sentidos: financeiro, faturamento-analista e comercial não veem o menu; `ti` vê o menu e recebe 403 (`fedhub/test_cadastro_proxy.py:119-123`).
- `[P]` PA-027 (`ti` entra?) continua aberta desde 23/09.

**Problema:** não há como liberar uma aba sem liberar o módulo inteiro, nem separar ver de exportar ou de gravar; o servidor não sabe quem exportou o quê; e há dois buracos de escalação de privilégio no app `users`. Este documento especifica a autorização por capacidade, com fonte única no Django.

## Escopo

**Dentro do escopo:** catálogo e matriz de capacidades (`users/capacidades.py`); `capacidades` em `GET users/me/`; decisão por capacidade no proxy `cadastro/*` com mapa (método, rota) → capacidade (`fedhub/cadastro_permissoes.py`) e negação por padrão; modo sombra; cliente próprio `fedconnect-cadastro`; CORS dos headers do proxy; conversão de 401/403 do FedHub; correção dos buracos do app `users`; log de negação, exportação e escrita.

**Fora do escopo:** abas, botões e rotas do Front (par `FedConnect-FrontEnd/specs/cadastro-object-pages/`); rotas novas e `X-Operador` obrigatório no FedHub (par `FedHub-Backend/specs/etl-object-pages/`); tabela de perfis com tela de administração e exceções por pessoa (PA-033); refresh token em cookie `HttpOnly` e `SECRET_KEY` sem default (riscos registrados no levantamento de 07/10, cada um com spec ou correção próprios); autorização das telas fora do cadastro.

## Vocabulário e catálogo

`[P]` Hipótese de trabalho (ADR-0011, proposto; aprovação em PA-038):

```
capacidade := "cad:" objeto ":" aba ":" acao
objeto     := administradora | condominio | contrato | funcionario | comissionado | seguradora | produto | admin_dados | comum
acao       := ver | exportar | criar | editar | vincular | excluir | fundir | converter
```

Catálogo fechado (`CATALOGO_CAPACIDADES`). Não existe aba "Apólices" no contrato: a apólice é a divisão (sem sequência), e as divisões ficam na aba `divisoes`. `[D]` PA-040 (decisão do dono, 08/10)

A coluna "Servidor" diz se o proxy consegue cobrar a capacidade por rota própria; "só interface" é aba montada sobre o payload de outra rota, que o Front esconde mas o servidor cobra pela rota de origem.

| Objeto | Aba | Ações | Servidor |
|---|---|---|---|
| `administradora` | `lista` | ver, exportar | sim |
| `administradora` | `dados` | ver, criar, editar, vincular | sim |
| `administradora` | `condominios`, `contratos`, `faturas`, `pdd`, `comissoes`, `grupos` | ver, exportar | sim |
| `administradora` | `pessoas` | ver, exportar (dado pessoal: lista por CPF) | sim |
| `administradora` | `historico` | ver | reservada (sem rota) |
| `condominio` | `lista` | ver, exportar | sim |
| `condominio` | `dados` | ver, criar, editar | sim |
| `condominio` | `funcionarios`, `produtos`, `contratos`, `faturas`, `boletos` | ver, exportar | sim |
| `condominio` | `vinculos` | ver (só interface, payload de `dados:ver`), vincular | vincular: sim |
| `contrato` | `lista` | ver, exportar | sim |
| `contrato` | `dados` | ver, criar, editar (reservada: não existe `PUT contratos/{id}`) | ver e criar: sim |
| `contrato` | `parceiros`, `produtos` | ver, exportar | só interface (payload de `dados:ver`) |
| `contrato` | `participantes`, `faturas` | ver, exportar | sim |
| `contrato` | `pessoas` | ver, exportar (dado pessoal: lista por CPF) | sim |
| `contrato` | `divisoes` | ver, exportar, fundir (simular e confirmar) | sim |
| `funcionario` | `lista` | ver, exportar | sim |
| `funcionario` | `dados` | criar; ver e editar reservadas (sem rota) | criar: sim |
| `comissionado`, `seguradora` | `lista` | ver, exportar | sim |
| `comissionado`, `seguradora` | `dados` | ver, criar | sim |
| `produto` | `lista`, `produtos`, `faturamento` | ver, exportar | sim |
| `produto` | `regras` | ver | sim |
| `produto` | `boletos` | exportar (aba só de exportação) | sim |
| `produto` | `dados` | criar | sim |
| `admin_dados` | `parceiros` | ver | sim |
| `admin_dados` | `linhas` | criar, editar | sim |
| `admin_dados` | `regras` | ver (só interface, rota de `produto:regras:ver`), criar, excluir | criar e excluir: sim |
| `admin_dados` | `conversao` | converter | sim |
| `comum` | `referencias`, `totais` | ver (derivadas — INV-CAD-005, INV-CAD-006) | sim |

## Matriz inicial papel × capacidade

`[P]` Proposta a confirmar pelo dono; `?` marca a célula que depende da questão da última coluna, e todo o conjunto depende de PA-038. `●` concedida, `○` negada. Níveis `usuario`, `moderador`, `recepcionista`, `vistoria`, `condomed` e `esocial` não recebem nada, como hoje (`fedhub/views/cadastro_view.py:20`). `admin` recebe o catálogo inteiro (INV-CAD-008).

| Capacidades | admin | ti | financeiro | faturamento-analista | comercial | faturamento | Questões |
|---|---|---|---|---|---|---|---|
| `cad:*:lista:ver` (entra no módulo) | ● | ●? | ● | ● | ● | ●? | PA-027, PA-030 |
| `cad:{administradora,condominio,contrato}:lista:exportar` | ● | ●? | ● | ● | ○? | ○? | PA-027, PA-029, PA-030 |
| `cad:administradora:{dados,condominios,contratos,grupos,faturas}:ver` | ● | ●? | ● | ● | ● | ●? | PA-027, PA-030 |
| `cad:administradora:{condominios,contratos,grupos}:exportar` | ● | ●? | ● | ● | ○? | ○? | PA-027, PA-029, PA-030 |
| `cad:administradora:faturas:exportar` | ● | ○? | ● | ● | ○? | ●? | PA-027, PA-029, PA-030 |
| `cad:administradora:pdd:ver` | ● | ○? | ● | ● | ○? | ○? | PA-027, PA-029, PA-030 |
| `cad:administradora:pdd:exportar` | ● | ○? | ● | ○? | ○? | ○? | PA-031, PA-029 |
| `cad:administradora:comissoes:{ver,exportar}` | ● | ○? | ● | ○? | ○? | ○ | PA-031, PA-029 |
| `cad:administradora:pessoas:ver` (dado pessoal) | ● | ○? | ● | ● | ○? | ○ | PA-027, PA-029 |
| `cad:administradora:pessoas:exportar` (dado pessoal) | ● | ○? | ●? | ○? | ○ | ○ | PA-029, PA-031, PA-038 |
| `cad:administradora:dados:{criar,editar,vincular}` | ● | ○? | ● | ●? | ●? | ○ | PA-027, PA-031, PA-029 |
| `cad:condominio:{dados,produtos,contratos,vinculos,faturas,boletos}:ver` | ● | ●? | ● | ● | ● | ●? | PA-027, PA-030 |
| `cad:condominio:{produtos,contratos}:exportar` | ● | ●? | ● | ● | ○? | ○? | PA-027, PA-029, PA-030 |
| `cad:condominio:{faturas,boletos}:exportar` | ● | ○? | ● | ● | ○? | ●? | PA-027, PA-029, PA-030 |
| `cad:condominio:funcionarios:ver` (dado pessoal) | ● | ○? | ● | ● | ○? | ○ | PA-027, PA-029 |
| `cad:condominio:funcionarios:exportar` (dado pessoal) | ● | ○? | ●? | ○? | ○ | ○ | PA-029, PA-031, PA-038 |
| `cad:condominio:dados:{criar,editar}` e `cad:condominio:vinculos:vincular` | ● | ○? | ● | ●? | ●? | ○ | PA-027, PA-031, PA-029 |
| `cad:contrato:{dados,parceiros,produtos,participantes,faturas,divisoes}:ver` | ● | ●? | ● | ● | ● | ●? | PA-027, PA-030 |
| `cad:contrato:{parceiros,produtos,participantes,divisoes}:exportar` | ● | ●? | ● | ● | ○? | ○? | PA-027, PA-029, PA-030 |
| `cad:contrato:faturas:exportar` | ● | ○? | ● | ● | ○? | ●? | PA-027, PA-029, PA-030 |
| `cad:contrato:pessoas:ver` (dado pessoal) | ● | ○? | ● | ● | ○? | ○ | PA-027, PA-029 |
| `cad:contrato:pessoas:exportar` (dado pessoal) | ● | ○? | ●? | ○? | ○ | ○ | PA-029, PA-031, PA-038 |
| `cad:contrato:dados:criar` | ● | ○? | ● | ●? | ●? | ○ | PA-027, PA-031, PA-029 |
| `cad:contrato:divisoes:fundir` (simular e confirmar) | ● | ○ | ○? | ○? | ○ | ○ | PA-038 |
| `cad:funcionario:lista:ver` (dado pessoal) | ● | ○? | ● | ● | ○? | ○ | PA-027, PA-029 |
| `cad:funcionario:lista:exportar` (dado pessoal) | ● | ○? | ○? | ○? | ○ | ○ | PA-029, PA-038 |
| `cad:funcionario:dados:criar` | ● | ○ | ● | ●? | ○? | ○ | PA-031, PA-029 |
| `cad:{comissionado,seguradora}:{lista,dados}:ver` | ● | ●? | ● | ● | ● | ●? | PA-027, PA-030 |
| `cad:{comissionado,seguradora}:lista:exportar` | ● | ○? | ● | ● | ○? | ○ | PA-027, PA-029 |
| `cad:{comissionado,seguradora}:dados:criar` | ● | ○ | ● | ●? | ●? | ○ | PA-031, PA-029 |
| `cad:produto:{lista,produtos,faturamento,regras}:ver` | ● | ●? | ● | ● | ● | ●? | PA-027, PA-030 |
| `cad:produto:{lista,produtos,faturamento}:exportar` | ● | ○? | ● | ● | ○? | ○ | PA-027, PA-029 |
| `cad:produto:boletos:exportar` (CSV de boletos da competência) | ● | ○ | ○? | ○? | ○ | ○ | PA-032 |
| `cad:produto:dados:criar` | ● | ○ | ● | ○? | ○? | ○ | PA-031, PA-029 |
| `cad:admin_dados:*` | ● | ○? | ○? | ○? | ○? | ○ | PA-027, PA-038 |

Leitura: financeiro fica como hoje, menos Admin de dados, CSV de boletos e exportação da lista global de funcionários; faturamento-analista perde comissões e a exportação de PDD; comercial perde dado pessoal e exportações; faturamento puro ganha leitura (hoje 403); `ti` lê e não grava.

`[P]` PA-029 — as abas `administradora:pessoas` e `contrato:pessoas` (lista de pessoas por CPF) recebem o mesmo tratamento de dado pessoal de `condominio:funcionarios`: ver só `admin`, `financeiro` e `faturamento-analista` (`ti` e `comercial` pendentes); exportar só `admin`, com `financeiro` pendente.

Toda redução em relação a hoje aparece primeiro como linha "negaria" no modo sombra (RF-CAD-007), antes de bloquear.

## Mapa (método, rota) → capacidade

`[P]` Hipótese de trabalho (ADR-0011, proposto; PA-038). Rota relativa a `/api/etl/`, a mesma `rota` que o proxy já valida (`fedhub/views/cadastro_view.py:40-42`). Lista ordenada; a primeira regra que casa vence. "Lista = sim" indica rota paginada em que a capacidade exigida é `:ver` ou `:exportar` conforme RF-CAD-006 (escrito `:*` na tabela); "não" exige a capacidade escrita, sempre. "Nova" = rota da spec `FedHub-Backend/specs/etl-object-pages/`, mapeada antes de existir.

| # | Método | Rota (regex) | Capacidade | Lista | Nota |
|---|---|---|---|---|---|
| 1 | GET | `^totais$` | `cad:comum:totais:ver` | não | |
| 2 | GET | `^referencias$` | `cad:comum:referencias:ver` | não | |
| 3 | GET | `^documentos/[^/]+$` | `cad:comum:referencias:ver` | não | revela o dono de um CPF/CNPJ |
| 4 | GET | `^parceiros/semelhantes$` | `cad:comum:referencias:ver` | não | |
| 5 | GET | `^administradoras/sugestoes$` | `cad:administradora:lista:ver` | não | autocomplete |
| 6 | GET | `^administradoras/ufs$` | `cad:administradora:lista:ver` | não | |
| 7 | GET | `^administradoras$` | `cad:administradora:lista:*` | sim | |
| 8 | GET | `^administradoras/\d+$` | `cad:administradora:dados:ver` | não | traz `quantitativos` (contagens, sem dado pessoal; PA-040) |
| 9 | GET | `^administradoras/\d+/formulario$` | `cad:administradora:dados:editar` | não | formulário só para quem edita |
| 10 | GET | `^administradoras/\d+/condominios$` | `cad:administradora:condominios:*` | sim | |
| 11 | GET | `^administradoras/\d+/contratos/filtros$` | `cad:administradora:contratos:ver` | não | nova (opções dos combos) |
| 12 | GET | `^administradoras/\d+/contratos$` | `cad:administradora:contratos:*` | sim | |
| 13 | GET | `^administradoras/\d+/grupos$` | `cad:administradora:grupos:*` | sim | nova (grupos que a administradora trabalha) |
| 14 | GET | `^administradoras/\d+/faturas/exercicios$` | `cad:administradora:faturas:ver` | não | |
| 15 | GET | `^administradoras/\d+/faturas$` | `cad:administradora:faturas:*` | sim | |
| 16 | GET | `^faturas/\d+$` | `cad:administradora:faturas:ver` | não | sem tela hoje |
| 17 | GET | `^administradoras/\d+/boletos-sem-baixa$` | `cad:administradora:pdd:*` | sim | |
| 18 | GET | `^administradoras/\d+/comissoes$` | `cad:administradora:comissoes:*` | sim | |
| 19 | GET | `^administradoras/\d+/pessoas$` | `cad:administradora:pessoas:*` | sim | nova (PA-040); dado pessoal (CPF) |
| 20 | POST | `^administradoras$` | `cad:administradora:dados:criar` | não | |
| 21 | PUT | `^administradoras/\d+$` | `cad:administradora:dados:editar` | não | |
| 22 | POST | `^administradoras/\d+/grupos$` | `cad:administradora:dados:vincular` | não | mesma rota da 13, outro método |
| 23 | GET | `^condominios/sugestoes$` | `cad:condominio:lista:ver` | não | autocomplete |
| 24 | GET | `^condominios/ufs$` | `cad:condominio:lista:ver` | não | |
| 25 | GET | `^condominios$` | `cad:condominio:lista:*` | sim | |
| 26 | GET | `^condominios/\d+$` | `cad:condominio:dados:ver` | não | traz vínculos e comissionados |
| 27 | GET | `^condominios/\d+/formulario$` | `cad:condominio:dados:editar` | não | |
| 28 | GET | `^condominios/\d+/funcionarios$` | `cad:condominio:funcionarios:*` | sim | dado pessoal |
| 29 | GET | `^condominios/\d+/produtos$` | `cad:condominio:produtos:*` | sim | |
| 30 | GET | `^condominios/\d+/contratos$` | `cad:condominio:contratos:*` | sim | |
| 31 | GET | `^condominios/\d+/faturas/exercicios$` | `cad:condominio:faturas:ver` | não | |
| 32 | GET | `^condominios/\d+/faturas$` | `cad:condominio:faturas:*` | sim | |
| 33 | GET | `^condominios/\d+/boletos$` | `cad:condominio:boletos:*` | sim | |
| 34 | POST | `^condominios$` | `cad:condominio:dados:criar` | não | |
| 35 | PUT | `^condominios/\d+$` | `cad:condominio:dados:editar` | não | |
| 36 | POST | `^condominios/\d+/administradoras$` | `cad:condominio:vinculos:vincular` | não | |
| 37 | PATCH | `^condominios/\d+/administradoras/\d+$` | `cad:condominio:vinculos:vincular` | não | encerrar vínculo |
| 38 | GET | `^contratos/grupos$` | `cad:contrato:lista:ver` | não | |
| 39 | GET | `^contratos$` | `cad:contrato:lista:*` | sim | |
| 40 | GET | `^contratos/\d+$` | `cad:contrato:dados:ver` | não | traz parceiros e produtos |
| 41 | GET | `^contratos/\d+/participantes$` | `cad:contrato:participantes:*` | sim | |
| 42 | GET | `^contratos/\d+/pessoas$` | `cad:contrato:pessoas:*` | sim | nova (PA-040); dado pessoal (CPF) |
| 43 | GET | `^contratos/\d+/faturas/exercicios$` | `cad:contrato:faturas:ver` | não | nova |
| 44 | GET | `^contratos/\d+/faturas$` | `cad:contrato:faturas:*` | sim | nova |
| 45 | GET | `^contratos/\d+/divisoes$` | `cad:contrato:divisoes:*` | sim | nova |
| 46 | POST | `^contratos/\d+/divisoes/fundir$` | `cad:contrato:divisoes:fundir` | não | nova; a mesma capacidade para simular (`simular: true`) e confirmar |
| 47 | POST | `^contratos$` | `cad:contrato:dados:criar` | não | |
| 48 | GET | `^funcionarios$` | `cad:funcionario:lista:*` | sim | dado pessoal |
| 49 | POST | `^funcionarios$` | `cad:funcionario:dados:criar` | não | |
| 50 | GET | `^comissionados/sugestoes$` | `cad:comissionado:lista:ver` | não | autocomplete |
| 51 | GET | `^comissionados$` | `cad:comissionado:lista:*` | sim | |
| 52 | GET | `^comissionados/\d+$` | `cad:comissionado:dados:ver` | não | |
| 53 | POST | `^comissionados$` | `cad:comissionado:dados:criar` | não | |
| 54 | GET | `^seguradoras$` | `cad:seguradora:lista:*` | sim | |
| 55 | GET | `^seguradoras/\d+$` | `cad:seguradora:dados:ver` | não | |
| 56 | POST | `^seguradoras$` | `cad:seguradora:dados:criar` | não | |
| 57 | GET | `^catalogo/grupos$` | `cad:produto:lista:*` | sim | |
| 58 | GET | `^grupos-produto/faturamento$` | `cad:produto:lista:*` | sim | |
| 59 | GET | `^grupos-produto/boletos$` | `cad:produto:boletos:exportar` | não | sempre exportar |
| 60 | GET | `^grupos-produto/\d+/faturamento$` | `cad:produto:faturamento:*` | sim | |
| 61 | GET | `^grupos-produto/\d+/faturas$` | `cad:produto:faturamento:*` | sim | |
| 62 | GET | `^grupos-produto/\d+/papeis$` | `cad:produto:regras:ver` | não | |
| 63 | GET | `^catalogo/produtos/\d+/coberturas$` | `cad:produto:produtos:ver` | não | |
| 64 | GET | `^catalogo/produtos$` | `cad:produto:produtos:*` | sim | |
| 65 | POST | `^catalogo/produtos$` | `cad:produto:dados:criar` | não | |
| 66 | GET | `^admin/tabelas$` | `cad:admin_dados:parceiros:ver` | não | |
| 67 | GET | `^admin/parceiros(/busca)?$` | `cad:admin_dados:parceiros:ver` | não | dado pessoal |
| 68 | GET | `^admin/parceiros/\d+$` | `cad:admin_dados:parceiros:ver` | não | dado pessoal |
| 69 | PATCH | `^admin/linhas/[a-z_]+/[^/]+$` | `cad:admin_dados:linhas:editar` | não | |
| 70 | POST | `^admin/linhas/grupo_produto_papel$` | `cad:admin_dados:regras:criar` | não | antes da regra 71 |
| 71 | POST | `^admin/linhas/[a-z_]+$` | `cad:admin_dados:linhas:criar` | não | |
| 72 | DELETE | `^admin/linhas/grupo_produto_papel/[^/]+$` | `cad:admin_dados:regras:excluir` | não | único DELETE hoje |
| 73 | POST | `^admin/papeis/\d+/converter$` | `cad:admin_dados:conversao:converter` | não | |
| — | qualquer | `health`, `lacunas` e tudo o mais (inclusive `contratos/{id}/apolices` e `contratos/{id}/divisoes/{id}`, que não existem — PA-040) | não mapeada | — | 403 `rota_nao_mapeada` |

## User Stories e Critérios de Aceitação

### RF-CAD-004: Catálogo e matriz de capacidades

**Como** dono do produto, **quero** decidir por papel o que cada um vê, exporta e grava em cada aba, **para** liberar uma aba sem liberar o módulo inteiro.

- O sistema **DEVE** manter em `users/capacidades.py` o catálogo fechado `CATALOGO_CAPACIDADES` (§Vocabulário e catálogo) e a matriz `MATRIZ = {nivel_acesso: [padrões]}` (§Matriz inicial), com curinga `*` por segmento, e expor `capacidades_de(usuario) -> frozenset[str]`, que expande os curingas contra o catálogo e aplica as derivações. `[P]` PA-038 · ADR-0011 (proposto)
- **ENQUANTO** a matriz existir, ela **DEVE** satisfazer INV-CAD-004..009 e INV-CAD-013; violação **DEVE** fazer `manage.py check` falhar com o nível e o padrão culpados (verificação registrada pelo app `users`). `[P]` PA-038
- **SE** um padrão da matriz não casar com nenhuma capacidade do catálogo, **ENTÃO** `manage.py check` **DEVE** falhar com o nome do padrão. `[P]` PA-038
- **QUANDO** o `nivel_acesso` do usuário não tiver linha na matriz, **ENTÃO** `capacidades_de` **DEVE** devolver conjunto vazio. `[P]` PA-038
- O conteúdo inicial da matriz é a tabela §Matriz inicial; cada célula com `?` segue a questão citada na linha. `[P]` PA-027, PA-029..032
- Mudar a matriz é mudança de código com teste (PR + deploy), nunca configuração em tempo de execução; exceções por pessoa ficam fora até PA-033. `[P]` PA-033

### RF-CAD-005: `capacidades` em `GET users/me/`

**Como** frontend, **quero** receber a lista do que o usuário pode, **para** esconder abas, botões e rotas sem manter lista de níveis.

- **QUANDO** o usuário autenticado chamar `GET users/me/`, **ENTÃO** a resposta **DEVE** incluir `capacidades: [string]`, lista plana, ordenada, sem curingas, igual a `sorted(capacidades_de(request.user))`, além de todos os campos atuais (inclusive `nivel_acesso`). `[E]` `users/views.py:89-93` · `[P]` PA-038
- O campo **DEVE** ser somente leitura: `capacidades` enviado em `POST/PUT/PATCH users/` **DEVE** ser ignorado. `[P]` PA-038
- **QUANDO** o nível não tiver linha na matriz, **ENTÃO** `capacidades` **DEVE** ser `[]` (nunca ausente). `[P]` PA-038

### RF-CAD-006: Proxy decide por capacidade

**Como** dono do produto, **quero** que o servidor bloqueie a aba, a exportação e a gravação que o papel não tem, **para** que esconder na tela não seja a única barreira.

- **QUANDO** o proxy receber `(método, rota)` já validada (`fedhub/views/cadastro_view.py:40-45`), **ENTÃO** **DEVE** resolver a capacidade exigida pelo mapa de `fedhub/cadastro_permissoes.py` (§Mapa; primeira regra que casa). `[E]` `fedhub/views/cadastro_view.py:40-42` · `[P]` PA-038
- **SE** nenhuma regra casar, **ENTÃO** o sistema **DEVE** responder 403 `{"erro": "rota_nao_mapeada", "mensagem": ...}` sem chamar o FedHub. `[P]` PA-038
- **SE** a capacidade exigida não estiver em `capacidades_de(request.user)`, **ENTÃO** o sistema **DEVE** responder 403 `{"erro": "sem_acesso", "mensagem": ..., "capacidade": "cad:..."}` sem chamar o FedHub. `[D]` ADR-0008 (formato `{"erro","mensagem"}`) · `[P]` PA-038 (campo `capacidade`)
- **QUANDO** a regra for de lista e a requisição trouxer `X-Finalidade: exportar` **OU** `limite` maior que 100, **ENTÃO** a capacidade exigida **DEVE** ser a `:exportar` da aba; caso contrário, a `:ver`. `limite` igual a 100 é `:ver`; `limite` não numérico é tratado como ausente (o FedHub valida). `[P]` PA-038
- **QUANDO** a rota for `GET grupos-produto/boletos`, **ENTÃO** a capacidade exigida **DEVE** ser `cad:produto:boletos:exportar`, com ou sem header. `[P]` PA-032
- **QUANDO** a rota for `GET administradoras/{id}/formulario` ou `GET condominios/{id}/formulario`, **ENTÃO** a capacidade exigida **DEVE** ser a `:dados:editar` do objeto. `[P]` PA-038
- O header `X-Finalidade` **NÃO DEVE** ser repassado ao FedHub (continua valendo a lista de ADR-0008 decisão 3). `[D]` ADR-0008
- **QUANDO** a fase 4 entrar (RF-CAD-007 com `CADASTRO_PERMISSOES_ENFORCE` verdadeiro em produção por uma semana sem negação indevida), **ENTÃO** `NIVEIS_TELA` **DEVE** ser removida de `fedhub/views/cadastro_view.py` e RF-CAD-003 de `specs/cadastro-etl/` passa a "substituído por RF-CAD-006". `[P]` PA-038

### RF-CAD-007: Ativação gradual (modo sombra)

- **ENQUANTO** `CADASTRO_PERMISSOES_ENFORCE` for falso (padrão; lido do ambiente), o sistema **DEVE** continuar exigindo `NIVEIS_TELA`, calcular a capacidade como em RF-CAD-006 e, quando a decisão fosse negar (rota não mapeada ou capacidade ausente), registrar `[cadastro] negaria <capacidade ou rota_nao_mapeada> para <email> em <método> <rota> request=<id>` e repassar como hoje. `[P]` PA-038
- **ENQUANTO** `CADASTRO_PERMISSOES_ENFORCE` for verdadeiro, o sistema **DEVE** negar conforme RF-CAD-006. `[P]` PA-038
- Voltar a flag para falso **DEVE** restaurar o comportamento anterior sem deploy de código. `[P]` PA-038

### RF-CAD-008: Mapa completo contra as rotas do FedHub

- O mapa **DEVE** ser uma lista ordenada de `(métodos, regex compilada, capacidade, lista)`; toda capacidade citada no mapa **DEVE** existir no catálogo. `[P]` PA-038
- O repositório **DEVE** ter uma lista fixa das rotas `/api/etl/*` do FedHub (método + caminho com parâmetros), copiada de `FedHub-Backend/specs/etl-cadastro-api/design.md` §Rotas e das specs filhas (inclusive `FedHub-Backend/specs/etl-object-pages/`), contendo no mínimo as rotas novas `GET contratos/{id}/faturas`, `GET contratos/{id}/faturas/exercicios`, `GET contratos/{id}/divisoes`, `POST contratos/{id}/divisoes/fundir`, `GET contratos/{id}/pessoas`, `GET administradoras/{id}/pessoas`, `GET administradoras/{id}/grupos` e `GET administradoras/{id}/contratos/filtros`. `[E]` `FedHub-Backend/src/modules/etl/controller.py:82-136,365-372,465-476` (67 rotas em `014ffaa`) · `[D]` PA-040 (rotas de pessoas; sem rota de apólices nem de divisão individual) · `[P]` PA-038
- **QUANDO** a suíte rodar, **ENTÃO** um teste **DEVE** falhar se alguma rota da lista não casar com regra do mapa, ou se `GET health`, `GET lacunas`, `GET contratos/{id}/apolices` ou `GET contratos/{id}/divisoes/{id}` casarem. `[P]` PA-038 · `[D]` PA-040
- Rota nova no FedHub sob `/api/etl` **DEVE** entrar na lista e no mapa antes de ser usada pelo Front; até lá responde 403 `rota_nao_mapeada` (reverte a consequência 1 do ADR-0008). `[P]` PA-038 · ADR-0011 (proposto)

### RF-CAD-009: Cliente próprio do cadastro no FedHub

- **QUANDO** `FEDHUB_CADASTRO_CLIENT_ID` e `FEDHUB_CADASTRO_CLIENT_SECRET` existirem no ambiente, **ENTÃO** `CadastroService` **DEVE** obter o bearer com o cliente `fedconnect-cadastro` (escopo `/api/etl` no FedHub) e nunca com o cliente `fedconnect`. `[E]` `fedhub/services/cadastro_service.py:44`, `consultas/utils/fedhub_auth.py:33-54` · `[P]` PA-038
- **SE** as envs não existirem, **ENTÃO** o sistema **DEVE** manter o comportamento atual (`get_auth_headers()`) e registrar um aviso uma vez por processo. `[P]` PA-038
- Os demais proxies do FedHub não mudam de cliente. `[E]` `consultas/utils/get_headers.py:9-24`

### RF-CAD-010: CORS dos headers do proxy

- `CORS_ALLOW_HEADERS` **DEVE** incluir, além de `default_headers`, `Idempotency-Key`, `X-Request-Id` e `X-Finalidade`. `[E]` `bigcorp/settings.py:249` (hoje só `default_headers`) · `[D]` ADR-0008 (decisão 3 promete repassar os dois primeiros)
- `CORS_EXPOSE_HEADERS` **DEVE** existir com `X-Request-Id`, `Idempotent-Replayed` e `Retry-After`, para o navegador ler os headers que o proxy devolve. `[E]` `fedhub/services/cadastro_service.py:30`, `fedhub/views/cadastro_view.py:56` · `[P]` PA-038

### RF-CAD-011: Credencial do FedHub recusada não é sessão expirada

- **QUANDO** o FedHub responder 401 ou 403, **ENTÃO** o proxy **DEVE** responder 502 `{"erro": "credencial_fedhub", "mensagem": ..., "origem": "fedconnect"}` e registrar em log status, rota e `request_id` (o FedHub não conhece o usuário final; a recusa dele é da credencial do Django). `[E]` `fedhub/services/cadastro_service.py:49-57` · `[P]` PA-038
- Os demais status do FedHub continuam repassados como estão. `[D]` ADR-0008

### RF-CAD-012: Usuários — fechar criação e escalação de privilégio

**Como** administrador, **quero** que só eu crie usuários e mude papéis, **para** que a matriz não possa ser contornada por quem escolhe o próprio papel.

- **QUANDO** `POST users/` chegar sem JWT, **ENTÃO** 401; **QUANDO** chegar de usuário não-admin, **ENTÃO** 403; só `admin` cria. `[E]` `users/views.py:31-33,40-43` (hoje `AllowAny`, sem autenticação) · `[P]` PA-035 (fluxo público que dependa disso)
- **QUANDO** um não-admin fizer `PUT/PATCH users/{id}/` com `nivel_acesso`, `is_active` ou `is_fed` diferentes dos atuais, **ENTÃO** o sistema **DEVE** responder 403 com a lista dos campos recusados, sem gravar nada; valor igual ao atual é aceito sem efeito. `[E]` `users/serializers.py:17-26` · `[P]` PA-035 (hipótese: recusar; alternativa: ignorar)
- **QUANDO** o login Google receber uma conta cujo domínio (claim `hd` do token e sufixo do e-mail) não esteja em `GOOGLE_LOGIN_DOMINIOS` (env, lista), **ENTÃO** **NÃO DEVE** criar usuário e **DEVE** responder 403; **QUANDO** criar, o `nivel_acesso` **DEVE** ser `usuario`. `[E]` `users/views.py:147-153` · `[P]` PA-039
- Esta entrega (fase 0) pode ser antecipada às demais por decisão do dono, por ser correção de segurança. `[P]` PA-035

### RF-CAD-013: Trilha de negação, exportação e escrita

- **QUANDO** o proxy negar (403 `sem_acesso` ou `rota_nao_mapeada`), **ENTÃO** **DEVE** registrar em log, nível `warning`: `request_id`, e-mail, método, rota sem query, capacidade exigida e código do erro. `[E]` `fedhub/services/cadastro_service.py:54,70` (hoje sem `request_id` nem e-mail) · `[P]` PA-038
- **QUANDO** o proxy repassar escrita (`POST/PUT/PATCH/DELETE`) ou exportação (capacidade `:exportar`), **ENTÃO** **DEVE** registrar em log, nível `info`: `request_id`, e-mail, método, rota sem query, capacidade e status do FedHub. `[P]` PA-038
- O log **NÃO DEVE** conter corpo, query string nem cabeçalhos de credencial (a query pode conter CPF em `busca`). `[E]` CONVENCOES §8

## Requisitos Não Funcionais

### RNF-CAD-004: Segurança

- Negação por padrão em três pontos: catálogo fechado (INV-CAD-007), nível sem linha na matriz = conjunto vazio (INV-CAD-009), rota sem regra = 403 (INV-CAD-011). `[P]` PA-038
- Nenhuma capacidade vem do cliente: nem do corpo, nem de header, nem de claim do JWT; a fonte é sempre `request.user.nivel_acesso` carregado do banco pelo `JWTAuthentication` (INV-CAD-012). `[E]` `bigcorp/settings.py:195-219` (JWT sem claims customizadas) · `[P]` PA-038
- Todo 403 do proxy (`sem_acesso`, `rota_nao_mapeada`) é respondido sem chamar o FedHub (INV-CAD-010). `[E]` `fedhub/views/cadastro_view.py:38-39` (já é assim para `NIVEIS_TELA`)

### RNF-CAD-005: Compatibilidade

- O 403 mantém `{"erro", "mensagem"}` e só acrescenta `capacidade`; `nivel_acesso` continua em `users/me/`; nenhuma rota do FedHub muda de contrato por causa desta spec; nenhum header novo chega ao FedHub. `[D]` ADR-0008 · `[P]` PA-038
- No modo sombra (RF-CAD-007) a resposta de toda requisição é idêntica à de hoje. `[P]` PA-038
- Nada é criado no god-object `consultas/services/fedhub_service.py`. `[E]` CLAUDE.md

### RNF-CAD-006: Desempenho

- `capacidades_de` é memoizada por `nivel_acesso` dentro do processo (sem consulta extra ao banco; invalidação = deploy); as regexes do mapa são compiladas no import; resolver a capacidade não faz I/O. `[P]` PA-038
- Nenhuma chamada HTTP nova do Front: `capacidades` vem no `GET users/me/` que o login e o reload já fazem. `[E]` `FedConnect-FrontEnd/src/services/userService.js:66`

## Invariantes

| ID | Afirmação | Onde é garantido |
|---|---|---|
| INV-CAD-004 | Toda capacidade `:exportar` concedida a um nível vem com a `:ver` da mesma aba, exceto em aba só de exportação declarada no catálogo (hoje só `cad:produto:boletos`). | aplicação — `check` do app `users` |
| INV-CAD-005 | Quem tem qualquer `criar`, `editar`, `vincular`, `excluir`, `fundir` ou `converter` tem `cad:comum:referencias:ver` (derivada, nunca escrita na matriz). | aplicação — `capacidades_de` |
| INV-CAD-006 | Quem tem qualquer `:lista:ver` tem `cad:comum:totais:ver` (derivada). | aplicação — `capacidades_de` |
| INV-CAD-007 | Nenhuma capacidade fora de `CATALOGO_CAPACIDADES` é concedida ou exigida; padrão que não casa com o catálogo é erro de configuração. | aplicação — `check` + teste do mapa |
| INV-CAD-008 | `admin` tem o catálogo inteiro; nenhum outro nível tem `cad:admin_dados:*` sem linha explícita na matriz. | aplicação — `check` |
| INV-CAD-009 | Nível sem linha na matriz tem conjunto vazio de capacidades. | aplicação — `capacidades_de` |
| INV-CAD-010 | Com `CADASTRO_PERMISSOES_ENFORCE` verdadeiro, nenhuma requisição chega ao FedHub sem capacidade resolvida pelo mapa e concedida ao usuário (sucede INV-CAD-001 de `specs/cadastro-etl/` na fase 4). | aplicação — `CadastroProxyView`, antes do service |
| INV-CAD-011 | Toda rota da lista fixa de rotas do FedHub casa com uma regra do mapa; `health`, `lacunas`, `contratos/{id}/apolices` e `contratos/{id}/divisoes/{id}` não casam (as duas últimas não existem — PA-040). | processo — teste de completude na suíte |
| INV-CAD-012 | Nenhuma capacidade é lida da requisição (corpo, query, header ou claim). | aplicação — `capacidades_de(request.user)` é a única fonte |
| INV-CAD-013 | Quem tem `cad:contrato:dados:criar` tem `cad:produto:produtos:ver` e `cad:produto:regras:ver` (o formulário de contrato usa `catalogo/produtos` e `grupos-produto/{id}/papeis`). | aplicação — `capacidades_de` |

## Fases (migração sem quebrar produção)

| Fase | Entrega aqui | Depende de | Reversão |
|---|---|---|---|
| 0 | RF-CAD-012 (correção de usuários) | PA-035, PA-039 | revert |
| 1 | `NIVEIS_TELA` e Front alinhados (o Front devolve `financeiro`, `faturamento-analista` e `comercial`); aqui só muda algo se PA-027 fechar | PA-027; par Front | revert |
| 2 | RF-CAD-004, 005, 007 (sombra), 008, 009, 010, 011 e 013 | PA-038 | flag + env |
| 3 | nada aqui; o Front consome `capacidades` | par Front | revert no Front |
| 4 | `CADASTRO_PERMISSOES_ENFORCE=true`; `NIVEIS_TELA` removida (RF-CAD-006) | uma semana de linhas "negaria" analisadas | flag para falso |

## Casos de teste (sem banco; `APIRequestFactory` + `requests` mockado, como `fedhub/test_cadastro_proxy.py:36-41`)

- CT-CAD-007 — `capacidades_de` para `admin` == catálogo; `usuario` e nível inexistente == conjunto vazio; `financeiro` contém `cad:administradora:faturas:exportar` e não contém `cad:admin_dados:linhas:editar`. _(RF-CAD-004)_
- CT-CAD-008 — matriz de teste com `:exportar` sem `:ver` faz o `check` falhar; padrão fora do catálogo faz falhar; `cad:produto:boletos:exportar` sozinho não falha; derivações de INV-CAD-005, INV-CAD-006 e INV-CAD-013 presentes. _(RF-CAD-004)_
- CT-CAD-009 — `GET users/me/` traz `capacidades` ordenada, sem `*`, e `nivel_acesso`; nível sem linha → `[]`; `PATCH users/{id}/` com `capacidades` não altera nada (serializer com contexto, `save` mockado). _(RF-CAD-005)_
- CT-CAD-010 — com enforce: `financeiro` em `GET administradoras/10/comissoes` → 200; `comercial` → 403 `sem_acesso` com `capacidade = cad:administradora:comissoes:ver` e `requests.request` não chamado; `GET lacunas` e `GET health` → 403 `rota_nao_mapeada`; `comercial` em `GET contratos/7/pessoas` e `GET administradoras/10/pessoas` → 403 `sem_acesso` (`pessoas:ver`), `faturamento-analista` → 200. _(RF-CAD-006)_
- CT-CAD-011 — `comercial` em `GET administradoras?limite=50` e `?limite=100` → 200; `?limite=500` → 403 (`:exportar`); sem `limite` e com `X-Finalidade: exportar` → 403; `financeiro` nos quatro → 200; `X-Finalidade` não aparece nos headers enviados ao FedHub. _(RF-CAD-006)_
- CT-CAD-012 — `GET grupos-produto/boletos?competencia=2026-09` por `financeiro` → 403, por `admin` → 200; `GET administradoras/10/formulario` e `PUT administradoras/10` por quem só tem `dados:ver` → 403; `POST condominios/5/administradoras` exige `vinculos:vincular`; `POST contratos/7/divisoes/fundir` exige `divisoes:fundir` com `simular: true` e com `simular: false`; `GET contratos/7/pessoas?limite=500` por `faturamento-analista` → 403 (`pessoas:exportar`). _(RF-CAD-006)_
- CT-CAD-013 — sem enforce: `comercial` em `comissoes` → 200 e uma linha `negaria` com `request=`; `usuario` → 403 `sem_acesso` (vale `NIVEIS_TELA`); `GET lacunas` por `admin` → repassado e linha `negaria rota_nao_mapeada`. _(RF-CAD-007)_
- CT-CAD-014 — toda rota da lista fixa (as 67 de `014ffaa` mais as novas de RF-CAD-008) casa com uma regra; `health`, `lacunas`, `GET contratos/1/apolices` e `GET contratos/1/divisoes/2` não casam; `GET administradoras/1/pessoas` resolve `administradora:pessoas:ver` e `GET contratos/1/pessoas` resolve `contrato:pessoas:ver`; nenhuma capacidade `cad:contrato:apolices:*` existe no catálogo; toda capacidade do mapa está no catálogo; `POST administradoras/1/grupos` resolve `dados:vincular` e `GET administradoras/1/grupos` resolve `grupos:ver`. _(RF-CAD-008)_
- CT-CAD-015 — com `FEDHUB_CADASTRO_CLIENT_ID/SECRET`, o `Authorization` enviado vem do cliente `fedconnect-cadastro` (`fedhub_auth` mockado); sem as envs, vem de `get_auth_headers()` e há um aviso no log. _(RF-CAD-009)_
- CT-CAD-016 — `settings.CORS_ALLOW_HEADERS` contém `idempotency-key`, `x-request-id` e `x-finalidade`; `settings.CORS_EXPOSE_HEADERS` contém `X-Request-Id`, `Idempotent-Replayed` e `Retry-After`. _(RF-CAD-010)_
- CT-CAD-017 — FedHub 401 e 403 → 502 `credencial_fedhub` com log; 404, 409 e 422 continuam repassados. _(RF-CAD-011)_
- CT-CAD-018 — `POST users/` anônimo → 401; `usuario` → 403; `admin` → 201 (`perform_create` mockado); `PATCH users/{próprio}/` com `nivel_acesso: admin` por `usuario` → 403 com `campos`, nada gravado; mesmo valor atual → 200; `admin` muda o nível de outro → 200. _(RF-CAD-012)_
- CT-CAD-019 — login Google com domínio fora de `GOOGLE_LOGIN_DOMINIOS` → 403 e `get_or_create` não chamado; domínio aceito e usuário novo → criado com `nivel_acesso = usuario` (verificação do token mockada). _(RF-CAD-012)_
- CT-CAD-020 — negação e escrita geram uma linha de log com `request_id`, e-mail, método, rota sem query e capacidade (`assertLogs`); `GET` autorizado sem exportação não gera linha `info`; nenhuma linha contém o valor de `busca`. _(RF-CAD-013)_
- CT-CAD-021 — em todos os caminhos de 403 do proxy, `requests.request` não é chamado; header `X-Capacidades` e campo `capacidades` no corpo não mudam a decisão. _(RNF-CAD-004)_
- CT-CAD-022 — o corpo do 403 tem exatamente `erro`, `mensagem` e, em `sem_acesso`, `capacidade`; CT-CAD-001..006 de `specs/cadastro-etl/` continuam verdes no modo sombra. _(RNF-CAD-005)_
- CT-CAD-023 — duas chamadas de `capacidades_de` para o mesmo nível dão acerto de cache (`cache_info().hits`); toda regra do mapa é `re.Pattern` no import. _(RNF-CAD-006)_

## Divergência vs. produção

- **ADR-0008 decisão 5** diz `NIVEIS_TELA` "hoje `("admin",)`"; o código tem quatro níveis (`fedhub/views/cadastro_view.py:20`). Esta spec propõe substituir a decisão (ADR-0011, proposto). `[P]` PA-038
- **ADR-0008 consequência 1** ("rota nova no FedHub fica disponível ao frontend sem deploy do Django — e sem revisão aqui") é revertida por RF-CAD-008. `[P]` PA-038
- **ADR-0008 decisões 1 e 6** listam `GET/POST/PUT/PATCH`; o DELETE repassado desde 29/09 (`fedhub/services/cadastro_service.py:29`, RF-CAD-002) não foi emendado no ADR. `[P]` PA-036
- **Dois arquivos ADR-0008** em `specs/adr/` (`0008-composicao-do-voucher-registrada-no-django.md` e `0008-proxy-transparente-para-api-etl.md`). Registrado, não resolvido aqui. `[P]` PA-036
- **STATUS.md** cita "PA-014 aberta" na linha de `cadastro-etl`; a questão foi renumerada para PA-027 em 24/09. A tabela também tem a linha de `auth-refresh-token` duplicada e uma quebra antes de `cadastro-etl`. Não corrigido aqui. `[P]` PA-037
- **Front × Django** divergem desde `e6d97e6` (§Contexto); a correção é do Front (fase 1). `[P]` PA-027
- **`CORS_ALLOW_HEADERS`** não libera os headers que o ADR-0008 promete repassar (§Contexto); RF-CAD-010 corrige.
- **Apólice × divisão (decisão do dono de 08/10, PA-040):** a versão de 07/10 desta spec tinha a aba `contrato:apolices` ao lado de `contrato:divisoes` e mapeava `GET contratos/{id}/apolices`, `GET contratos/{id}/divisoes/{id}`, `PATCH contratos/{id}/divisoes/{id}` e `POST contratos/{id}/divisoes`, rotas que não existem no FedHub nem no par `FedHub-Backend/specs/etl-object-pages/` (lido em 08/10: só `GET contratos/{id}/divisoes` e `POST contratos/{id}/divisoes/fundir`). Removidas; `divisoes` fica com `ver`, `exportar` e `fundir`. `[D]` PA-040
- **Rotas de pessoas ainda fora do par do FedHub:** `GET administradoras/{id}/pessoas` e `GET contratos/{id}/pessoas` foram decididas pelo dono em 08/10, mas `FedHub-Backend/specs/etl-object-pages/` ainda não as descreve (lido em 08/10); estão mapeadas antes de existir, como as demais "nova". `[D]` PA-040
- **Login Google**: `get_or_create` com `username` em `defaults` num modelo que declara `username = None` pode dar erro na criação; não verificado com requisição real. RF-CAD-012 reescreve o trecho. `[P]` PA-039

## Questões em Aberto

- PA-027 — `ti` entra? Proposta da matriz: lê e não grava.
- PA-029 — `comercial` vê dado pessoal (funcionários) e exporta faturas, PDD e comissões?
- PA-030 — `faturamento` puro ganha leitura do cadastro?
- PA-031 — `faturamento-analista` vê comissões e exporta PDD? Continua criando e editando?
- PA-032 — CSV de boletos da competência abre para `financeiro`?
- PA-033 — exceções por pessoa (`capacidades_extra`) agora ou só matriz por papel?
- PA-034 — `criado_por/alterado_por` no FedHub: texto truncado `cliente|e-mail` ou coluna `operador`?
- PA-035 — `PATCH users/{id}/` de não-admin com `nivel_acesso`: ignorar ou 403? Algum fluxo público depende de `POST users/` anônimo?
- PA-036 — colisão dos dois ADR-0008 e DELETE não emendado no ADR do proxy.
- PA-037 — STATUS.md cita PA-014 em vez de PA-027 (e linha duplicada).
- PA-038 — aprovação do modelo (ADR-0011): catálogo, matriz inicial, mapa, sombra e corte da fase 4. Quem aprova é o Hamilton, diretamente (PA-040); ele ainda não leu esta spec, por isso o status segue `rascunho`.
- PA-039 — domínios aceitos no login Google e se ele pode criar usuário.
- PA-040 — **fechada (2026-10-08):** apólice = divisão (sem sequência), sem aba "Apólices"; rotas de pessoas da administradora e do contrato (PII); `quantitativos` no detalhe da administradora; divisões só em `GET contratos/{id}/divisoes` e `POST contratos/{id}/divisoes/fundir`; o Hamilton aprova as specs diretamente.
