# fedhub/test_cadastro_proxy.py — spec cadastro-etl, CT-CAD-001..006. Sem banco e sem rede:
#   DJANGO_SETTINGS_MODULE=bigcorp.settings python -m unittest fedhub.test_cadastro_proxy

import json
import unittest
from unittest.mock import MagicMock, patch

import django
from django.conf import settings

if not settings.configured:  # pragma: no cover
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bigcorp.settings")
django.setup()

import requests  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from fedhub.services import cadastro_service as mod  # noqa: E402
from fedhub.views.cadastro_view import CadastroProxyView  # noqa: E402


def resposta(status, json_body=None, text="", headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.text = text or json.dumps(json_body)
    if json_body is None:
        r.json.side_effect = ValueError("não é JSON")
    else:
        r.json.return_value = json_body
    return r


class Usuario:
    is_authenticated = True
    is_active = True

    def __init__(self, nivel, email="op@fedcorp.exemplo"):
        self.nivel_acesso, self.email, self.pk, self.id = nivel, email, 1, 1


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CadastroProxyView.as_view()

    def _chamar(self, metodo, rota, usuario=Usuario("admin"), **kw):
        req = getattr(self.factory, metodo)(f"/cadastro/{rota}", **kw)
        if usuario:
            force_authenticate(req, user=usuario)
        return self.view(req, rota=rota)

    # CT-CAD-001
    @patch.object(mod, "get_auth_headers", return_value={"Authorization": "Bearer t", "X-Application-Key": "k"})
    @patch.object(mod.requests, "request")
    def test_get_repassa_query_headers_status_e_corpo(self, request, _):
        request.return_value = resposta(200, {"linhas": [], "total": 0})
        r = self._chamar("get", "administradoras", data={"busca": "bbz", "limite": "50"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"linhas": [], "total": 0})
        args, kw = request.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/api/etl/administradoras"))
        self.assertEqual(kw["params"]["busca"], "bbz")
        self.assertEqual(kw["headers"]["X-Operador"], "op@fedcorp.exemplo")
        self.assertEqual(kw["headers"]["Authorization"], "Bearer t")
        self.assertEqual(kw["timeout"], 20)
        self.assertTrue(r["X-Request-Id"])
        self.assertIsNone(kw["data"])

    # CT-CAD-002
    @patch.object(mod, "get_auth_headers", return_value={})
    @patch.object(mod.requests, "request")
    def test_erros_do_fedhub_repassados_e_tunel_fora_vira_503(self, request, _):
        request.return_value = resposta(404, {"erro": "nao_encontrado", "mensagem": "Administradora não encontrada."})
        r = self._chamar("get", "administradoras/999")
        self.assertEqual((r.status_code, r.data["erro"]), (404, "nao_encontrado"))
        request.return_value = resposta(502, None, text="<html>ngrok</html>")
        r = self._chamar("get", "totais")
        self.assertEqual((r.status_code, r.data["erro"], r.data["origem"]), (503, "servico_indisponivel", "fedconnect"))
        request.side_effect = requests.Timeout("lento")
        r = self._chamar("get", "totais")
        self.assertEqual(r.status_code, 503)

    # CT-CAD-003
    @patch.object(mod, "get_auth_headers", return_value={})
    @patch.object(mod.requests, "request")
    def test_post_repassa_corpo_idempotency_e_request_id(self, request, _):
        request.return_value = resposta(201, {"papel_id": 1}, headers={"Idempotent-Replayed": "true"})
        corpo = {"nome": "X", "contatos": []}
        r = self._chamar("post", "administradoras", data=json.dumps(corpo), content_type="application/json",
                         HTTP_IDEMPOTENCY_KEY="adm-1", HTTP_X_REQUEST_ID="rid-123")
        self.assertEqual(r.status_code, 201)
        args, kw = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(json.loads(kw["data"]), corpo)
        self.assertEqual(kw["headers"]["Idempotency-Key"], "adm-1")
        self.assertEqual(kw["headers"]["X-Request-Id"], "rid-123")
        self.assertEqual(kw["timeout"], 30)
        self.assertEqual(r["X-Request-Id"], "rid-123")
        self.assertEqual(r["Idempotent-Replayed"], "true")
        r = self._chamar("delete", "administradoras/1")
        self.assertEqual(r.status_code, 405)

    # CT-CAD-004
    @patch.object(mod.requests, "request")
    def test_nivel_e_autenticacao(self, request):
        r = self._chamar("get", "administradoras", usuario=Usuario("usuario"))
        self.assertEqual((r.status_code, r.data["erro"]), (403, "sem_acesso"))
        r = self._chamar("get", "administradoras", usuario=Usuario("ti"))
        self.assertEqual(r.status_code, 403)  # PA-014: só admin por ora
        request.assert_not_called()
        r = self._chamar("get", "administradoras", usuario=None)
        self.assertEqual(r.status_code, 401)

    # CT-CAD-005
    @patch.object(mod.requests, "request")
    def test_rota_invalida(self, request):
        for rota in ("../auth/token", "a//b", "espaço x"):
            r = self._chamar("get", rota)
            self.assertEqual((r.status_code, r.data["erro"]), (400, "rota_invalida"), rota)
        request.assert_not_called()
        self.assertTrue(mod.CadastroService()._url("/x/").endswith("/api/etl/x"))

    # CT-CAD-006
    def test_rota_registrada_e_god_object_intocado(self):
        from django.urls import resolve

        self.assertEqual(resolve("/cadastro/administradoras/10/faturas").func.view_class, CadastroProxyView)
        import inspect

        from consultas.services import fedhub_service

        self.assertNotIn("/api/etl", inspect.getsource(fedhub_service))


if __name__ == "__main__":
    unittest.main()
