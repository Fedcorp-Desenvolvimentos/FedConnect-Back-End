import json
import requests  # Certifique-se de ter 'requests' instalado
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def webhook_receiver(request):
    # Aceita POST ou GET, conforme sua lógica original
    if request.method in ['POST', 'GET']:
        
        # 1. Tenta capturar o body da requisição original
        try:
            # Se for GET, o body costuma ser vazio, então tratamos o erro
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}

        # 2. Define a URL de destino (ngrok)
        target_url = "https://steeply-outlandish-reese.ngrok-free.dev/santander/webhook/"

        # 3. Faz a requisição para o destino enviando o mesmo body
        try:
            response = requests.post(
                target_url,
                json=data,  # Envia o dicionário como JSON automaticamente
                timeout=10  # Boa prática para não travar seu servidor
            )
            
            # Opcional: Log ou tratamento da resposta do destino
            target_status = response.status_code
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                "status": "erro",
                "mensagem": f"Falha ao encaminhar para o ngrok: {str(e)}"
            }, status=502)

        # 4. Retorna a confirmação
        return JsonResponse({
            "status": "sucesso",
            "mensagem": "Requisição recebida e encaminhada! 🚀",
            "ngrok_status": target_status,
            "recebido": data
        }, status=200)
    
    return JsonResponse({"erro": "Método não permitido"}, status=405)