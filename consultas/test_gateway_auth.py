# consultas/test_gateway_auth.py — JWT do Kong + normalização de URL (GATEWAY.md)
#
# Sem banco e sem Django test runner:
#   python -m unittest consultas.test_gateway_auth
#
# Cobre os dois bugs do gateway: (1) toda chamada ao gateway precisa levar o
# JWT do Kong — inclusive o POST /api/auth/token do FedHub; (2) FEDHUB_URL
# com barra final não pode gerar "//api/..." depois do strip_path do Kong.

import time
import unittest
from unittest.mock import MagicMock, patch

import jwt

from consultas.utils import fedhub_auth
from consultas.utils import get_headers as headers_mod
from consultas.utils import kong_auth
from consultas.utils.kong_auth import HEADER_PADRAO, KongAuth


SEGREDO = "segredo-de-teste"


def fake_config(mapa):
    """Substitui decouple.config no módulo alvo: lê só do dicionário dado."""
    def _config(chave, default=None, **kwargs):
        return mapa.get(chave, default)
    return _config


class KongTokenTeste(unittest.TestCase):
    def test_sem_segredo_retorna_none(self):
        with patch.object(kong_auth, "config", fake_config({})):
            self.assertIsNone(KongAuth().token())

    def test_token_hs256_com_iss_e_exp(self):
        cfg = {"FEDHUB_JWT_SECRET": SEGREDO, "FEDHUB_JWT_KEY": "fedconnect"}
        with patch.object(kong_auth, "config", fake_config(cfg)):
            token = KongAuth().token()
        payload = jwt.decode(token, SEGREDO, algorithms=["HS256"])
        self.assertEqual(payload["iss"], "fedconnect")
        # exp ~ agora + 900s (payload combinado no GATEWAY.md)
        self.assertAlmostEqual(payload["exp"], int(time.time()) + 900, delta=5)

    def test_cache_reusa_token_enquanto_valido(self):
        cfg = {"FEDHUB_JWT_SECRET": SEGREDO}
        auth = KongAuth()
        with patch.object(kong_auth, "config", fake_config(cfg)):
            self.assertIs(auth.token(), auth.token())

    def test_renova_na_margem_de_60s(self):
        cfg = {"FEDHUB_JWT_SECRET": SEGREDO}
        auth = KongAuth()
        relogio = MagicMock()
        relogio.time.return_value = 1_000_000.0
        with patch.object(kong_auth, "config", fake_config(cfg)), \
             patch.object(kong_auth, "time", relogio):
            primeiro = auth.token()
            relogio.time.return_value = 1_000_000.0 + 900 - 59  # dentro da margem
            segundo = auth.token()
        self.assertNotEqual(primeiro, segundo)

    def test_gateway_headers_sem_segredo_vazio(self):
        with patch.object(kong_auth, "config", fake_config({})):
            kong_auth._auth._token = None  # limpa o singleton entre testes
            self.assertEqual(kong_auth.gateway_headers(), {})

    def test_gateway_headers_header_padrao_e_custom(self):
        cfg = {"FEDHUB_JWT_SECRET": SEGREDO}
        with patch.object(kong_auth, "config", fake_config(cfg)):
            kong_auth._auth._token = None
            h = kong_auth.gateway_headers()
            self.assertIn(HEADER_PADRAO, h)
            self.assertTrue(h[HEADER_PADRAO].startswith("Bearer "))
        cfg["FEDHUB_GATEWAY_AUTH_HEADER"] = "Authorization"
        with patch.object(kong_auth, "config", fake_config(cfg)):
            h = kong_auth.gateway_headers()
            self.assertIn("Authorization", h)


class GetHeadersTeste(unittest.TestCase):
    def test_tres_credenciais_juntas(self):
        with patch.object(headers_mod, "config", fake_config({"FEDHUB_X_API_KEY": "legada"})), \
             patch.object(headers_mod, "bearer_token", return_value="tok-fedhub"), \
             patch.object(headers_mod, "gateway_headers", return_value={HEADER_PADRAO: "Bearer tok-kong"}):
            h = headers_mod.get_headers()
        self.assertEqual(h["X-Application-Key"], "legada")
        self.assertEqual(h["Authorization"], "Bearer tok-fedhub")
        self.assertEqual(h[HEADER_PADRAO], "Bearer tok-kong")
        self.assertEqual(h["Content-Type"], "application/json")

    def test_fora_do_gateway_nada_muda(self):
        with patch.object(headers_mod, "config", fake_config({"FEDHUB_X_API_KEY": "legada"})), \
             patch.object(headers_mod, "bearer_token", return_value=None), \
             patch.object(headers_mod, "gateway_headers", return_value={}):
            h = headers_mod.get_auth_headers()
        self.assertEqual(h, {"X-Application-Key": "legada"})


class FedhubAuthViaGatewayTeste(unittest.TestCase):
    def _renovar(self, url_env):
        cfg = {"FEDHUB_URL": url_env, "FEDHUB_CLIENT_ID": "cid", "FEDHUB_CLIENT_SECRET": "cs"}
        auth = fedhub_auth.FedHubAuth()
        post = MagicMock()
        post.return_value.json.return_value = {"access_token": "t", "expires_in": 3600}
        with patch.object(fedhub_auth, "config", fake_config(cfg)), \
             patch.object(fedhub_auth, "gateway_headers", return_value={HEADER_PADRAO: "Bearer tok-kong"}), \
             patch.object(fedhub_auth.requests, "post", post):
            auth._renovar()
        return post.call_args

    def test_barra_final_nao_gera_barra_dupla(self):
        chamada = self._renovar("https://gateway.fedhub.com.br/fedhub/")
        self.assertEqual(chamada.args[0], "https://gateway.fedhub.com.br/fedhub/api/auth/token")

    def test_token_do_kong_vai_no_proprio_auth_token(self):
        chamada = self._renovar("https://gateway.fedhub.com.br/fedhub")
        self.assertEqual(chamada.kwargs["headers"], {HEADER_PADRAO: "Bearer tok-kong"})


if __name__ == "__main__":
    unittest.main()
