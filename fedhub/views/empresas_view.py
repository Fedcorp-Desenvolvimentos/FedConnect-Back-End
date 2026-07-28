# views/empresas_view.py

import asyncio
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from fedhub.services.empresas_service import EmpresasService
from datetime import datetime

logger = logging.getLogger(__name__)

class BuscarTodasEmpresas(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            nome = request.query_params.get("nome", "").strip()
            cnpj = request.query_params.get("cnpj", "").strip()
            codigo = request.query_params.get("codigo", "").strip()
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))

            service = EmpresasService()
            dados = asyncio.run(service.buscar_todas_empresas(params={
                "nome": nome,
                "cnpj": cnpj,
                "codigo": codigo,
                "page": page,
                "page_size": page_size
            }))

            if not dados:
                return Response({
                    "status": "not_found",
                    "message": "Empresa não encontrada",
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_404_NOT_FOUND)

            if nome:
                dados = [
                    e for e in dados
                    if nome.lower() in (e.get("nome") or e.get("NOME") or "").lower()
                ]
            if cnpj:
                cnpj_digits = "".join(filter(str.isdigit, cnpj))
                dados = [
                    e for e in dados
                    if cnpj_digits in "".join(filter(str.isdigit, e.get("cnpj") or e.get("CNPJ") or ""))
                ]
            if codigo:
                dados = [
                    e for e in dados
                    if codigo.lower() in str(e.get("codigo") or e.get("CODIGO") or e.get("id") or "").lower()
                ]

            total = len(dados)
            start = (page - 1) * page_size
            end = start + page_size
            paginated = dados[start:end]

            return Response({
                "status": "success",
                "total_returned": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
                "data": paginated,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Erro ao buscar empresas: {str(e)}")
            return Response({"detail": str(e)}, status=500)
                