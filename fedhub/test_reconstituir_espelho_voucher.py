"""Reconstituição da composição de vouchers emitidos antes do espelho (RF-VOU-005)."""
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from fedhub.models import VoucherEmitido
from fedhub.services import espelho_voucher_service as espelho
from fedhub.test_consulta_espelho_voucher import PAYLOAD, linha_fedhub


def rodar(*args, **kwargs):
    saida = StringIO()
    call_command("reconstituir_espelho_voucher", *args, stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


BAIXADAS = {
    "status": "success",
    "data": [
        linha_fedhub(parcela=5, documento="0001631755", valor=28.99),
        linha_fedhub(parcela=7, documento="0001631757", valor=9.66),
        linha_fedhub(fatura=177448, parcela=2, documento="0001640125", valor=9.66),
    ],
}


class ReconstituirTests(TestCase):
    def setUp(self):
        self.patcher = patch("fedhub.management.commands.reconstituir_espelho_voucher.FedhubService")
        self.Service = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.Service.return_value.consultar_comissoes.return_value = BAIXADAS

    def test_sem_numero_e_sem_favorecido_recusa(self):
        with self.assertRaises(CommandError):
            rodar()

    def test_simula_por_padrao_sem_gravar(self):
        saida = rodar("20131244")

        self.assertIn("SIMULAÇÃO", saida)
        self.assertIn("3 parcela(s)", saida)
        self.assertEqual(VoucherEmitido.objects.count(), 0)

    def test_confirmar_grava_marcando_reconstituido(self):
        rodar("20131244", "--confirmar")

        v = VoucherEmitido.objects.get(numero="20131244")
        self.assertTrue(v.reconstituido)
        self.assertEqual(v.itens.count(), 3)
        self.assertEqual(v.total_bruto, Decimal("48.31"))
        # Retenções não são recuperáveis: líquido == bruto, e o aviso da consulta diz isso.
        self.assertEqual(v.total_retencoes, Decimal("0.00"))
        self.assertEqual(v.total_liquido, Decimal("48.31"))
        # Só parcelas baixadas foram pedidas ao FedHub.
        self.Service.return_value.consultar_comissoes.assert_called_with(
            {"voucher": "20131244", "status": "baixadas"}
        )

    def test_nao_mexe_em_registro_gravado_na_emissao(self):
        espelho.registrar_emissao("20131244", "voucher", PAYLOAD)

        saida = rodar("20131244", "--confirmar")

        self.assertIn("gravado na emissão", saida)
        self.assertFalse(VoucherEmitido.objects.get(numero="20131244").reconstituido)

    def test_refazer_so_vale_para_reconstituido(self):
        rodar("20131244", "--confirmar")
        self.Service.return_value.consultar_comissoes.return_value = {
            "status": "success", "data": BAIXADAS["data"] + [linha_fedhub(parcela=9, documento="0001631759", valor=5.0)],
        }

        rodar("20131244", "--confirmar", "--refazer")

        self.assertEqual(VoucherEmitido.objects.get(numero="20131244").itens.count(), 4)

    def test_sem_parcela_baixada_nao_grava(self):
        self.Service.return_value.consultar_comissoes.return_value = {"status": "success", "data": []}

        saida = rodar("20131244", "--confirmar")

        self.assertIn("nenhuma parcela baixada", saida)
        self.assertEqual(VoucherEmitido.objects.count(), 0)

    def test_por_favorecido_descobre_os_numeros(self):
        def consultar(params):
            if "voucher" in params:
                return BAIXADAS
            return {"status": "success", "data": [
                linha_fedhub(VOUCHER="20131244"), linha_fedhub(VOUCHER="20130786"), linha_fedhub(VOUCHER="20131244"),
            ]}
        self.Service.return_value.consultar_comissoes.side_effect = consultar

        saida = rodar("--favorecido", "5912", "--confirmar")

        self.assertIn("2 voucher(s) do favorecido 5912", saida)
        self.assertEqual(sorted(VoucherEmitido.objects.values_list("numero", flat=True)), ["20130786", "20131244"])


class ConsultaDeRegistroReconstituidoTests(TestCase):
    def test_consulta_avisa_que_a_composicao_foi_reconstituida(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        with patch("fedhub.management.commands.reconstituir_espelho_voucher.FedhubService") as S:
            S.return_value.consultar_comissoes.return_value = BAIXADAS
            rodar("20131244", "--confirmar")

        usuario = get_user_model().objects.create_user(
            email="fin@fedcorp.test", password="x", nome_completo="Fin", nivel_acesso="financeiro"
        )
        client = APIClient()
        client.force_authenticate(user=usuario)

        with patch("fedhub.views.comissao_view.FedhubService") as S:
            S.return_value.consultar_comissoes.return_value = {
                "status": "success", "total_registros": 4,
                "data": BAIXADAS["data"] + [linha_fedhub(parcela=13, documento="0001631763", DT_BAIXA=None)],
            }
            resposta = client.get("/comissoes/consultar/", {"voucher": "20131244"})

        self.assertTrue(resposta.data["espelho"])
        self.assertEqual(resposta.data["dados"]["total_registros"], 3)
        self.assertIn("reconstituída", resposta.data["aviso"])
