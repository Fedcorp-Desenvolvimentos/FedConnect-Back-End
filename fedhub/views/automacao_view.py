import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import HttpResponse
from rest_framework.parsers import MultiPartParser, FormParser

from fedhub.services.automacao_service import AutomacaoService

logger = logging.getLogger(__name__)
           
class AutomacaoSepararPDFView(APIView):
    """Separa um PDF em múltiplos arquivos (um por página)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        nome_base = request.data.get('nome_base', '')
        
        if not file:
            return Response(
                {"sucesso": False, "erro": "Nenhum arquivo enviado"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not file.name.lower().endswith('.pdf'):
            return Response(
                {"sucesso": False, "erro": "O arquivo deve ser um PDF"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = AutomacaoService()
            resultado = service.separar_pdf(file, nome_base)
            
            # Se o resultado for bytes (conteúdo do ZIP), retorna como download
            if isinstance(resultado, bytes):
                nome_base_clean = nome_base or file.name.replace('.pdf', '')
                response = HttpResponse(
                    resultado,
                    content_type='application/zip'
                )
                response['Content-Disposition'] = f'attachment; filename="{nome_base_clean}_separado.zip"'
                return response
            
            # Se for erro
            return Response(
                {"sucesso": False, "erro": resultado.get("message", "Erro ao processar")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                
        except Exception as e:
            logger.error(f"Erro ao separar PDF: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )           

class AutomacaoUploadPDFsBBZView(APIView):
    """Apenas upload - salva os PDFs na pasta de origem"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files')
        
        if not files:
            return Response(
                {"sucesso": False, "erro": "Nenhum arquivo enviado"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = AutomacaoService()
            resultado = service.upload_pdfs_bbz(files)
            
            if not resultado:
                return Response(
                    {"sucesso": False, "erro": "Sem resposta do FedHub"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            status_fedhub = resultado.get("status")

            if status_fedhub != "sucesso":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", f"Status inesperado: {status_fedhub}")
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            return Response({
                "sucesso": True,
                "mensagem": resultado.get("message"),
                "resultado": resultado.get("dados")
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Erro no upload: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AutomacaoProcessarPDFsBBZView(APIView):
    """Apenas processa - move PDFs da pasta origem para pastas corretas"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        fazer_backup = request.data.get('fazer_backup', True)
        
        try:
            service = AutomacaoService()
            resultado = service.processar_pdfs_bbz(fazer_backup)
            
            if not resultado or resultado.get("status") != "sucesso":
                return Response(
                    {"sucesso": False, "erro": resultado.get("message", "Falha no processamento")},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            return Response({
                "sucesso": True,
                "mensagem": "PDFs processados com sucesso",
                "resultado": resultado.get("dados")
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Erro no processamento: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )