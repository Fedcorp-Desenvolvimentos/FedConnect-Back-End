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

        # 🔑 tipo de pagamento
        payment_type = data.get("paymentType")

        # 🔑 identificador principal
        if payment_type == "PIX":
            identificador = data.get("txId")
        else:
            identificador = data.get("bankNumber")

        # 💰 valores
        valor_pago = data.get("payedValue")
        valor_nominal = data.get("nominalValue")

        # 👤 pagador
        pagador_nome = data.get("payerName")
        pagador_doc = data.get("payerDocumentNumber")

        # 📅 datas
        data_pagamento = data.get("paymentDate")
        data_credito = data.get("creditDate")

        # 🧾 controle interno
        nosso_numero = data.get("clientNumber")
        convenio = data.get("covenant")

        logger.info(
            f"""
            🔔 PAGAMENTO RECEBIDO
            tipo={payment_type}
            valor_nominal={valor_nominal}
            valor_pago={valor_pago}
            data_pagamento={data_pagamento}
            data_credito={data_credito}
            convenio={convenio}
            id={identificador}
            nosso_numero={nosso_numero}
            valor={valor_pago}
            pagador={pagador_nome} ({pagador_doc})
            """
        )

        if not identificador and not nosso_numero:
            logger.warning("Webhook sem identificador válido")
            return Response(status=200)

        return Response(status=200)