"""Consulta de CNPJ: BrasilAPI primeiro, BigDataCorp quando ela cai.

Em 01/10/2026 a BrasilAPI respondia 504 em produção e a consulta de CNPJ
parava inteira. O corpo da BigDataCorp abaixo é o que a plataforma devolveu
nesse dia para o CNPJ do Banco do Brasil, enxugado — inclusive o aviso
"-205 DEPRECATED DATASET" ao lado do `OK` em `addresses`.
"""
import json
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from consultas.integrations import (
    TEMPO_LIMITE,
    ConsultaCNPJ,
    RecusaBigDataCorp,
    bigdatacorp_para_brasilapi,
    verificar_recusa_bigdatacorp,
)

CNPJ = "00000000000191"

BRASILAPI_OK = {"cnpj": CNPJ, "razao_social": "BANCO DO BRASIL SA", "uf": "DF"}

BIGDATACORP_OK = {
    "Result": [
        {
            "BasicData": {
                "TaxIdNumber": CNPJ,
                "OfficialName": "BANCO DO BRASIL SA",
                "TradeName": "DIRECAO GERAL",
                "FoundedDate": "1966-08-01T00:00:00Z",
                "IsHeadquarter": True,
                "HeadquarterState": "DF",
                "TaxIdStatus": "ATIVA",
                "TaxIdStatusReason": " ",
                "TaxIdStatusDate": "2026-09-30T00:00:00Z",
                "CompanyType_ReceitaFederal": "DEMAIS",
                "TaxRegimes": {"Simples": False},
                "Activities": [
                    {"IsMain": True, "Code": "6422100", "Activity": "BANCOS MULTIPLOS, COM CARTEIRA COMERCIAL"},
                    {"IsMain": False, "Code": "6499999", "Activity": "OUTRAS ATIVIDADES DE SERVICOS FINANCEIROS"},
                ],
                "LegalNature": {"Code": "2038", "Activity": "SOCIEDADE DE ECONOMIA MISTA"},
                "AdditionalOutputData": {"CapitalRS": "120000000000.00"},
            },
            "Addresses": [
                {
                    "Type": "WORK", "Priority": 2, "Typology": "R", "AddressMain": "SOUZA FRANCO",
                    "Number": "1535", "Neighborhood": "CENTRO", "City": "MOGI DAS CRUZES",
                    "State": "SP", "ZipCode": "08780120",
                },
                {
                    "Type": "OFFICIAL REGISTRATION", "Priority": 1, "Typology": "",
                    "AddressMain": "Q SAUN QUADRA 5 BLOCO B TORRE I, II, III", "Number": "SN",
                    "Complement": "ANDAR T I", "Neighborhood": "ASA NORTE", "City": "BRASILIA",
                    "State": "DF", "ZipCode": "70040912",
                },
            ],
        }
    ],
    "Status": {
        "addresses": [
            {"Code": 0, "Message": "OK"},
            {"Code": -205, "Message": "DEPRECATED DATASET. PLEASE CHECK THE DOCUMENTATION AND UPGRADE TO A SUPPORTED VERSION."},
        ],
        "basic_data": [{"Code": 0, "Message": "OK"}],
    },
}

RECUSA_SALDO = {"Status": {"api": [{"Code": -128, "Message": "NO CREDITS LEFT"}]}}


class _Resposta:
    def __init__(self, corpo, status_code=200):
        self._corpo = corpo
        self.status_code = status_code
        self.text = corpo if isinstance(corpo, str) else json.dumps(corpo)

    def json(self):
        if isinstance(self._corpo, str):
            raise json.JSONDecodeError("Expecting value", self._corpo, 0)
        return self._corpo


class _ComCredencial(TestCase):
    def setUp(self):
        env = patch.dict("os.environ", {"BIGDATA_ACCESS_TOKEN": "token", "BIGDATA_TOKEN_ID": "id"})
        env.start()
        self.addCleanup(env.stop)


@patch("consultas.integrations.requests.post")
@patch("consultas.integrations.requests.get")
class FallbackTests(_ComCredencial):
    def test_brasilapi_ok_nao_consulta_a_bigdatacorp(self, get, post):
        get.return_value = _Resposta(BRASILAPI_OK)

        self.assertEqual(ConsultaCNPJ.consultar(CNPJ), BRASILAPI_OK)
        post.assert_not_called()

    def test_504_da_brasilapi_cai_na_bigdatacorp(self, get, post):
        get.return_value = _Resposta("<html>504 Gateway Time-out</html>", status_code=504)
        post.return_value = _Resposta(BIGDATACORP_OK)

        resultado = ConsultaCNPJ.consultar(CNPJ)

        self.assertEqual(resultado["razao_social"], "BANCO DO BRASIL SA")
        self.assertEqual(resultado["fonte"], "bigdatacorp")
        self.assertEqual(post.call_args.kwargs["json"]["q"], f"doc{{{CNPJ}}}")
        self.assertEqual(post.call_args.kwargs["timeout"], TEMPO_LIMITE)

    def test_timeout_e_conexao_caem_na_bigdatacorp(self, get, post):
        post.return_value = _Resposta(BIGDATACORP_OK)
        for erro in (requests.exceptions.Timeout("lento"), requests.exceptions.ConnectionError("fora")):
            get.side_effect = erro
            self.assertEqual(ConsultaCNPJ.consultar(CNPJ)["fonte"], "bigdatacorp")

    def test_brasilapi_sem_json_cai_na_bigdatacorp(self, get, post):
        get.return_value = _Resposta("manutenção", status_code=200)
        post.return_value = _Resposta(BIGDATACORP_OK)

        self.assertEqual(ConsultaCNPJ.consultar(CNPJ)["fonte"], "bigdatacorp")

    def test_cnpj_invalido_nao_gasta_consulta_na_bigdatacorp(self, get, post):
        get.return_value = _Resposta({"message": "CNPJ inválido"}, status_code=400)

        with self.assertRaises(ValueError):
            ConsultaCNPJ.consultar("12345678000100")
        post.assert_not_called()

    def test_as_duas_fora_viram_erro_de_comunicacao_com_as_duas_causas(self, get, post):
        get.return_value = _Resposta("gateway", status_code=504)
        post.return_value = _Resposta("indisponível", status_code=503)

        with self.assertRaises(requests.exceptions.RequestException) as ctx:
            ConsultaCNPJ.consultar(CNPJ)

        self.assertIn("BrasilAPI", str(ctx.exception))
        self.assertIn("504", str(ctx.exception))
        self.assertIn("503", str(ctx.exception))

    def test_recusa_da_bigdatacorp_no_fallback_continua_recusa(self, get, post):
        get.return_value = _Resposta("gateway", status_code=504)
        post.return_value = _Resposta(RECUSA_SALDO)

        with self.assertRaises(RecusaBigDataCorp) as ctx:
            ConsultaCNPJ.consultar(CNPJ)
        self.assertIn("NO CREDITS LEFT", str(ctx.exception))

    def test_nao_encontrado_na_bigdatacorp_e_valueerror(self, get, post):
        get.return_value = _Resposta({"message": "não encontrado"}, status_code=404)
        post.return_value = _Resposta({"Result": [], "Status": {"basic_data": [{"Code": 0, "Message": "OK"}]}})

        with self.assertRaises(ValueError):
            ConsultaCNPJ.consultar(CNPJ)

    def test_pior_caso_cabe_no_limite_do_balanceador(self, get, post):
        conectar, ler = TEMPO_LIMITE
        # BrasilAPI e BigDataCorp em série; a DigitalOcean corta em 60 s.
        self.assertLess(2 * (conectar + ler), 60)


class SemCredencialTests(TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("consultas.integrations.requests.post")
    @patch("consultas.integrations.requests.get")
    def test_sem_credencial_vira_erro_de_comunicacao(self, get, post):
        get.return_value = _Resposta("gateway", status_code=504)

        with self.assertRaises(requests.exceptions.RequestException):
            ConsultaCNPJ.consultar(CNPJ)
        post.assert_not_called()


class ConversaoTests(TestCase):
    def test_converte_para_o_formato_da_brasilapi(self):
        r = bigdatacorp_para_brasilapi(BIGDATACORP_OK, CNPJ)

        self.assertEqual(r["cnpj"], CNPJ)
        self.assertEqual(r["nome_fantasia"], "DIRECAO GERAL")
        self.assertEqual(r["descricao_situacao_cadastral"], "ATIVA")
        self.assertIsNone(r["descricao_motivo_situacao_cadastral"])  # " " é vazio
        self.assertEqual(r["data_inicio_atividade"], "1966-08-01")
        self.assertEqual(r["data_situacao_cadastral"], "2026-09-30")
        self.assertEqual(r["cnae_fiscal"], 6422100)
        self.assertEqual(r["cnae_fiscal_descricao"], "BANCOS MULTIPLOS, COM CARTEIRA COMERCIAL")
        self.assertEqual(r["cnaes_secundarios"], [{"codigo": 6499999, "descricao": "OUTRAS ATIVIDADES DE SERVICOS FINANCEIROS"}])
        self.assertEqual(r["natureza_juridica"], "SOCIEDADE DE ECONOMIA MISTA")
        self.assertEqual(r["porte"], "DEMAIS")
        self.assertEqual(r["capital_social"], 120000000000.0)
        self.assertEqual(r["descricao_identificador_matriz_filial"], "MATRIZ")
        self.assertIs(r["opcao_pelo_simples"], False)

    def test_endereco_e_o_da_receita_e_nao_o_de_maior_prioridade_da_lista(self):
        r = bigdatacorp_para_brasilapi(BIGDATACORP_OK, CNPJ)

        self.assertEqual(r["municipio"], "BRASILIA")
        self.assertEqual(r["uf"], "DF")
        self.assertEqual(r["cep"], "70040912")
        self.assertEqual(r["bairro"], "ASA NORTE")
        self.assertEqual(r["numero"], "SN")
        self.assertIsNone(r["descricao_tipo_de_logradouro"])

    def test_sem_endereco_da_receita_usa_o_de_maior_prioridade(self):
        corpo = json.loads(json.dumps(BIGDATACORP_OK))
        corpo["Result"][0]["Addresses"][1]["Type"] = "WORK"
        corpo["Result"][0]["Addresses"][1]["Priority"] = 5

        self.assertEqual(bigdatacorp_para_brasilapi(corpo, CNPJ)["municipio"], "MOGI DAS CRUZES")

    def test_sem_empresa_devolve_none(self):
        for corpo in ({"Result": []}, {}, None, {"Result": [{"BasicData": {}}]}):
            self.assertIsNone(bigdatacorp_para_brasilapi(corpo, CNPJ))


class AvisoComSucessoTests(TestCase):
    def test_negativo_ao_lado_do_ok_no_mesmo_grupo_e_aviso(self):
        self.assertIs(verificar_recusa_bigdatacorp(BIGDATACORP_OK), BIGDATACORP_OK)


@patch("consultas.integrations.requests.post")
@patch("consultas.integrations.requests.get")
class RealizarConsultaCnpjViewTests(APITestCase):
    def setUp(self):
        env = patch.dict("os.environ", {"BIGDATA_ACCESS_TOKEN": "token", "BIGDATA_TOKEN_ID": "id"})
        env.start()
        self.addCleanup(env.stop)
        usuario = get_user_model().objects.create_user(
            email="operador@fedcorp.test", password="senha-de-teste",
            nome_completo="Operador de Teste", nivel_acesso="usuario",
        )
        self.client.force_authenticate(user=usuario)

    def test_brasilapi_fora_ainda_responde_200_e_grava_historico(self, get, post):
        from consultas.models import HistoricoConsulta

        get.return_value = _Resposta("gateway", status_code=504)
        post.return_value = _Resposta(BIGDATACORP_OK)

        resposta = self.client.post(
            "/consultas/realizar/", {"tipo_consulta": "cnpj", "parametro_consulta": CNPJ}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["resultado_api"]["razao_social"], "BANCO DO BRASIL SA")
        self.assertEqual(HistoricoConsulta.objects.count(), 1)

    def test_as_duas_fora_viram_503(self, get, post):
        get.return_value = _Resposta("gateway", status_code=504)
        post.side_effect = requests.exceptions.Timeout("lento")

        resposta = self.client.post(
            "/consultas/realizar/", {"tipo_consulta": "cnpj", "parametro_consulta": CNPJ}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
