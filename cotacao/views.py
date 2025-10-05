import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Importe o seu modelo
from .models import CotacaoIncendio


# A função csrf_exempt é usada para simplificar,
# mas para produção, use o CSRF token do Django para segurança.
@csrf_exempt
def calcular_cotacao_incendio(request):
    if request.method == "POST":
        try:
            # Recebe os dados JSON da requisição
            data = json.loads(request.body)
            print(f"{request.body}")

            # O problema mais comum é se a chave não existe no dicionário.
            # Use .get(key, 0) para garantir que sempre retorne um valor padrão.
            incendio_conteudo = float(data.get("incendio_conteudo", 0))
            perda_aluguel = float(data.get("perda_aluguel", 0))
            repasse_percentual = float(data.get("repasse_percentual", 0))
            premio_proposto = float(data.get("premio_proposto", 0))

            is_total = incendio_conteudo + perda_aluguel
            premio_liquido = premio_proposto / 1.0738
            repasse = repasse_percentual / 100
            comissao_administradora = premio_liquido * repasse
            assistencia_basica = 0.2
            taxa_seguradora = 0.00585 / 100

            if is_total * taxa_seguradora < 0.80:
                premio_liquido_seguradora = 0.80
            else:
                premio_liquido_seguradora = is_total * taxa_seguradora

            premio_bruto_seguradora = premio_liquido_seguradora * 1.0738
            repasse_seguradora_bruto = premio_liquido_seguradora * 57 / 100
            imposto = 20 / 100
            repasse_liquido = repasse_seguradora_bruto * (1 - imposto)
            entradas = premio_proposto + repasse_liquido
            saidas = (
                comissao_administradora + assistencia_basica + premio_bruto_seguradora
            )

            resultado = entradas - saidas
            percetual = resultado / premio_proposto

            repasse_administradora = premio_proposto * repasse
            # --- Fim da Lógica de Cálculo ---

            cotacao = CotacaoIncendio.objects.create(
                incendio_conteudo=incendio_conteudo,
                perda_aluguel=perda_aluguel,
                repasse_percentual=repasse_percentual,
                premio_proposto=premio_proposto,
                is_total=is_total,
                premio_liquido=premio_liquido,
                repasse=repasse,
                comissao_administradora=comissao_administradora,
                assistencia_basica=assistencia_basica,
                taxa_seguradora=taxa_seguradora,
                premio_liquido_seguradora=premio_liquido_seguradora,
                premio_bruto_seguradora=premio_bruto_seguradora,
                repasse_seguradora_bruto=repasse_seguradora_bruto,
                imposto=imposto,
                repasse_liquido=repasse_liquido,
                entradas=entradas,
                saidas=saidas,
                resultado=resultado,
                percentual=percetual,
            )

            results = {
                # Dados de entrada
                "incendio_conteudo": cotacao.incendio_conteudo,
                "perda_aluguel": cotacao.perda_aluguel,
                "repasse_percentual": cotacao.repasse_percentual,
                "premio_proposto": cotacao.premio_proposto,
                "is_total": cotacao.is_total,
                "premio_liquido": cotacao.premio_liquido,
                "repasse": cotacao.repasse,
                "comissao_administradora": cotacao.comissao_administradora,
                "assistencia_basica": cotacao.assistencia_basica,
                "taxa_seguradora": cotacao.taxa_seguradora,
                "premio_liquido_seguradora": cotacao.premio_liquido_seguradora,
                "premio_bruto_seguradora": cotacao.premio_bruto_seguradora,
                "repasse_seguradora_bruto": cotacao.repasse_seguradora_bruto,
                "imposto": cotacao.imposto,
                "repasse_liquido": cotacao.repasse_liquido,
                "entradas": cotacao.entradas,
                "saidas": cotacao.saidas,
                "resultado": cotacao.resultado,
                "percentual": cotacao.percentual,
                "data_cotacao": cotacao.data_cotacao.isoformat(),  # Formata a data para JSON
            }

            return JsonResponse(results, status=201)

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Em caso de erro, retorna uma resposta de erro
            # TypeError pode ocorrer se um valor não for um número
            return JsonResponse(
                {"error": f"Dados inválidos na requisição. Detalhe: {str(e)}"},
                status=400,
            )
    else:
        # Se a requisição não for POST, retorna um erro
        return JsonResponse({"error": "Método não permitido."}, status=405)
