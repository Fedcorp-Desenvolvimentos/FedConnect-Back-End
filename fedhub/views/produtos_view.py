import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.produto_service import ProdutoService

logger = logging.getLogger(__name__)

class BuscarProdutosView(APIView):
    """
    Busca todos os produtos distintos do Firebird
    GET /produtos/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = ProdutoService()
            dados = service.buscar_produtos()
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar produtos"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(dados, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro em BuscarProdutosView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            
class BuscarNFSEPorBoleto(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, documento, *args, **kwargs):
            try:
                service = ProdutoService()

                nota_id = service.buscar_nfse_por_boleto(documento)
                
                logger.info(f"NFSE encontrada: {nota_id}")

                if not nota_id:
                    return Response(
                        {"status": "error", "message": "NFSE não encontrada."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                return Response(
                    {
                        "status": "success",
                        "data": nota_id
                    },
                    status=status.HTTP_200_OK
                )

            except Exception as e:
                logger.error(f"Erro ao buscar nota: {str(e)}")
                return Response(
                    {"status": "error", "message": "Erro interno ao buscar nota."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )               