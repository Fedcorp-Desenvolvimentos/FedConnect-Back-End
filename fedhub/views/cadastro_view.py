# fedhub/views/cadastro_view.py
#
# Rota curinga `cadastro/<rota>` → CadastroService → /api/etl/<rota> do FedHub
# (spec specs/cadastro-etl/, ADR-0008). JWT + IsAuthenticated + nível em
# NIVEIS_TELA (PA-014: só admin por ora). O operador vai no header X-Operador a
# partir do JWT — nunca do corpo. Nenhum header do cliente além de
# Idempotency-Key e X-Request-Id chega ao FedHub.

import re
import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.cadastro_service import METODOS, CadastroService

NIVEIS_TELA = ("admin",)  # PA-014
_ROTA_VALIDA = re.compile(r"^[A-Za-z0-9_\-./]+$")


def _erro(codigo: str, mensagem: str, http: int) -> Response:
    return Response({"erro": codigo, "mensagem": mensagem}, status=http)


class CadastroProxyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "options"]

    @property
    def service(self) -> CadastroService:
        return CadastroService()

    def _repassar(self, request, rota: str) -> Response:
        if getattr(request.user, "nivel_acesso", None) not in NIVEIS_TELA:
            return _erro("sem_acesso", "Seu nível de acesso não permite usar o cadastro.", status.HTTP_403_FORBIDDEN)
        rota = (rota or "").strip("/")
        if not rota or ".." in rota or "//" in rota or not _ROTA_VALIDA.match(rota):
            return _erro("rota_invalida", "Rota inválida.", status.HTTP_400_BAD_REQUEST)
        metodo = request.method.upper()
        if metodo not in METODOS:
            return _erro("metodo_nao_permitido", f"Método {metodo} não permitido.", status.HTTP_405_METHOD_NOT_ALLOWED)
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        resultado = self.service.repassar(
            metodo, rota,
            params=request.query_params if metodo == "GET" else None,
            corpo=request.body if metodo != "GET" else None,
            operador=getattr(request.user, "email", "") or "",
            request_id=request_id,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        resposta = Response(resultado["body"], status=resultado["http_status"])
        resposta["X-Request-Id"] = request_id
        for chave, valor in (resultado.get("headers") or {}).items():
            resposta[chave] = valor
        return resposta

    def get(self, request, rota, *args, **kwargs):
        return self._repassar(request, rota)

    def post(self, request, rota, *args, **kwargs):
        return self._repassar(request, rota)

    def put(self, request, rota, *args, **kwargs):
        return self._repassar(request, rota)

    def patch(self, request, rota, *args, **kwargs):
        return self._repassar(request, rota)
