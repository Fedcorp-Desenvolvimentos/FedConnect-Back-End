# Specs — Spec-Driven Design do FedConnect-Back-End

Cada feature ou mudança relevante ganha uma pasta aqui, escrita segundo [CONVENCOES.md](./CONVENCOES.md) e verificada por [verificar.sh](./verificar.sh). O código vem depois e responde à spec. Padrão SDD do Grupo FedCorp — canônico em `FedHub-Backend/specs/`.

```
specs/
├── CONVENCOES.md              # regras de escrita, marcas [E]/[D]/[P], esquema de IDs
├── STATUS.md                  # painel de status (vence o cabeçalho em divergência)
├── 00-registro-de-questoes.md # PA-### — questões abertas, com dono e o que travam
├── adr/                       # ADR-#### — decisões arquiteturais (numeração deste repo)
├── verificar.sh               # verificação por script; roda a cada gravação
├── _templates/                # templates dos 3 documentos
└── nome-da-feature/
    ├── requirements.md        # 1º — o quê e por quê (RF/RNF com EARS e marcas)
    ├── design.md              # 2º — o como (arquitetura, invariantes, divergência)
    ├── tasks.md               # 3º — o plano (T-### rastreáveis a RF e CT)
    └── matriz.csv             # rastreabilidade: requisito → origem/design/tarefas/testes
```

## Fluxo

1. **Requirements** → escrever com marcas de origem, revisar, `Status: aprovado` (aqui e no STATUS.md). Só então:
2. **Design** → decisões não óbvias viram **ADR**; invariantes declarados; divergência vs. produção. Aprovar. Só então:
3. **Tasks + matriz** → tarefas pequenas rastreadas na `matriz.csv`; `[x]` só com testes passando.
4. **`bash specs/verificar.sh`** antes de considerar qualquer gravação concluída.

Mudou o entendimento? Spec primeiro, código depois. Divergência é informação: registre ou abra `PA-###` e continue com a hipótese declarada. Não decida sozinho, e não pare.

## Quando exige spec

- Endpoint novo ou contrato alterado com o frontend (payload, resposta, status)
- Mudança de modelo/migração no PostgreSQL
- Integração externa nova ou alterada (FedHub, BigDataCorp, FedBnk, Monday, e-mail)
- Autenticação, permissões, níveis de acesso
- Mudança que cruza apps; fluxo financeiro (mesmo quando só faz proxy — o contrato tem dois lados: spec também no FedHub)

## Quando NÃO exige spec

- Fix de bug pontual sem mudança de comportamento contratual
- Refactor interno pequeno, logging, typo, ajuste de teste

O método tem custo fixo alto — é para o que é caro errar, não para CRUD.

Nomes de pasta: `kebab-case`, ex.: `paginacao-consulta-pessoas`.
