# ADR-0011 — Autorização do cadastro por objeto × aba × ação, com fonte única no Django

> **Status:** proposto (equivale a "a decidir" do template; aprovação em PA-038) · **Dono:** Hamilton (produto), com Daniel Mello (proxy) · **Data:** 2026-10-07
> **Pode ser adiada:** não — toda tela nova no padrão lista + página de objeto com abas herda a regra, e cada aba criada sem ela vira uma liberação a desfazer depois
> **Contexto(s):** `CAD` · **Specs:** `specs/cadastro-permissoes/` (nova), emenda a `specs/cadastro-etl/`; pares `FedConnect-FrontEnd/specs/cadastro-object-pages/` e `FedHub-Backend/specs/etl-object-pages/`
> **Substitui:** a decisão 5 e a consequência 1 do ADR-0008 do proxy (`0008-proxy-transparente-para-api-etl.md`), quando aprovado

## Contexto

O cadastro adota lista + página de objeto com abas, e o dono pediu em 07/10/2026 "um esquema de acesso que nos permita fazer a gestão por abas, bloqueando acessos indevidos". Hoje a autorização é binária e por prefixo: a tupla `NIVEIS_TELA` no proxy `cadastro/<path:rota>` (`fedhub/views/cadastro_view.py:20,38`) libera todo `/api/etl/*` para quatro níveis, e o Front tem três listas de níveis próprias (`FedConnect-FrontEnd/src/utils/routeAccess.js:42,45,47`), divergentes do Django desde o commit `e6d97e6`. Nenhuma camada distingue aba, ação (ver, exportar, criar, editar, vincular, excluir, fundir, converter) ou objeto. O FedHub conhece só o `client_id` do bearer (`FedHub-Backend/src/modules/etl/controller.py:55-62`) e exige `X-Operador` só em `/admin/*` (`:354-359`).

A única camada que vê ao mesmo tempo **quem** (JWT, `request.user.nivel_acesso`) e **o quê** (método + rota relativa a `/api/etl/`) é este Django. A rota identifica objeto e aba; o método identifica a ação; `X-Finalidade` ou `limite` identificam exportação.

## Decisão

Proposta (vincula só depois de aprovada em PA-038):

1. **Vocabulário fechado** de capacidades `cad:<objeto>:<aba>:<ação>`, catálogo em `users/capacidades.py`; nome fora do catálogo é erro de configuração, não concessão.
2. **Papel continua sendo `Usuario.nivel_acesso`.** Uma matriz versionada nível → padrões de capacidade (curingas expandidos no servidor) é a **única** fonte. Invariantes verificados no `manage.py check`: exportar exige ver da mesma aba (salvo aba só de exportação); qualquer escrita concede `cad:comum:referencias:ver`; qualquer `lista:ver` concede `cad:comum:totais:ver`; `admin` tem o catálogo inteiro; `admin_dados` só por linha explícita; nível sem linha não tem nada. Exceções por pessoa ficam para decisão futura (PA-033).
3. **O Front recebe `capacidades`** (lista plana, ordenada) em `GET users/me/` e as usa só para esconder abas, botões, rotas e colunas; quem decide é o Django.
4. **O proxy `cadastro/<rota>` aplica um mapa ordenado** (métodos, regex da rota relativa) → capacidade, com negação por padrão: rota não mapeada → 403 `rota_nao_mapeada`; capacidade ausente → 403 `sem_acesso` com o campo `capacidade`, sem chamar o FedHub. GET de lista com `X-Finalidade: exportar` ou `limite > 100` exige `:exportar`; `grupos-produto/boletos` exige sempre `:exportar`; `…/formulario` exige `:editar`. A ativação passa por modo sombra (`CADASTRO_PERMISSOES_ENFORCE=false` só registra "negaria"); `NIVEIS_TELA` sai na fase 4. 401/403 vindos do FedHub viram 502 `credencial_fedhub`.
5. **O FedHub não conhece capacidades.** Continua confiando no Django por escopo de cliente; o Django passa a usar um cliente próprio `fedconnect-cadastro` com escopo `/api/etl` só no `CadastroService`, e o FedHub passa a exigir `X-Operador` em toda escrita (decisão do par `FedHub-Backend/specs/etl-object-pages/`).
6. **Toda rota nova do FedHub sob `/api/etl` exige uma linha no mapa do Django**, garantida por teste de completude contra a lista de rotas das specs do FedHub. Reverte a consequência 1 do ADR-0008 do proxy.

## Opções consideradas

| Opção | Custo de reverter | Observações |
|---|---|---|
| Matriz versionada no Django + mapa rota → capacidade + `capacidades` em `users/me/` | baixo — arquivo + flag de modo sombra | **Proposta.** Fonte única, testável, sem tela nova, sem migração de usuários; cada aba nova custa uma linha no catálogo, uma no mapa e uma por papel |
| Tabela `Perfil`/`Capacidade` com tela de administração e cache | médio — migração dos 12 níveis para perfis, invalidação de cache | Fase futura se o dono quiser editar em tempo de execução; o arquivo vira carga inicial |
| Claims no JWT | baixo | Token de 30 min com cerca de 70 strings; mudar permissão exige novo login; o Django já carrega o usuário a cada requisição, não ganha nada |
| Capacidades no FedHub (ele checa por rota) | alto | O FedHub não conhece o usuário final; duplicaria a matriz em dois repositórios |
| Manter listas de níveis por rota no Front + `NIVEIS_TELA` | — | Estado atual: divergente, sem aba, sem ação, sem trilha |

## Consequências

- Uma aba nova = uma capacidade no catálogo + uma linha no mapa + uma decisão por papel na matriz; o Front só pergunta `usePode(cap)`.
- Exportação, escrita e negação ficam registradas no servidor (log com `request_id`, e-mail, rota e capacidade).
- Rota nova no FedHub deixa de "passar sozinha" pelo proxy: precisa de deploy do Django com a linha no mapa (substitui a consequência 1 do ADR-0008 do proxy).
- A decisão 5 do ADR-0008 do proxy (`NIVEIS_TELA`) fica substituída a partir da fase 4; até lá as duas convivem (sombra).
- Quem só tem `:ver` ainda pagina de 50 em 50: `:exportar` controla volume e trilha, não torna o dado invisível.
- Abas montadas sobre o payload de outra rota (parceiros e produtos do contrato, vínculos do condomínio) só podem ser escondidas pelo Front; o servidor cobra a capacidade da rota de origem.
- Mudar a matriz é deploy do Django enquanto não existir a tabela de perfis.
- Passa a ser obrigatório: teste de completude do mapa; `check` dos invariantes; correção do app `users` (criação só por admin, campos de papel protegidos) antes de ampliar acesso, senão a matriz é contornável.
