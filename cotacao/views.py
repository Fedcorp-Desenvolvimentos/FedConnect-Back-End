import json
from django.http import JsonResponse
# O decorador drf_api_view substitui o csrf_exempt para APIs
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from consultas.models import HistoricoConsulta
from consultas.serializers import HistoricoConsultaSerializer
from .models import CotacaoIncendio
from django.db import IntegrityError # Importar para capturar erros de integridade (como o campo responsavel obrigatório)


# 1. Usamos os decoradores do DRF (api_view, authentication_classes, permission_classes)
# para garantir que o request.user seja um usuário válido ANTES da lógica ser executada.
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def calcular_cotacao_incendio(request):
    # A autenticação e permissão são aplicadas ANTES de chegar aqui.
    # Se o usuário não estiver logado, a função nem será executada e retornará 401.
    if request.method == "POST":
        try:
            # Recebe os dados JSON da requisição (DRF já trata o request.data se estiver usando JSON)
            # Como você usou json.loads(request.body) no código original, vamos manter a compatibilidade
            # Mas, se for uma requisição DRF, você deve usar `data = request.data`
            data = json.loads(request.body)

            # ... (Restante da lógica de cálculo é mantida) ...

            incendio_conteudo = float(data.get("incendio_conteudo", 0))
            perda_aluguel = float(data.get("perda_aluguel", 0))
            repasse_percentual = float(data.get("repasse_percentual", 0))
            premio_proposto = float(data.get("premio_proposto", 0))
            tipo_imovel = data.get("tipo_imovel", "").lower()
            assistencia = data.get("assistencia", "").lower()

            is_total = incendio_conteudo + perda_aluguel
            premio_liquido = premio_proposto / 1.0738
            repasse = repasse_percentual / 100
            comissao_administradora = premio_liquido * repasse
            assistencia_basica = 0.2
            taxa_seguradora = 0.00585 / 100 # Valor padrão para garantir que a variável existe
            
            if tipo_imovel == "comercial":
                taxa_seguradora = 0.00585 / 100
            elif tipo_imovel == "residencial":
                taxa_seguradora = 0.00250 / 100
            
            # Adicionar um 'else' caso tipo_imovel não seja 'comercial' nem 'residencial'
            # (opcional, mas recomendado)
            # else:
            #    raise ValueError("Tipo de imóvel inválido.")


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

            # repasse_administradora = premio_proposto * repasse # Variável não usada, pode remover.
            # --- Fim da Lógica de Cálculo ---

            # 2. Agora, request.user é um usuário válido ('Usuario' ou seu AUTH_USER_MODEL)
            cotacao = CotacaoIncendio.objects.create(
                # Adicionar o campo OBRIGATÓRIO (responsavel)
                # O default=1 em seu modelo garante que, se não for passado, ele tente usar o 1.
                # No entanto, aqui é mais seguro passar o usuário logado:
                responsavel=request.user, 
                
                incendio_conteudo=round(incendio_conteudo, 2),
                perda_aluguel=round(perda_aluguel, 2),
                repasse_percentual=round(repasse_percentual, 2),
                premio_proposto=round(premio_proposto, 2),
                is_total=round(is_total, 2),
                premio_liquido=round(premio_liquido, 2),
                repasse=round(repasse, 2) * 100,
                comissao_administradora=round(comissao_administradora, 2),
                assistencia_basica=round(assistencia_basica, 2) * 100,
                # A taxa seguradora deve ser arredondada antes de multiplicar por 100 se for um campo float:
                taxa_seguradora=round(taxa_seguradora, 6) * 100, 
                premio_liquido_seguradora=round(premio_liquido_seguradora, 2),
                premio_bruto_seguradora=round(premio_bruto_seguradora, 2),
                repasse_seguradora_bruto=round(repasse_seguradora_bruto, 2),
                imposto=round(imposto, 2) * 100,
                repasse_liquido=round(repasse_liquido, 2),
                entradas=round(entradas, 2),
                saidas=round(saidas, 2),
                resultado=round(resultado, 2),
                percentual=round(percetual, 2) * 100,
            )

            # 3. Preparação dos resultados (mantida a sua estrutura)
            results = {
                # ... (resultado) ...
                "incendio_conteudo": cotacao.incendio_conteudo,
                "perda_aluguel": cotacao.perda_aluguel,
                "repasse_percentual": cotacao.repasse_percentual,
                "premio_proposto": cotacao.premio_proposto,
                "is_total": cotacao.is_total,
                "premio_liquido": cotacao.premio_liquido,
                "repasse": f"{cotacao.repasse}%",
                "comissao_administradora": cotacao.comissao_administradora,
                "assistencia_basica": f"{cotacao.assistencia_basica}%",
                "taxa_seguradora": f"{cotacao.taxa_seguradora}%",
                "premio_liquido_seguradora": cotacao.premio_liquido_seguradora,
                "premio_bruto_seguradora": cotacao.premio_bruto_seguradora,
                "repasse_seguradora_bruto": cotacao.repasse_seguradora_bruto,
                "imposto": f"{cotacao.imposto}%",
                "repasse_liquido": cotacao.repasse_liquido,
                "entradas": cotacao.entradas,
                "saidas": cotacao.saidas,
                "resultado": cotacao.resultado,
                "percentual": f"{cotacao.percentual}%",
                "data_cotacao": cotacao.data_cotacao.isoformat(),
            }
            
            # 4. Salvamento do Histórico de Consulta
            # Note: Como o campo 'usuario' em HistoricoConsulta é OBRIGATÓRIO (NOT NULL),
            # e a view está protegida, request.user é seguro.
            historico = HistoricoConsulta.objects.create(
                usuario=request.user,
                tipo_consulta="estudo-incendio",
                parametro_consulta=request.body, # Salva o payload completo
                resultado=results,
                origem="manual",
                lote_id=None,
            )

            # 5. O serializador do histórico não precisa ser retornado na resposta da cotação
            # A linha abaixo é redundante se você só quer retornar 'results'.
            # historico_serializer = HistoricoConsultaSerializer(historico)

            return JsonResponse(results, status=200)

        # 6. Adicione exceção para erros de integridade (como faltar o responsavel se o IsAuthenticated falhar)
        except IntegrityError as e:
            return JsonResponse(
                {"error": f"Erro de integridade do banco de dados. Verifique se todos os campos obrigatórios foram fornecidos. Detalhe: {str(e)}"},
                status=400,
            )
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return JsonResponse(
                {"error": f"Dados inválidos na requisição. Detalhe: {str(e)}"},
                status=400,
            )
            
    else:
        # Se a requisição não for POST, retorna um erro (o decorador @api_view já faz isso, mas é bom manter)
        return JsonResponse({"error": "Método não permitido."}, status=405)