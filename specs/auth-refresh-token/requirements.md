# Requisitos — Refresh Token na Autenticação (contrato com o FedConnect-FrontEnd)

> **Status:** Aprovado (2026-08-24)
> **Autor:** Daniel Mello (com Claude) | **Data:** 2026-08-24 | **Área(s):** `bigcorp/urls.py`, `bigcorp/settings.py`, `users/views.py`
> **Spec do front:** `FedConnect-FrontEnd/specs/auth-refresh-token/`

## Contexto e Problema

O front vai passar a renovar o access token automaticamente. O `/login/` e o `/google-login/` já retornam `{access, refresh}`; falta a rota de refresh (hoje comentada no `urls.py`) e o endurecimento padrão de mercado (access curto, rotação e blacklist de refresh).

## Escopo

**Dentro do escopo:**
- Habilitar `POST /login/refresh/` (`TokenRefreshView` do simplejwt).
- `SIMPLE_JWT`: `ACCESS_TOKEN_LIFETIME` 30 min; `REFRESH_TOKEN_LIFETIME` 7 dias (mantido); `ROTATE_REFRESH_TOKENS = True`; `BLACKLIST_AFTER_ROTATION = True`.
- `INSTALLED_APPS` += `rest_framework_simplejwt.token_blacklist` (**exige `python manage.py migrate` no deploy**).
- `LogoutView`: aceitar `{refresh}` opcional no corpo e colocá-lo na blacklist (falha na blacklist não impede a resposta 200).

**Fora do escopo:**
- Cookies HttpOnly; mudanças no fluxo de login/Google (já retornam o par).

## Critérios de Aceitação (EARS)

- **QUANDO** `POST /login/refresh/` receber `{refresh: <válido>}`, **ENTÃO** o backend **DEVE** responder 200 com `{access, refresh}` (refresh novo, por causa da rotação) e invalidar o refresh usado (blacklist).
- **SE** o refresh estiver expirado, inválido ou já usado (blacklisted), **ENTÃO** o backend **DEVE** responder 401 com `detail` legível.
- **QUANDO** `POST /logout/` receber `{refresh}`, **ENTÃO** o backend **DEVE** blacklistar o token e responder 200; **SE** o corpo vier sem `refresh` ou com token inválido, **ENTÃO** ainda responde 200 (logout local do front não pode travar).
- **QUANDO** um access token com mais de 30 min for usado, **ENTÃO** o backend **DEVE** responder 401 (comportamento padrão do simplejwt — critério de verificação dos lifetimes).

## Questões em Aberto

- [x] Todas resolvidas na aprovação de 2026-08-24 (lifetimes, rotação, URL).
