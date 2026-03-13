from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt # Use isso para facilitar testes externos (Postman/Insomnia) sem CSRF token
def webhook_receiver(request):
    if request.method == 'POST' or 'GET':
        # Opcional: capturar os dados enviados
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        return JsonResponse({
            "status": "sucesso",
            "mensagem": "Requisição recebida com sucesso! 🚀",
            "recebido": data
        }, status=200)
    
    return JsonResponse({"erro": "Método não permitido"}, status=405)