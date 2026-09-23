# indicadores/test_painel_tv.py
#
# Painel de TV (spec indicadores-painel-tv, RF-IEX-009). O que se prova aqui é o
# CONTRATO da rota: exige usuário autenticado, repassa o que o FedHub devolve
# sem recalcular, e traduz cada falha em 503 com `erro` nomeado. O FedHub é
# substituído por `patch`, como o resto da suíte faz com o que é externo.

from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from indicadores.services import painel_tv

ROTA = "/indicadores/painel-tv/"

LINHA = {
    "seguradora_sigla": "ALLI", "seguradora_nome": "ALLIANZ SEGUROS", "codram": 4,
    "ramo_sigla": "COND", "ramo_nome": "CONDOMINIO", "mes_atual": "2026-09-01",
    "mes_anterior": "2025-09-01", "valor_atual": "819768.8700", "valor_anterior": "690450.0000",
    "apolices_atual": "211", "apolices_anterior": "180", "valor_meta": None,
    "variacao_percentual": "18.7", "atingimento": None,
}


class PainelTvTests(APITestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(email="tv@teste.local", password="x", nivel_acesso="admin")

    def test_sem_login_e_401(self):
        self.assertEqual(self.client.get(ROTA).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_repassa_as_linhas_do_fedhub_sem_recalcular(self):
        """`valor_meta` nulo continua nulo e os decimais chegam como texto: a tela soma,
        a rota não. É a mesma regra do FedHub para o lake (nada é convertido no caminho)."""
        self.client.force_authenticate(self.usuario)
        with patch.object(painel_tv, "linhas", return_value=[LINHA]):
            resposta = self.client.get(ROTA)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        corpo = resposta.json()
        self.assertTrue(corpo["sucesso"])
        self.assertIn("gerado_em", corpo)
        self.assertEqual(corpo["linhas"], [LINHA])

    def test_lake_sem_contrato_publicado_e_503_nomeado(self):
        """No servidor do lake as views ainda não existem: o estado é esperado e a tela
        precisa distingui-lo de "FedHub caiu" — um se resolve publicando, o outro ligando."""
        self.client.force_authenticate(self.usuario)
        with patch.object(painel_tv, "linhas", side_effect=painel_tv.LakeIndisponivel("contrato_nao_publicado", "view ausente")):
            resposta = self.client.get(ROTA)
        self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resposta.json()["erro"], "contrato_nao_publicado")

    def test_fedhub_fora_e_503_fedhub_indisponivel(self):
        self.client.force_authenticate(self.usuario)
        with patch.object(painel_tv, "linhas", side_effect=requests.ConnectionError("recusado")):
            resposta = self.client.get(ROTA)
        self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resposta.json()["erro"], "fedhub_indisponivel")


class ServicoPainelTvTests(APITestCase):
    def test_503_do_fedhub_vira_lake_indisponivel_com_o_erro_do_fedhub(self):
        class Resposta:
            status_code = 503
            def json(self):
                return {"detail": {"erro": "lake_indisponivel", "detalhe": "timeout"}}
        with patch.object(painel_tv.requests, "get", return_value=Resposta()), \
             patch.object(painel_tv, "get_headers", return_value={}), \
             patch.object(painel_tv, "config", return_value="http://fedhub"):
            with self.assertRaises(painel_tv.LakeIndisponivel) as ctx:
                painel_tv.linhas()
        self.assertEqual(ctx.exception.erro, "lake_indisponivel")
