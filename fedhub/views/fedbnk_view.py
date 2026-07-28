import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from consultas.services.fedbnk_sync_service import FedBnkSyncService
from consultas.services.fedhub_service import FedhubService

logger = logging.getLogger(__name__)

# *******************************************#
#********** Boleto FedBnk ********#
# *******************************************# 
class CancelarBoletoFedBnkView(APIView):
    """Cancela boleto(s) no sistema do FedBnk"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """
        Payload esperado:
        {
            "metodo": "INDIVIDUAL" ou "TODOS",
            "fatura": "167455",  # obrigatório
            "documento": "0001482774",  # opcional - para INDIVIDUAL
            "motivo": "motivo do cancelamento",
            "mail": "email@exemplo.com"
        }
        """
        try:
            data = request.data
            metodo = data.get("metodo")
            fatura = data.get("fatura")
            documento = data.get("documento")
            motivo = data.get("motivo", f"Cancelamento solicitado por {request.user.email}")
            mail = data.get("mail", request.user.email)
            
            if not fatura:
                return Response(
                    {"sucesso": False, "erro": "Número da fatura é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not metodo:
                return Response(
                    {"sucesso": False, "erro": "Metodo (INDIVIDUAL ou TODOS) é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Cancelamento {metodo} - Fatura: {fatura}, Documento: {documento}")
            
            # Payload para o FedHub (sempre com fatura, documento pode ser None)
            payload = {
                "fatura": fatura,
                "documento": documento if metodo == "INDIVIDUAL" else None,
                "motivo": motivo,
                "mail": mail
            }
            
            # Chamar o FedhubService
            service = FedhubService()
            resultado = service.cancelar_boleto_fedbnk(payload)
            
            if resultado and resultado.get("status") == "sucesso":
                return Response({
                    "sucesso": True,
                    "status": "success",
                    "message": resultado.get("message", "Cancelamento realizado com sucesso"),
                    "resultado": resultado.get("dados")
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "sucesso": False,
                    "status": "error",
                    "message": resultado.get("message", "Erro no cancelamento") if resultado else "Erro desconhecido"
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Erro no cancelamento: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SincronizarBoletosView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        numero_fatura = request.data.get("numero_fatura")

        if not numero_fatura:
            return Response(
                {"sucesso": False, "erro": "numero_fatura é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = FedBnkSyncService()
            resultado = service.sincronizar_boletos(str(numero_fatura))

            return Response({
                "sucesso": True,
                "total_pendentes": resultado.get("total_pendentes", 0),
                "atualizados": resultado.get("atualizados", []),
                "erros": resultado.get("erros", []),
                "total_atualizados": resultado.get("total_atualizados", 0),
                "total_erros": resultado.get("total_erros", 0),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erro na sincronização de boletos: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
