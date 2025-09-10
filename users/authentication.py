from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings

class JWTCookieAuthentication(BaseJWTAuthentication):
    """
    Classe de autenticação personalizada que lê o token JWT de um cookie HttpOnly.
    """
    def authenticate(self, request):
        # Tenta obter o token do cookie 'access_token'
        raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            return None # Nenhum token no cookie, a autenticação falha (ou tenta outro método)

        validated_token = self.get_validated_token(raw_token)

        return self.get_user(validated_token), validated_token