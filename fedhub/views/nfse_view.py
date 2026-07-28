import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.nfse_service import NFSeService

logger = logging.getLogger(__name__)

class BuscarNFSEPorBoleto(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, documento, *args, **kwargs):
        try:
            service = NFSeService()

            nfse_data = service.buscar_nfse_por_boleto(documento)
            
            logger.info(f"NFSE encontrada: {nfse_data}")

            if not nfse_data:
                return Response(
                    {"status": "error", "message": "NFSE não encontrada."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "status": "success",
                    "data": nfse_data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Erro ao buscar nota: {str(e)}")
            return Response(
                {"status": "error", "message": "Erro interno ao buscar nota."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )  