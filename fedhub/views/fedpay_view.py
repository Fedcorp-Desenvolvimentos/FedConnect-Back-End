# fedhub/views/fedpay_view.py
#
# Tela de tratamento de boletos (reemissão com ajuste de dados).
#
# Hierarquia: a tela é acessível aos níveis NIVEIS_TELA; o nível enviado ao
# FedHub ("admin" | "comum") é derivado AQUI do request.user autenticado —
# nunca do corpo da requisição. O FedHub reforça a whitelist campo×nível
# do lado dele (defesa em profundidade).

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.fedpay_service import FedPayService

logger = logging.getLogger(__name__)

# Quem enxerga/usa a tela de tratamento
NIVEIS_TELA = ("admin", "faturamento", "ti")
# Quem opera como "admin" no FedHub (pode alterar nome cobrado, CNPJ/CPF cobrado e endereço)
NIVEIS_ADMIN_FEDHUB = ("admin", "ti")


def _nivel_fedhub(user) -> str:
    return "admin" if user.nivel_acesso in NIVEIS_ADMIN_FEDHUB else "comum"


def _sem_acesso():
    return Response(
        {"sucesso": False, "erro": "Seu nível de acesso não permite usar o tratamento de boletos."},
        status=status.HTTP_403_FORBIDDEN,
    )


class ConsultarFedPayView(APIView):
    """Estado dos boletos de uma fatura no banco emissor (somente leitura)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, fatura, *args, **kwargs):
        if request.user.nivel_acesso not in NIVEIS_TELA:
            return _sem_acesso()

        isfedcob = str(request.query_params.get("isfedcob", "")).lower() in ("true", "1")

        service = FedPayService()
        resultado = service.consultar_fatura(fatura, isfedcob=isfedcob)
        body = resultado["body"]

        if resultado["http_status"] == 200:
            return Response({"sucesso": True, "resultado": body}, status=status.HTTP_200_OK)
        return Response(
            {"sucesso": False, "erro": body.get("resumo") or body.get("message") or "Erro na consulta", "resultado": body},
            status=resultado["http_status"],
        )


class TratamentoFedPayView(APIView):
    """Reemite boletos selecionados com ajuste de dados (cancela, recria e emite).

    Payload esperado:
    {
        "fatura": 174625,
        "isfedcob": false,                       # opcional
        "boletos": [
            {"documento": "0001593331", "alteracoes": {"vencimento": "2026-09-10", "valor": 150.0}}
        ]
    }
    O operador (usuário/nível) NÃO vem no payload — é derivado do token.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.nivel_acesso not in NIVEIS_TELA:
            return _sem_acesso()

        try:
            data = request.data
            fatura = data.get("fatura")
            boletos = data.get("boletos")

            if not fatura:
                return Response({"sucesso": False, "erro": "Número da fatura é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)
            if not boletos or not isinstance(boletos, list):
                return Response({"sucesso": False, "erro": "Selecione ao menos um boleto"}, status=status.HTTP_400_BAD_REQUEST)

            nivel = _nivel_fedhub(request.user)
            payload = {
                "fatura": int(fatura),
                "operador": {"usuario": request.user.email, "nivel": nivel},
                "boletos": [
                    {"documento": str(b.get("documento") or ""), "alteracoes": b.get("alteracoes") or {}}
                    for b in boletos
                ],
            }

            logger.info(
                f"FedPay tratamento — fatura {fatura}, {len(boletos)} boleto(s), "
                f"operador {request.user.email} (nivel_acesso={request.user.nivel_acesso} → {nivel})"
            )

            service = FedPayService()
            resultado = service.tratar(payload, isfedcob=bool(data.get("isfedcob")))
            body = resultado["body"]

            if resultado["http_status"] == 200:
                return Response({"sucesso": True, "resultado": body}, status=status.HTTP_200_OK)

            # 400 do FedHub carrega o bloco amigável (resumo/pendencias) — o
            # front mostra as pendências mesmo no erro
            return Response(
                {"sucesso": False, "erro": body.get("resumo") or body.get("message") or "Erro no tratamento", "resultado": body},
                status=resultado["http_status"],
            )

        except Exception as e:
            logger.error(f"Erro no tratamento de boletos: {e}")
            return Response({"sucesso": False, "erro": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
