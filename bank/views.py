import json
import requests  # Certifique-se de ter 'requests' instalado
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def webhook_receiver(request):
    if request.method in ['POST', 'GET']:
        # Se for GET, pegamos os parâmetros da URL. Se for POST, o JSON do body.
        if request.method == 'GET':
            data = request.GET.dict()
        else:
            try:
                data = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                data = {}

        target_url = "https://steeply-outlandish-reese.ngrok-free.dev/santander/webhook/"

        try:
            # Repassamos os dados. Se for GET no original, talvez você queira 
            # decidir se envia como POST para o ngrok ou mantém o método.
            response = requests.post(
                target_url,
                json=data,
                headers={'ngrok-skip-browser-warning': '1'},
                timeout=10
            )
            target_status = response.status_code
        except requests.exceptions.RequestException as e:
            return JsonResponse({"status": "erro", "detalhes": str(e)}, status=502)

        return JsonResponse({"status": "sucesso", "ngrok_status": target_status}, status=200)
    
    return JsonResponse({"erro": "Método não permitido"}, status=405)