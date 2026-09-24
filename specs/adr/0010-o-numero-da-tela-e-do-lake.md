# ADR-0010 — O número da tela Produção CORP é do lake; o espelho deixa de ser origem

> **Status:** decidido · **Dono:** Ingryd Aylana (arquitetura de dados), a pedido da gestão · **Data:** 2026-09-23
> **Pode ser adiada:** não (enquanto houver dois motores, haverá dois números para a mesma pergunta)
> **Contexto(s):** `IEX` · **Specs:** `specs/indicadores-lake-como-origem/`, `specs/indicadores-meta-no-lake/`

## Contexto

A ADR-0009 (22/09/2026) decidiu um espelho da CORP no Postgres do FedConnect e agregações no Django, porque o FedConnect não alcançava o lake. Em 23/09/2026 o FedHub passou a expor o lake (`/api/lake/*`) e a razão do espelho acabou. Ficaram dois motores de regra para o mesmo número: a tela agregava o espelho por **data de emissão** e **prêmio total**; o painel de TV lia o lake por **início de vigência** e **prêmio líquido**, com a classificação de renovação da casa e sem os documentos que a CORP apagou. Com a meta gravada no lake (PA-025), a mesma meta Allianz × condomínio mostrou 38,5 % num lugar e 69,8 % no outro, na mesma noite.

## Decisão

O lake é o dono do número. A regra (corte, valor, classificação, exclusão de ausentes) vive no contrato do lake (`vw_documento_indicador`, `fn_ind_*`); o FedHub repassa; o FedConnect **monta** a resposta no contrato do front e não calcula nada. O espelho (`Producao`, `Documento`, `Cliente`, `CargaCorp`, cargas por snapshot e por lake) deixa de ser origem de qualquer leitura e fica no repositório como histórico até uma migração própria removê-lo (T-IEX-11.9).

## Consequências

- Um número por pergunta: resumo, por-seguradora, séries, não fechadas, composição e painel de TV batem entre si e com a grade da CORP por início de vigência (EVD-31 do lake).
- Os números da tela **mudam** em relação ao que o gestor via desde 22/09 (emissão × vigência; total × líquido). Precisa ser comunicado (T-IEX-11.8).
- A tela depende do FedHub e do lake estarem de pé: lake fora é 503 nomeado, não número velho.
- Latência de uma tela de gestão (1,6–2,1 s no resumo), com caminho de melhoria no lake (`fn_ind_resumo`).
- A suíte deste app prova o contrato com um FedHub em memória que calcula as mesmas funções sobre o banco de teste — a regra fica escrita duas vezes (SQL no lake, ORM no falso) e tem de bater.
