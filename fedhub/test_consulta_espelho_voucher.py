"""Espelho do voucher: a consulta por número devolve exatamente o que entrou na emissão.

Caso real (PA-016, 2026-09-18): o voucher 20131244 saiu com 169 parcelas e a
consulta mostrava 186. As 17 a mais eram parcelas não pagas do mesmo lançamento
geral, que herdam o número carimbado no Firebird.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from fedhub.models import VoucherEmitido, VoucherEmitidoItem
from fedhub.services import espelho_voucher_service as espelho


def comissao_payload(fatura="176779", parcela="5", documento="0001631755", valor=28.99, **extra):
    """Formato que o frontend manda na emissão (minúsculas, favorecido sem zeros)."""
    base = {
        "fatura": fatura, "tipo_fat": "A", "favorecido": "5912", "tipo": "BENEFICIO",
        "parcela": parcela, "parcela_comissao": "1", "documento": documento,
        "valor_comissao": valor, "favorecido_nome": "ACPL ADMINISTRADORA DE IMOVEIS LTDA",
    }
    base.update(extra)
    return base


def linha_fedhub(fatura=176779, parcela=5, documento="0001631755", valor=28.99, **extra):
    """Formato que o FedHub devolve na consulta (MAIÚSCULAS, favorecido com zeros)."""
    base = {
        "FATURA": fatura, "TIPO_FAT": "A", "FAVOR": "0000005912", "TIPO": "BENEFICIO",
        "PARCELA": parcela, "PARCELA_2": 1, "DOCUMENTO": documento, "VALOR": valor,
        "VOUCHER": "20131244", "DT_BAIXA": "2026-09-10",
    }
    base.update(extra)
    return base


PAYLOAD = {
    "tipo_documento": "voucher",
    "empresa_pagadora_nome": "FEDCORP ASSISTENCIA E BENEFICIOS LTDA",
    "empresa_pagadora_cnpj": "13.037.030/0001-14",
    "comissoes": [
        comissao_payload(parcela="5", documento="0001631755", valor=28.99),
        comissao_payload(parcela="7", documento="0001631757", valor=9.66),
        comissao_payload(fatura="177448", parcela="2", documento="0001640125", valor=9.66),
    ],
    "resumo": {"valor_total_bruto": 48.31, "total_retencoes": 2.27, "valor_liquido_final": 46.04},
}


class RegistrarEmissaoTests(TestCase):
    def test_grava_documento_e_uma_parcela_por_comissao(self):
        v = espelho.registrar_emissao("20131244", "voucher", PAYLOAD)

        self.assertEqual(v.numero, "20131244")
        self.assertEqual(v.favorecido, "5912")
        self.assertEqual(v.empresa_pagadora_nome, "FEDCORP ASSISTENCIA E BENEFICIOS LTDA")
        self.assertEqual(v.total_bruto, Decimal("48.31"))
        self.assertEqual(v.total_liquido, Decimal("46.04"))
        self.assertEqual(v.itens.count(), 3)
        item = v.itens.get(documento="0001631755")
        self.assertEqual((item.fatura, item.favor, item.tipo, item.parcela, item.parcela_comissao), ("176779", "5912", "BENEFICIO", "5", "1"))
        self.assertEqual(item.valor, Decimal("28.99"))

    def test_reemissao_do_mesmo_numero_so_acrescenta_o_que_faltava(self):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)
        mais_uma = dict(PAYLOAD, comissoes=PAYLOAD["comissoes"] + [comissao_payload(parcela="8", documento="0001631758", valor=9.66)])

        espelho.registrar_emissao("20131244", "voucher", mais_uma, resultado={"reutilizado": True})

        self.assertEqual(VoucherEmitido.objects.count(), 1)
        self.assertEqual(VoucherEmitidoItem.objects.count(), 4)

    def test_sem_numero_nao_registra(self):
        with self.assertRaises(ValueError):
            espelho.registrar_emissao("", "voucher", PAYLOAD)


class AplicarEspelhoTests(TestCase):
    def setUp(self):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)

    def test_devolve_so_as_parcelas_que_estavam_no_documento(self):
        consulta = [
            linha_fedhub(parcela=5, documento="0001631755"),
            linha_fedhub(parcela=7, documento="0001631757", valor=9.66),
            linha_fedhub(parcela=13, documento="0001631763", valor=9.66, DT_BAIXA=None),  # não paga na emissão
            linha_fedhub(parcela=28, documento="0001631778", valor=57.97, DT_BAIXA="2026-09-20"),  # paga depois
            linha_fedhub(fatura=177448, parcela=2, documento="0001640125", valor=9.66),
        ]

        linhas, aplicado, voucher = espelho.aplicar_espelho("20131244", consulta)

        self.assertTrue(aplicado)
        self.assertEqual(voucher.numero, "20131244")
        self.assertEqual([l["DOCUMENTO"] for l in linhas], ["0001631755", "0001631757", "0001640125"])

    def test_favorecido_com_zeros_e_fatura_numerica_casam_com_o_registro(self):
        linhas, aplicado, _ = espelho.aplicar_espelho("20131244", [linha_fedhub(FATURA="0000176779", FAVOR="5912")])

        self.assertTrue(aplicado)
        self.assertEqual(len(linhas), 1)

    def test_voucher_sem_registro_passa_inteiro_e_avisa(self):
        consulta = [linha_fedhub(VOUCHER="20122872"), linha_fedhub(parcela=13, VOUCHER="20122872")]

        linhas, aplicado, voucher = espelho.aplicar_espelho("20122872", consulta)

        self.assertFalse(aplicado)
        self.assertIsNone(voucher)
        self.assertEqual(len(linhas), 2)


class MarcarCancelamentoTests(TestCase):
    def test_marca_a_data_e_mantem_o_registro(self):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)

        self.assertEqual(espelho.marcar_cancelamento(["20131244", "inexistente"]), 1)
        v = VoucherEmitido.objects.get(numero="20131244")
        self.assertIsNotNone(v.cancelado_em)
        self.assertEqual(v.itens.count(), 3)
        self.assertEqual(espelho.marcar_cancelamento(["20131244"]), 0)  # idempotente


class ViewsTests(APITestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email="financeiro@fedcorp.test", password="senha-de-teste",
            nome_completo="Financeiro", nivel_acesso="financeiro",
        )
        self.client.force_authenticate(user=self.usuario)

    @patch("fedhub.views.comissao_view.FedhubService")
    def test_emissao_registra_o_espelho(self, Service):
        Service.return_value.emitir_voucher_comissao.return_value = {
            "numero_documento": "20131244", "nome_arquivo": "voucher_20131244.pdf",
            "pdf_base64": "JVBERi0=", "registros_atualizados": 2,
        }

        resposta = self.client.post("/comissoes/emitir-voucher/", PAYLOAD, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        v = VoucherEmitido.objects.get(numero="20131244")
        self.assertEqual(v.itens.count(), 3)
        self.assertEqual(v.emitido_por, self.usuario)

    @patch("fedhub.views.comissao_view.FedhubService")
    def test_consulta_por_voucher_devolve_exatamente_o_documento(self, Service):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)
        Service.return_value.consultar_comissoes.return_value = {
            "status": "success", "total_registros": 5,
            "data": [
                linha_fedhub(parcela=5, documento="0001631755"),
                linha_fedhub(parcela=7, documento="0001631757", valor=9.66),
                linha_fedhub(parcela=13, documento="0001631763", valor=9.66, DT_BAIXA=None),
                linha_fedhub(parcela=28, documento="0001631778", valor=57.97),
                linha_fedhub(fatura=177448, parcela=2, documento="0001640125", valor=9.66),
            ],
        }

        resposta = self.client.get("/comissoes/consultar/", {"voucher": "20131244"})

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.data["espelho"])
        self.assertEqual(resposta.data["dados"]["total_registros"], 3)
        self.assertEqual(len(resposta.data["dados"]["data"]), 3)
        self.assertNotIn("aviso", resposta.data)

    @patch("fedhub.views.comissao_view.FedhubService")
    def test_consulta_de_voucher_antigo_passa_inteira_com_aviso(self, Service):
        Service.return_value.consultar_comissoes.return_value = {
            "status": "success", "total_registros": 2,
            "data": [linha_fedhub(VOUCHER="20122872"), linha_fedhub(parcela=13, VOUCHER="20122872")],
        }

        resposta = self.client.get("/comissoes/consultar/", {"voucher": "20122872"})

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertFalse(resposta.data["espelho"])
        self.assertIn("aviso", resposta.data)
        self.assertEqual(resposta.data["dados"]["total_registros"], 2)

    @patch("fedhub.views.comissao_view.FedhubService")
    def test_consulta_sem_filtro_de_voucher_nao_mexe_na_lista(self, Service):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)
        Service.return_value.consultar_comissoes.return_value = {
            "status": "success", "total_registros": 2,
            "data": [linha_fedhub(), linha_fedhub(parcela=13, documento="0001631763")],
        }

        resposta = self.client.get("/comissoes/consultar/", {"favorecido": "5912"})

        self.assertEqual(resposta.data["dados"]["total_registros"], 2)
        self.assertNotIn("espelho", resposta.data)

    @patch("fedhub.views.comissao_view.FedhubService")
    def test_cancelamento_marca_o_registro(self, Service):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)
        Service.return_value.cancelar_comissao.return_value = {"status": "success", "total_canceladas": 3}

        resposta = self.client.post(
            "/comissoes/cancelar/",
            {"comissoes": [{"voucher": "20131244", "favorecido": "5912", "fatura": "176779", "parcela": "5", "documento": "0001631755", "tipo": "BENEFICIO"}]},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertIsNotNone(VoucherEmitido.objects.get(numero="20131244").cancelado_em)
