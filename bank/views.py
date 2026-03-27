from datetime import datetime
import logging

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from bank.fedhub_service import FedhubService
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

class SantanderWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # GET apenas para verificar se o endpoint está ativo
        return Response({"status": "webhook active"}, status=200)    
       
    def post(self, request):
        # SEMPRE retornar 200 para o Santander
        try:
            data = request.data
            
            logger.info(f"📩 Webhook recebido - Payload: {data}")

            # Extrair dados básicos
            bank_number = data.get("bankNumber")
            payment_type = data.get("paymentType")
            
            if not bank_number:
                logger.warning("⚠️ Webhook sem bankNumber - ignorando")
                return Response(status=200)
                
            if not payment_type:
                logger.warning(f"⚠️ Webhook sem paymentType para bankNumber={bank_number}")
                return Response(status=200)

            # Inicializar serviço
            fedhub_service = FedhubService()
            
            # Buscar fatura pelo nosso número
            logger.info(f"🔍 Buscando fatura para nosso_numero={bank_number}")
            
            try:
                dados_fatura_lista = async_to_sync(
                    fedhub_service.buscar_fatura_por_nosso_numero
                )(bank_number)
            except Exception as e:
                logger.error(f"❌ Erro ao buscar fatura: {e}")
                return Response(status=200)
            
            # Validar retorno da busca
            if not dados_fatura_lista:
                logger.warning(f"⚠️ Nenhuma fatura encontrada para nosso_numero={bank_number}")
                return Response(status=200)
            
            # Pegar o primeiro item da lista
            if isinstance(dados_fatura_lista, list) and len(dados_fatura_lista) > 0:
                fatura = dados_fatura_lista[0]
            elif isinstance(dados_fatura_lista, dict):
                fatura = dados_fatura_lista
            else:
                logger.error(f"❌ Formato inesperado de dados_fatura: {type(dados_fatura_lista)}")
                return Response(status=200)
            
            logger.info(f"📄 Fatura encontrada: DOCUMENTO={fatura.get('DOCUMENTO')}, FATURA={fatura.get('FATURA')}, STATUS={fatura.get('STATUS')}")
            
            # Validação de status - não processar se já estiver cancelado ou quitado
            status_atual = fatura.get("STATUS")
            quitado = fatura.get("QUITADO")
            
            if status_atual == "C" or quitado == "S":
                logger.info(f"ℹ️ Fatura já processada: bankNumber={bank_number}, STATUS={status_atual}, QUITADO={quitado}")
                return Response(status=200)
            
            # Identificador baseado no tipo de pagamento
            identificador = None
            if payment_type == "PIX":
                identificador = data.get("txId")
            else:  # BOLETO ou outros
                identificador = data.get("bankNumber") or fatura.get("txId")
            
            # Fallback para identificador da fatura
            if not identificador:
                identificador = fatura.get("IDENTIFICADOR")
                if identificador:
                    logger.info(f"ℹ️ Usando IDENTIFICADOR da fatura: {identificador}")
            
            if not identificador:
                logger.warning(f"⚠️ Sem identificador válido para bankNumber={bank_number}")
            
            # Valores do pagamento
            valor_pago = data.get("payedValue")
            valor_nominal = data.get("nominalValue")
            
            # Validar valores
            if valor_pago is None:
                logger.warning(f"⚠️ payedValue não informado para bankNumber={bank_number}")
                valor_pago = fatura.get("VALOR")
            
            if valor_nominal is None:
                valor_nominal = fatura.get("VALOR")
            
            # Dados do pagador
            pagador_nome = data.get("payerName")
            pagador_doc = data.get("payerDocumentNumber")
            
            # Datas
            data_pagamento_raw = data.get("paymentDate")
            data_credito_raw = data.get("creditDate")
            
            def parse_date(date_str):
                try:
                    return datetime.fromisoformat(date_str)
                except Exception:
                    return None
            
            data_pagamento = parse_date(data_pagamento_raw) if data_pagamento_raw else None
            data_credito = parse_date(data_credito_raw) if data_credito_raw else None
            
            # Usar data atual se não veio data de pagamento
            if not data_pagamento:
                data_pagamento = datetime.now()
                logger.info(f"ℹ️ Usando data atual para pagamento: {data_pagamento.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Dados de controle
            client_number = data.get("clientNumber")
            convenio = data.get("covenant")
            
            # Log estruturado do pagamento
            # logger.info(
            #     f"""
            #     PAGAMENTO RECEBIDO - FASE 1 (VALIDAÇÃO)
            #     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            #     Tipo: {payment_type}
            #     Nosso Número: {bank_number}
            #     Documento: {fatura.get('DOCUMENTO')}
            #     Fatura: {fatura.get('FATURA')}
            #     Identificador: {identificador or 'N/A'}
            #     Valor Pago: R$ {valor_pago}
            #     Valor Nominal: R$ {valor_nominal}
            #     Pagador: {pagador_nome or 'N/A'} ({pagador_doc or 'N/A'})
            #     Data Pagamento: {data_pagamento.strftime('%Y-%m-%d %H:%M:%S') if data_pagamento else 'N/A'}
            #     Data Crédito: {data_credito.strftime('%Y-%m-%d %H:%M:%S') if data_credito else 'N/A'}
            #     Cliente: {client_number or 'N/A'}
            #     Convênio: {convenio or 'N/A'}
            #     Status Atual: {status_atual}
            #     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            #     """
            # )
            
            # =============================================
            # PRIMEIRA FASE - VALIDAÇÃO E PREPARAÇÃO DE DADOS
            # =============================================
            # Preparar dados para futura atualização
            
            dados_pagamento = {
                "paymentType": payment_type,
                "payedValue": valor_pago,
                "nominalValue": valor_nominal,
                "paymentDate": data_pagamento.strftime("%Y-%m-%d %H:%M:%S") if data_pagamento else None,
                "creditDate": data_credito.strftime("%Y-%m-%d %H:%M:%S") if data_credito else None,
                "clientNumber": client_number,
                "covenant": convenio,
                "payerName": pagador_nome,
                "payerDocumentNumber": pagador_doc,
                "txId": identificador,
                "bankNumber": bank_number,
                "documento": fatura.get("DOCUMENTO"),
                "fatura": fatura.get("FATURA"),
            }
            
            # logger.info(f"✅ Dados preparados para futura atualização: {dados_pagamento}")
            
            # =============================================
            # SEGUNDA FASE - CHAMADA AO FEDHUB PARA ATUALIZAÇÃO
            # =============================================
            
            # Log antes de chamar o serviço
            logger.info(f"🔄 Chamando Fedhub para processar pagamento - DOCUMENTO={fatura.get('DOCUMENTO')}, FATURA={fatura.get('FATURA')}")
            try:
                response = async_to_sync(
                    fedhub_service.processar_pagamento_boleto
                )(
                    fatura.get("DOCUMENTO"),
                    fatura.get("FATURA"),
                    dados_pagamento
                )
                
                if response:
                    logger.info(f"✅ Pagamento processado com sucesso: {response} - Dados: {dados_pagamento}")
                else:
                    logger.error(f"❌ Falha no processamento do Fedhub")
            except Exception as e:
                logger.error(f"❌ Erro ao chamar Fedhub: {e}")
            
            # ✅ Sempre retornar 200 para o Santander
            return Response(status=200)
            
        except Exception as e:
            # Captura QUALQUER exceção não tratada e loga
            logger.exception(f"❌ Erro crítico no webhook: {str(e)}")
            # Mesmo com erro, retorna 200
            return Response(status=200)