import logging

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)

class SantanderWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=200)

    def post(self, request):
        data = request.data
        logger.info(f"Webhook recebido: {data}")
        print("Webhook recebido:", data)
        return Response(status=200)