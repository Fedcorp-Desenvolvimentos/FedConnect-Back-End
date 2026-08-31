# Convenções de escrita das specs

Regras obrigatórias para qualquer pessoa (ou agente) que escreva ou altere um documento em `specs/`. Este repositório segue o padrão SDD do Grupo FedCorp (nota técnica "SDD e DDD — Novo padrão"); o texto canônico das convenções vive em `FedHub-Backend/specs/CONVENCOES.md` — este arquivo replica as regras com as particularidades deste backend Django. Divergência de REGRA entre os dois é bug de processo: alinhe com o canônico.

---

## 1. Legenda de origem — `[E]` `[D]` `[P]`

| Marca | Significado | Exige |
|---|---|---|
| `[E]` | **Evidência.** Está implementado e verificado no código, ou verificado contra sistema externo/documentação oficial. | `arquivo:linha`, ou nota de verificação com data |
| `[D]` | **Decisão.** Alguém decidiu, e a decisão está registrada. | Referência a um `ADR-####` deste repositório |
| `[P]` | **Pendente.** Hipótese de trabalho. | Referência a uma `PA-###` |

**Regra dura:** enunciado sem marca é tratado como `[P]` na revisão. Regra `[P]` é hipótese, não acordo — antes de implementar, veja se a questão já foi respondida.

## 2. Esquema de identificadores

Mesmos formatos do canônico: `RF-<CTX>-###`, `RNF-<CTX>-###`, `INV-<CTX>-###`, `CT-<CTX>-###`, `T-<CTX>-#.#`, `ADR-####` (numeração global **deste repositório**), `PA-###` (registro global **deste repositório**).

**Namespaces são por repositório.** Para citar artefato de outro repo, use o caminho: `FedHub-Backend/specs/voucher-recebemos-de-empresa/` (RF-VOU-001 de lá ≠ RF-VOU-001 daqui).

### 2.1 Contextos (`<CTX>`)

Fixos. Não crie novos sem alterar esta tabela.

| Sigla | Contexto |
|---|---|
| `VOU` | vouchers/recibos de comissão — apps `consultas`/`fedhub` (proxy para o FedHub) |
| `CST` | consultas PF/PJ/CEP e histórico — app `consultas` |
| `USR` | usuários, autenticação, permissões — app `users` |
| `INT` | integrações externas (BigDataCorp, BrasilAPI, FedBnk, Monday, e-mail) |
| `CIP` | cursos CIPA da Condomed (turmas, inscritos, espelho na agenda) — app `condomed` |

### 2.2 Regras de identificador

1. IDs nunca são reciclados (descartado fica no arquivo com status `descartado`).
2. IDs nunca mudam de contexto (migrou = ID novo + `substituído por ...`).
3. Sequenciais dentro do contexto, passo 1.
4. **Cada fato mora em um lugar só** — cite o ID, não repita a descrição.

## 3. Cabeçalho de rastreabilidade

Todo documento de feature abre com o bloco após o título (formato idêntico ao canônico):

```markdown
> **Rastreabilidade** — RF: RF-VOU-001..003 · ADR: ADR-#### · Questões: PA-###
> **Status:** rascunho · **Dono:** · **Atualizado:** AAAA-MM-DD
```

## 4. Status de documento

`esboço` → `rascunho` → `em revisão` → `aprovado` (único que vincula) → `descartado`. Vive no cabeçalho **e** em [STATUS.md](./STATUS.md) — divergindo, STATUS.md vence. Só se avança de fase (requirements → design → tasks) com `aprovado` explícito do dono.

## 5. Matriz de rastreabilidade

Cada feature tem `matriz.csv`: **requisito fora da matriz não existe**. Separador `;`, multivalor `|`, sem escape (não use `;` dentro de campo; itens dentro de um campo separados por travessão). Colunas:

```
requisito;origem;design;invariantes;tarefas;testes;questoes
```

## 6. Invariantes

Afirmação sempre verdadeira (não instrução), um por ID, com onde é garantido: **banco** (constraint/migração), **aplicação** (view/service/transação) ou **processo**. Critérios de aceitação continuam em EARS dentro dos RF.

## 7. Seção de divergência

Todo `design.md` tem **"Divergência vs. produção"**, obrigatória mesmo vazia. Particularidade deste repo: **views/services duplicados entre `consultas/` e `fedhub/`** — o design identifica qual é o ativo em `bigcorp/urls.py` e declara o destino da duplicata (sincronizar ou eliminar).

## 8. Dados pessoais e segredos

Proibido em `specs/`: CPF/CNPJ/nome/contato de pessoa real; credencial, token, chave, senha ou string de conexão. Exemplos com dados fictícios evidentes. Segredos só em variáveis de ambiente (este repo já teve SECRET_KEY em código — auditoria 2026-08; não repetir).

## 9. Diagramas e formato

Mermaid em bloco de código, nunca imagem. Markdown UTF-8 sem BOM, LF, um `#` por arquivo, links relativos, pastas `kebab-case`. CSV: separador `;`, multivalor `|`.

## 10. Contrato de dois lados

Mudança no contrato com o **frontend** (payload/resposta de endpoint) ou com o **FedHub** exige spec nos dois repositórios envolvidos, uma citando a outra pelo caminho.

## 11. A verificação roda a cada gravação

```
bash specs/verificar.sh
```

Sai com código 1 se houver violação. Gravou em `specs/`, rodou.
