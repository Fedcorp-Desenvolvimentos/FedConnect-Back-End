import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

@csrf_exempt
def santander_webhook(request):
    # aceita GET (teste manual)
    if request.method == "GET":
        return JsonResponse({"status": "ok", "message": "webhook ativo"}, status=200)

    if request.method == "POST":
        try:
            body = request.body.decode("utf-8") if request.body else ""
        except Exception:
            body = ""

        data = {}

        # tenta parsear JSON (mas nunca quebra)
        if body:
            try:
                data = json.loads(body)
            except Exception:
                data = {}

        # loga (ou salva depois, sem travar resposta)
        logger.info(f"Webhook recebido: {data}")

        # 🔥 IMPORTANTE: responder 200 SEMPRE e RÁPIDO
        return JsonResponse({"received": True}, status=200)

    return JsonResponse({"error": "method not allowed"}, status=405)