import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from datetime import datetime

from django.utils.dateparse import parse_date
from asgiref.sync import async_to_sync

from fedhub.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


# ============================================
# VIEWS PARA ANALYTICS 
# ============================================

class AnalyticsFaturamentoPeriodoView(APIView):
    """
    1. Faturamento por período (agregado por mês)
    GET /analytics/faturamento/?data_ini=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono, não mais async
        try:
            data_ini_str = request.query_params.get('data_ini')
            data_fim_str = request.query_params.get('data_fim')
            
            if not data_ini_str or not data_fim_str:
                return Response(
                    {"sucesso": False, "erro": "Parâmetros data_ini e data_fim são obrigatórios"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data_ini = parse_date(data_ini_str)
            data_fim = parse_date(data_fim_str)
            
            if not data_ini or not data_fim:
                return Response(
                    {"sucesso": False, "erro": "Datas inválidas. Use formato YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = AnalyticsService()
            # Converte a chamada assíncrona para síncrona
            resultado = async_to_sync(service.get_faturamento_periodo)(data_ini, data_fim)
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsFaturamentoPeriodoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AnalyticsTopAdministradorasView(APIView):
    """
    2. Top administradoras que mais faturam
    GET /analytics/administradoras/top/?limit=10
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            limit = request.query_params.get('limit', 10)
            
            try:
                limit = int(limit)
                limit = max(1, min(100, limit))
            except ValueError:
                limit = 10
            
            service = AnalyticsService()
            resultado = async_to_sync(service.get_top_administradoras)(limit)
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsTopAdministradorasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AnalyticsInadimplenciaView(APIView):
    """
    3. Métricas de inadimplência
    GET /analytics/inadimplencia/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            service = AnalyticsService()
            resultado = async_to_sync(service.get_inadimplencia)()
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsInadimplenciaView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AnalyticsFaturamentoPorAdministradoraView(APIView):
    """
    4. Faturamento detalhado por administradora no período
    GET /analytics/administradoras/faturamento/?data_ini=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            data_ini_str = request.query_params.get('data_ini')
            data_fim_str = request.query_params.get('data_fim')
            
            if not data_ini_str or not data_fim_str:
                return Response(
                    {"sucesso": False, "erro": "Parâmetros data_ini e data_fim são obrigatórios"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data_ini = parse_date(data_ini_str)
            data_fim = parse_date(data_fim_str)
            
            if not data_ini or not data_fim:
                return Response(
                    {"sucesso": False, "erro": "Datas inválidas. Use formato YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = AnalyticsService()
            resultado = async_to_sync(service.get_faturamento_por_administradora)(data_ini, data_fim)
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsFaturamentoPorAdministradoraView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AnalyticsStatusFaturasView(APIView):
    """
    5. Distribuição de faturas por status
    GET /analytics/faturas/status/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            service = AnalyticsService()
            resultado = async_to_sync(service.get_status_faturas)()
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsStatusFaturasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AnalyticsDashboardCompletoView(APIView):
    """
    6. Dashboard completo (junção de todas as métricas)
    GET /analytics/dashboard/?data_ini=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            data_ini_str = request.query_params.get('data_ini')
            data_fim_str = request.query_params.get('data_fim')
            
            if not data_ini_str or not data_fim_str:
                return Response(
                    {"sucesso": False, "erro": "Parâmetros data_ini e data_fim são obrigatórios"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data_ini = parse_date(data_ini_str)
            data_fim = parse_date(data_fim_str)
            
            if not data_ini or not data_fim:
                return Response(
                    {"sucesso": False, "erro": "Datas inválidas. Use formato YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = AnalyticsService()
            resultado = async_to_sync(service.get_dashboard_completo)(data_ini, data_fim)
            
            if resultado:
                # Adiciona metadata adicional do Django
                resultado["backend"] = "django-gateway"
                resultado["timestamp"] = resultado.get("timestamp", datetime.now().isoformat())
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsDashboardCompletoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )