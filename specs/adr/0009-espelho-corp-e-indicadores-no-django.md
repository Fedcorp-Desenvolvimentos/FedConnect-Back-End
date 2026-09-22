# ADR-0009 — Espelho da CORP no Postgres, renovação classificada na carga, indicadores agregados no Django

> **Status:** decidido · **Dono:** Hamilton (gestor comercial), via Lucas Guidi · **Data:** 2026-09-22
> **Pode ser adiada:** não (define onde o dado vive e quem calcula; reverter é migração e reescrita dos endpoints)
> **Contexto(s):** `FCB` · **Specs:** `specs/indicadores-executivos/`

## Contexto

O gestor comercial quer um painel de indicadores da produção de seguros dentro do FedConnect, o primeiro de uma área de indicadores. A origem é a API CORP, o sistema de gestão da corretora, que hoje só é acessada por uma extração pontual (o snapshot entregue) e por uma POC de lake que lê o detalhe dos documentos. O acesso do FedConnect ao lake ainda não existe; virá depois.

O repositório resolve todo dado externo por proxy ao FedHub: nenhuma view agrega nada, e não há tabela espelhando sistema de terceiro. O protótipo entregue faz tudo no navegador, com a base inteira embutida no HTML, e calcula a regra de renovação (CPF/CNPJ com apólice anterior) a cada render, percorrendo 25.760 documentos.

## Decisão

**O FedConnect guarda um espelho normalizado da CORP no seu Postgres, calcula a classificação de renovação uma vez, na carga, e agrega os indicadores no Django com o ORM.** A tela recebe números prontos, uma requisição por seção, e nunca a base.

**Espelho, não proxy.** A CORP não é o FedHub: o FedConnect não tem acesso vivo a ela, o lake é quem terá. Guardar a cópia dá três coisas que o proxy não dá: funcionar sem a origem no ar, ter índice para agregar por período e seguradora, e auditar cada carga (quantos entraram, quantos foram rejeitados, de quando é a extração). O carregador é a única peça que sabe de onde o dado veio; o modelo tem só `origem` para distinguir snapshot de lake.

**Renovação é coluna, não cálculo de leitura.** A regra do gestor ("CPF/CNPJ que já teve qualquer apólice anterior é renovação, mesmo sem a cadeia da CORP") depende de olhar toda a carteira do cliente. Fazer isso a cada requisição é uma auto-junção por cliente em cada endpoint; fazer na carga é um passe com um dicionário por CPF e um `bulk_update`. A coluna também torna a regra auditável linha a linha: dá para abrir uma apólice e ver por que ela é renovação.

**Agregação no banco.** `Count`, `Sum`, `Case/When`, `TruncDay/TruncMonth` com fuso `America/Sao_Paulo`. É a primeira vez no repositório, e por isso fica declarado na divergência do design. O caminho oposto, somar em Python, repetiria o protótipo no servidor e não escalaria quando o lake trouxer o histórico completo.

**Cobertura ao lado de cada soma.** Prêmio e comissão só existem para documentos enriquecidos; no snapshot, 1.575 de 25.760. Toda soma monetária sai com a contagem de documentos que a compõem, e sai `null` quando não há nenhum. Somar zero no lugar do ausente é exatamente o fallback silencioso que o `CLAUDE.md` proíbe.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Servir o HTML do protótipo atrás de login (link em `/metricas`) | baixo | Um dia de trabalho; mas a base inteira, com CPF e nomes, vai para o navegador de quem abrir, e o dado é o da última troca manual do arquivo |
| Proxy à API CORP a cada requisição, como se faz com o FedHub | médio | O FedConnect não tem credencial nem acesso à CORP; a API filtra por vigência, não por emissão, e não devolve nada agregado — cada abertura da tela seria dezenas de páginas |
| Ler direto do lake quando ele existir, sem espelho local | alto | Acopla o painel a uma tecnologia ainda não definida (PA-021) e deixa a tela sem dado até lá; o espelho aceita o lake como segunda origem sem mudar endpoint |
| Espelho no Postgres + classificação na carga + agregação ORM (escolhida) | médio | Sete tabelas novas e um comando; tudo dentro do padrão do repo (app, migração, `APITestCase`) |
| Classificar renovação na leitura (subquery por CPF) | baixo | Correto, porém repetido em seis endpoints e caro; sem coluna, a regra não é auditável por apólice |

## Consequências

O app `indicadores` nasce com modelos próprios e sem dependência do FedHub. A fase 2 escreve um segundo carregador (lake → mesmas tabelas) e nada mais muda: endpoints, tela e testes continuam valendo. Se o volume crescer para milhões de linhas, a classificação de renovação migra de Python para uma window function em SQL dentro do mesmo serviço, sem mudar o contrato.

Passa a existir dado de terceiro com CPF e nome no banco do FedConnect. O snapshot não é versionado, os testes usam dado sintético e o CPF sai mascarado de toda resposta (INV-IEX-006). O acesso é para qualquer autenticado por decisão do dono; se mudar, é uma classe em `users/permissions.py` e uma linha por view.

Fica um caminho não coberto de propósito: escrever na CORP ou corrigir dado dela. O espelho é somente leitura; divergência entre espelho e origem se resolve recarregando, nunca editando a cópia.
