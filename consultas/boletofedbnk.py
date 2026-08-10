import requests
from django.http import JsonResponse
from django.conf import settings


FASTAPI_BASE_URL = settings.WEBHOOK_URL  


def consultar_boletos_proxy(request):
    # 1. Pegar o parâmetro 'numero' que veio na requisição para o Django
    numero_fatura = request.GET.get('numero')

    if not numero_fatura:
        return JsonResponse({'erro': 'Parâmetro numero é obrigatório'}, status=400)

    try:
        response = requests.get(
            f"{FASTAPI_BASE_URL}/boletofedbnk/boletos/",
            params={'numero': numero_fatura},
            timeout=10 # Sempre bom ter um timeout para não travar o Django
        )

        if response.status_code == 200:
            return JsonResponse(response.json(), safe=False) 
        
        return JsonResponse(
            {'erro': 'Erro ao consultar serviço interno', 'detalhes': response.text},
            status=response.status_code
        )
    except requests.exceptions.RequestException as e:
        return JsonResponse({'erro': 'Serviço de boletos indisponível'}, status=503)
    
    
def consultar_boleto(request):
    # 1. Pegar o parâmetro 'numero' que veio na requisição para o Django
    numero_fatura = request.GET.get('numero')

    if not numero_fatura:
        return JsonResponse({'erro': 'Parâmetro numero é obrigatório'}, status=400)

    try:
        response = requests.get(
            f"{FASTAPI_BASE_URL}/boletofedbnk/boleto/",
            params={'numero': numero_fatura},
            timeout=10
        )

        if response.status_code == 200:
            return JsonResponse(response.json(), safe=False) 
        
        return JsonResponse(
            {'erro': 'Erro ao consultar serviço interno', 'detalhes': response.text},
            status=response.status_code
        )
    except requests.exceptions.RequestException as e:
        return JsonResponse({'erro': 'Serviço de boletos indisponível'}, status=503)
    
       
def cancelar_boleto(request):
    method = request.GET.get('method')
    numero_fatura = request.GET.get('numero')

    if not numero_fatura:
        return JsonResponse({'erro': 'Parâmetro numero é obrigatório'}, status=400)

    try:
        response = requests.post(
            f"https://fedhub-api-local.ngrok.app/api/fedpay/cancelamento",
            json={
                'fatura': int(numero_fatura),
                'documento': None,
            },
            timeout=10
        )

        if response.status_code == 200:
            return JsonResponse(response.json(), safe=False) 
        
        return JsonResponse(
            {'erro': 'Erro ao consultar serviço interno', 'detalhes': response.text},
            status=response.status_code
        )
    except requests.exceptions.RequestException as e:
        return JsonResponse({'erro': 'Serviço de boletos indisponível'}, status=503)