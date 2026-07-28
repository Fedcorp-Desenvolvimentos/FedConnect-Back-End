import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from fedhub.services.corretores_service import CorretoresService
logger = logging.getLogger(__name__)

class BuscarCorretores(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, codigo, *args, **kwargs):
        try:
            service = CorretoresService()

            corretor = service.buscar_corretor_por_codigo(codigo)
            
            logger.info(f"Corretor encontrado: {corretor}")

            if not corretor:
                return Response(
                    {"status": "error", "message": "Corretor não encontrado."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "status": "success",
                    "data": corretor
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Erro ao buscar corretor: {str(e)}")
            return Response(
                {"status": "error", "message": "Erro interno ao buscar corretor."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )