import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.fatura_service import FaturaService
from consultas.utils.renderers import BinaryRenderer

import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

logger = logging.getLogger(__name__)

class BuscarFaturaPorNumero(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, numero_fatura: str, *args, **kwargs):
        service = FaturaService()
        dados = service.buscar_fatura_por_numero(numero_fatura)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Fatura não encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })

class ExportarFaturasDinamicasPaginadasExcel(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        service = FaturaService()
        
        logger.info(f"Exportação Excel dinâmica paginada - Parâmetros: {request.query_params}")

        # Coletar parâmetros (os mesmos da consulta)
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "seguradora": request.query_params.get("seguradora"),
            "status": request.query_params.get("status"),
            "ramo": request.query_params.get("ramo"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "valor_min": request.query_params.get("valor_min"),
            "valor_max": request.query_params.get("valor_max"),
            "por_pagina": request.query_params.get("por_pagina", 1000),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        
        # Adicionar limite maior para exportação
        filtros_limpos['pagina'] = 1
        filtros_limpos['por_pagina'] = 5000  # Limite maior para exportação

        try:
            # Buscar dados do microsserviço
            dados = service.buscar_faturas_dinamicamente_paginadas(filtros_limpos)
            
            if not dados or dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum dado encontrado para exportação"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            data_list = dados.get("data", [])
            
            if not data_list:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum registro encontrado com os filtros informados"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Criar DataFrame pandas
            df = pd.DataFrame(data_list)
            
            # Selecionar e renomear colunas importantes para FATURAS
            colunas_selecionadas = [
                'fatura', 'apolice', 'administradora', 'seguradora', 'ramo',
                'data_fat', 'vencimento', 'status', 'quitado',
                'premio_bruto', 'premio_liq', 'premio_liquido',
                'dt_ini_vig', 'dt_fim_vig', 'quant_parcelas',
                'corretor', 'cod_corretor', 'numero_endosso'
            ]
            
            # Manter apenas colunas que existem no DataFrame (em minúsculo)
            colunas_disponiveis = [col for col in colunas_selecionadas if col in df.columns]
            df = df[colunas_disponiveis]
            
            # Renomear colunas para nomes mais amigáveis
            mapeamento_colunas = {
                'fatura': 'Nº Fatura',
                'apolice': 'Apólice',
                'administradora': 'Administradora',
                'seguradora': 'Seguradora',
                'ramo': 'Ramo',
                'data_fat': 'Data Fatura',
                'vencimento': 'Vencimento',
                'status': 'Status',
                'quitado': 'Quitado',
                'premio_bruto': 'Prêmio Bruto (R$)',
                'premio_liq': 'Prêmio Líquido (R$)',
                'premio_liquido': 'Prêmio Líquido (R$)',
                'dt_ini_vig': 'Início Vigência',
                'dt_fim_vig': 'Fim Vigência',
                'quant_parcelas': 'Quantidade Parcelas',
                'corretor': 'Corretor',
                'cod_corretor': 'Código Corretor',
                'numero_endosso': 'Nº Endosso'
            }
            
            df.rename(columns=mapeamento_colunas, inplace=True)
            
            # Formatar valores monetários
            colunas_monetarias = ['Prêmio Bruto (R$)', 'Prêmio Líquido (R$)']
            
            for col in colunas_monetarias:
                if col in df.columns:
                    # Converter para numérico e formatar
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    df[col] = df[col].apply(
                        lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') 
                        if pd.notnull(x) else ''
                    )
            
            # Formatar datas
            colunas_datas = ['Data Fatura', 'Vencimento', 'Início Vigência', 'Fim Vigência']
            
            for col in colunas_datas:
                if col in df.columns:
                    # Converter para datetime
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].dt.strftime('%d/%m/%Y')
            
            # Ordenar por data da fatura (mais recente primeiro)
            if 'Data Fatura' in df.columns:
                df = df.sort_values('Data Fatura', ascending=False)
            
            # Criar arquivo Excel em memória
            output = BytesIO()
            
            # Criar Excel writer com openpyxl
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Escrever dados principais
                df.to_excel(writer, sheet_name='Faturas Dinâmicas', index=False)
                
                # Ajustar largura das colunas
                worksheet = writer.sheets['Faturas Dinâmicas']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Adicionar uma sheet com informações do relatório
                info_df = pd.DataFrame({
                    'Parâmetro': ['Data Exportação', 'Total Registros', 'Filtros Aplicados'],
                    'Valor': [
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                        len(data_list),
                        ', '.join([f'{k}: {v}' for k, v in filtros_limpos.items() if k not in ['pagina', 'por_pagina']]) or 'Nenhum'
                    ]
                })
                
                info_df.to_excel(writer, sheet_name='Informações', index=False)
                
                # Formatar sheet de informações
                info_worksheet = writer.sheets['Informações']
                for column in info_worksheet.columns:
                    column_letter = column[0].column_letter
                    info_worksheet.column_dimensions[column_letter].width = 30
            
            output.seek(0)
            
            # Criar nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'faturas_dinamicas_{timestamp}.xlsx'
            
            # Retornar arquivo Excel como resposta
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
            return response

        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro ao gerar arquivo Excel: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )   

class ExportarFaturasComBoletosExcel(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        service = FaturaService()
        
        logger.info(f"Exportação Excel - Parâmetros: {request.query_params}")

        # Coletar parâmetros (mesmos filtros da consulta normal)
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "limit": request.query_params.get("limit", 500),
            "offset": request.query_params.get("offset", 0),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}

        try:
            # Buscar dados do microsserviço
            dados = service.buscar_faturas_com_boletos(filtros_limpos)
            
            if not dados or dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum dado encontrado para exportação"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            data_list = dados.get("data", [])
            
            if not data_list:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum registro encontrado com os filtros informados"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Criar DataFrame pandas
            df = pd.DataFrame(data_list)
            
            # Selecionar e renomear colunas importantes
            colunas_selecionadas = [
                'FATURA', 'APOLICE', 'ADMINISTRADORA', 'SEGURADORA',
                'DATA_FAT', 'VENCIMENTO', 'STATUS', 'QUITADO',
                'NOME_COBRADO', 'CNPJ_COBRADO',
                'PREMIO_BRUTO', 'PREMIO_LIQ', 'VALOR',
                'DT_INI_VIG', 'DT_FIM_VIG',
                'NOSSO_NUMERO', 'DOCUMENTO', 'PARCELA', 'PARCELAS',
                'BOLETA_REC', 'BOLETA_QUITADA'
            ]
            
            # Manter apenas colunas que existem no DataFrame
            colunas_disponiveis = [col for col in colunas_selecionadas if col in df.columns]
            df = df[colunas_disponiveis]
            
            # Renomear colunas para nomes mais amigáveis
            mapeamento_colunas = {
                'FATURA': 'Nº Fatura',
                'APOLICE': 'Apólice',
                'ADMINISTRADORA': 'Administradora',
                'SEGURADORA': 'Seguradora',
                'DATA_FAT': 'Data Fatura',
                'VENCIMENTO': 'Vencimento',
                'STATUS': 'Status',
                'QUITADO': 'Quitado',
                'NOME_COBRADO': 'Tomador',
                'CNPJ_COBRADO': 'CNPJ',
                'PREMIO_BRUTO': 'Prêmio Bruto (R$)',
                'PREMIO_LIQ': 'Prêmio Líquido (R$)',
                'VALOR': 'Valor Boleto (R$)',
                'DT_INI_VIG': 'Início Vigência',
                'DT_FIM_VIG': 'Fim Vigência',
                'NOSSO_NUMERO': 'Nosso Número',
                'DOCUMENTO': 'Documento',
                'PARCELA': 'Parcela Atual',
                'PARCELAS': 'Total Parcelas',
                'BOLETA_REC': 'Boleta Recebida (R$)',
                'BOLETA_QUITADA': 'Boleta Quitada'
            }
            
            df.rename(columns=mapeamento_colunas, inplace=True)
            
            # Formatar valores monetários
            colunas_monetarias = ['Prêmio Bruto (R$)', 'Prêmio Líquido (R$)', 
                                  'Valor Boleto (R$)', 'Boleta Recebida (R$)']
            
            for col in colunas_monetarias:
                if col in df.columns:
                    # Converter para numérico e formatar
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    df[col] = df[col].apply(
                        lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') 
                        if pd.notnull(x) else ''
                    )
            
            # Formatar datas
            colunas_datas = ['Data Fatura', 'Vencimento', 'Início Vigência', 'Fim Vigência']
            
            for col in colunas_datas:
                if col in df.columns:
                    # Converter para datetime
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].dt.strftime('%d/%m/%Y')
            
            # Ordenar por data da fatura (mais recente primeiro)
            if 'Data Fatura' in df.columns:
                df = df.sort_values('Data Fatura', ascending=False)
            
            # Criar arquivo Excel em memória
            output = BytesIO()
            
            # Criar Excel writer com openpyxl
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Escrever dados principais
                df.to_excel(writer, sheet_name='Faturas', index=False)
                
                # Ajustar largura das colunas
                worksheet = writer.sheets['Faturas']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Adicionar uma sheet com informações do relatório
                info_df = pd.DataFrame({
                    'Parâmetro': ['Data Exportação', 'Total Registros', 'Filtros Aplicados'],
                    'Valor': [
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                        len(data_list),
                        ', '.join([f'{k}: {v}' for k, v in filtros_limpos.items()]) or 'Nenhum'
                    ]
                })
                
                info_df.to_excel(writer, sheet_name='Informações', index=False)
                
                # Formatar sheet de informações
                info_worksheet = writer.sheets['Informações']
                for column in info_worksheet.columns:
                    column_letter = column[0].column_letter
                    info_worksheet.column_dimensions[column_letter].width = 30
            
            output.seek(0)
            
            # Criar nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'faturas_com_boletos_{timestamp}.xlsx'
            
            # Retornar arquivo Excel como resposta
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
            return response

        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro ao gerar arquivo Excel: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )           

class ExportarFaturasComBoletosPDF(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        service = FaturaService()

        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "limit": 500,
        }

        filtros_limpos = {k: v for k, v in filtros.items() if v}

        dados = service.buscar_faturas_com_boletos(filtros_limpos)

        if not dados or dados.get("status") != "success":
            return Response({"erro": "Nenhum dado encontrado"}, status=404)

        data_list = dados.get("data", [])

        response = HttpResponse(content_type="application/pdf")
        filename = f"faturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Access-Control-Expose-Headers"] = "Content-Disposition"

        c = canvas.Canvas(response, pagesize=A4)
        width, height = A4

        y = height - 2 * cm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Relatório de Faturas com Boletos")
        y -= 1 * cm

        c.setFont("Helvetica", 8)
        c.drawString(2 * cm, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        y -= 1 * cm

        headers = ["Fatura", "Apólice", "Status", "Vencimento", "Valor"]
        col_x = [2, 5, 9, 12, 16]

        c.setFont("Helvetica-Bold", 8)
        for i, h in enumerate(headers):
            c.drawString(col_x[i] * cm, y, h)

        y -= 0.5 * cm
        c.setFont("Helvetica", 8)

        for row in data_list:
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm

            c.drawString(col_x[0] * cm, y, str(row.get("FATURA", "")))
            c.drawString(col_x[1] * cm, y, str(row.get("APOLICE", "")))
            c.drawString(col_x[2] * cm, y, str(row.get("STATUS", "")))
            c.drawString(col_x[3] * cm, y, str(row.get("VENCIMENTO", "")))
            c.drawRightString(col_x[4] * cm, y, str(row.get("VALOR", "")))

            y -= 0.4 * cm

        c.showPage()
        c.save()

        return response