"""A BigDataCorp recusa consultas com HTTP 200 — o erro vem no corpo, em `Status`.

Os corpos usados aqui são os que a plataforma devolveu de verdade em
2026-09-16, numa chamada de conferência: HTTP 200 com
`Status.login[0].Code = -111`. Era isso que atravessava as duas camadas sem
ser notado e deixava a tela de consulta de CPF vazia, sem erro nenhum.
"""
import json
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from consultas.integrations import (
    TEMPO_LIMITE,
    ConsultaCPF,
    RecusaBigDataCorp,
    verificar_recusa_bigdatacorp,
)


RECUSA_TOKEN = {
    "QueryId": "7a51edcc-1a7f-4dc6-99a2-24728467e139",
    "ElapsedMilliseconds": 0,
    "Status": {
        "login": [
            {
                "Code": -111,
                "Message": "INVALID ACCESS TOKEN. MAKE SURE TO ENTER THE CORRECT ACCESS TOKEN IN THE REQUEST HEADER",
            }
        ]
    },
}

SUCESSO = {
    "Result": [{"BasicData": {"Name": "FULANO DE TAL", "TaxIdNumber": "00000000191"}}],
    "Status": {"basic_data": [{"Code": 0, "Message": "OK"}]},
}


class _RespostaFalsa:
    """Só o que as integrações usam de um `requests.Response`."""

    def __init__(self, corpo, status_code=200):
        self._corpo = corpo
        self.status_code = status_code
        self.content = json.dumps(corpo).encode()

    def json(self):
        return self._corpo

    def raise_for_status(self):
        return None


class VerificarRecusaTests(TestCase):
    def test_codigo_negativo_vira_recusa_com_a_mensagem_da_base(self):
        with self.assertRaises(RecusaBigDataCorp) as ctx:
            verificar_recusa_bigdatacorp(RECUSA_TOKEN)

        mensagem = str(ctx.exception)
        self.assertIn("login", mensagem)
        self.assertIn("INVALID ACCESS TOKEN", mensagem)
        self.assertIn("-111", mensagem)

    def test_sucesso_passa_intacto(self):
        self.assertIs(verificar_recusa_bigdatacorp(SUCESSO), SUCESSO)

    def test_codigo_positivo_e_aviso_e_nao_recusa(self):
        """"Nada encontrado" precisa continuar chegando como consulta vazia."""
        vazio = {"Result": [], "Status": {"basic_data": [{"Code": 101, "Message": "NO DATA FOUND"}]}}

        self.assertIs(verificar_recusa_bigdatacorp(vazio), vazio)

    def test_resposta_sem_status_passa_intacta(self):
        for corpo in ({"Result": []}, {"Status": "texto"}, {}, None):
            self.assertIs(verificar_recusa_bigdatacorp(corpo), corpo)

    def test_varias_recusas_entram_todas_na_mensagem(self):
        corpo = {
            "Status": {
                "login": [{"Code": -111, "Message": "INVALID ACCESS TOKEN"}],
                "api": [{"Code": -128, "Message": "NO CREDITS LEFT"}],
            }
        }

        with self.assertRaises(RecusaBigDataCorp) as ctx:
            verificar_recusa_bigdatacorp(corpo)

        self.assertIn("INVALID ACCESS TOKEN", str(ctx.exception))
        self.assertIn("NO CREDITS LEFT", str(ctx.exception))


class ConsultaCPFTests(TestCase):
    def setUp(self):
        self.env = patch.dict(
            "os.environ",
            {"BIGDATA_ACCESS_TOKEN": "token-de-teste", "BIGDATA_TOKEN_ID": "id-de-teste"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    @patch("consultas.integrations.requests.post")
    def test_recusa_com_http_200_nao_passa_por_sucesso(self, post):
        post.return_value = _RespostaFalsa(RECUSA_TOKEN)

        with self.assertRaises(RecusaBigDataCorp):
            ConsultaCPF.consultar("00000000191")

    @patch("consultas.integrations.requests.post")
    def test_consulta_valida_devolve_o_corpo(self, post):
        post.return_value = _RespostaFalsa(SUCESSO)

        self.assertEqual(ConsultaCPF.consultar("00000000191"), SUCESSO)

    @patch("consultas.integrations.requests.post")
    def test_tempo_limite_separa_conectar_de_ler(self, post):
        """Um destino que engole pacotes não pode segurar a requisição até o 504."""
        post.return_value = _RespostaFalsa(SUCESSO)

        ConsultaCPF.consultar("00000000191")

        self.assertEqual(post.call_args.kwargs["timeout"], TEMPO_LIMITE)
        conectar, ler = TEMPO_LIMITE
        # O balanceador da DigitalOcean corta em 60 s; o pior caso tem que caber.
        self.assertLess(conectar + ler, 60)


class RealizarConsultaViewTests(APITestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email="operador@fedcorp.test", password="senha-de-teste",
            nome_completo="Operador de Teste", nivel_acesso="usuario",
        )
        self.client.force_authenticate(user=self.usuario)

    @patch("consultas.views.ConsultaCPF.consultar")
    def test_recusa_vira_502_com_a_mensagem_e_nao_grava_historico(self, consultar):
        from consultas.models import HistoricoConsulta

        consultar.side_effect = RecusaBigDataCorp(
            "A base de consulta recusou a requisição — login: INVALID ACCESS TOKEN (código -111)"
        )

        resposta = self.client.post(
            "/consultas/realizar/",
            {"tipo_consulta": "cpf", "parametro_consulta": "00000000191"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("INVALID ACCESS TOKEN", resposta.data["detail"])
        # Recusa não é consulta realizada: nada vai para o histórico.
        self.assertEqual(HistoricoConsulta.objects.count(), 0)

    @patch("consultas.views.ConsultaCPF.consultar")
    def test_consulta_valida_continua_200_e_grava_historico(self, consultar):
        from consultas.models import HistoricoConsulta

        consultar.return_value = SUCESSO

        resposta = self.client.post(
            "/consultas/realizar/",
            {"tipo_consulta": "cpf", "parametro_consulta": "00000000191"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["resultado_api"], SUCESSO)
        self.assertEqual(HistoricoConsulta.objects.count(), 1)
