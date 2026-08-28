# fedhub/test_segunda_via_service.py — 2ª via × FedHub (spec FedHub fedpay-pdf-somente-registrados)
#
# Sem banco e sem Django test runner: `python -m unittest fedhub.test_segunda_via_service`
# com DJANGO_SETTINGS_MODULE=bigcorp.settings. `requests` é mockado.

import unittest
from unittest.mock import MagicMock, patch

from fedhub.services import faturamento_service as mod
from fedhub.services.faturamento_service import FaturamentoService, mensagem_rejeicao


def resposta(status, json_body=None, content=b""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body
    r.text = str(json_body)
    r.content = content
    return r


ITEM = {"FATURA_NUM": "176345", "NOSSO_NUMERO": "0001622648 8", "VALOR_TOTAL": "222,51", "DEDUCOES": "0",
        "LINHA_DIGITAVEL": "x", "LINHA_PURIFICADA": "y", "CANAL": "REMESSA", "IDENTIFICADOR": ""}


class DadosSegundaVia(unittest.TestCase):
    def setUp(self):
        self.svc = FaturamentoService()

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "get")
    def test_200_devolve_dados_e_sem_registro(self, get, _):
        get.return_value = resposta(200, {"status": "success", "data": [dict(ITEM)],
                                          "sem_registro": [{"documento": "D9", "nome_cobrado": "X"}]})
        r = self.svc.processar_dados_segunda_via_boleto("176345")
        self.assertEqual(len(r["dados"]), 1)
        self.assertEqual(r["dados"][0]["CANAL"], "REMESSA")
        self.assertEqual(r["dados"][0]["VALOR_DOCUMENTO"], "222,51")
        self.assertEqual(r["sem_registro"], [{"documento": "D9", "nome_cobrado": "X"}])

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "get")
    def test_200_sem_chave_sem_registro_vira_lista_vazia(self, get, _):
        get.return_value = resposta(200, {"status": "success", "data": [dict(ITEM)]})
        self.assertEqual(self.svc.processar_dados_segunda_via_boleto("1")["sem_registro"], [])

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "get")
    def test_422_todos_sem_registro(self, get, _):
        get.return_value = resposta(422, {"detail": {"status": "error", "motivo": "sem_registro", "data": [],
                                                     "sem_registro": [{"documento": "D1", "nome_cobrado": "A"}]}})
        r = self.svc.processar_dados_segunda_via_boleto("5")
        self.assertEqual(r, {"dados": [], "sem_registro": [{"documento": "D1", "nome_cobrado": "A"}]})

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "get")
    def test_404_marca_nao_encontrada(self, get, _):
        get.return_value = resposta(404, {"detail": "nada"})
        self.assertTrue(self.svc.processar_dados_segunda_via_boleto("404")["nao_encontrada"])

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "get")
    def test_500_continua_none(self, get, _):
        get.return_value = resposta(500, {"detail": "boom"})
        self.assertIsNone(self.svc.processar_dados_segunda_via_boleto("1"))


class EmitirSegundaVia(unittest.TestCase):
    def setUp(self):
        self.svc = FaturamentoService()
        self.boletos = [{"FATURA_NUM": "10", "NOSSO_NUMERO": "D2 8", "LINHA_DIGITAVEL": "1", "LINHA_PURIFICADA": "1"}]

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "post")
    def test_422_do_fedhub_vira_rejeitado_com_mensagem(self, post, _):
        post.return_value = resposta(422, {"detail": {"motivo": "sem_registro", "rejeitados": [
            {"indice": 0, "fatura": "10", "nosso_numero": "D2 8", "motivo": "sem_registro"}]}})
        r = self.svc.emitir_segunda_via_boleto("10", self.boletos)
        self.assertEqual(r["status"], "rejeitado")
        self.assertIn("D2 8", r["erro"])
        self.assertIn("não consta como enviado ao banco", r["erro"])
        self.assertEqual(r["rejeitados"][0]["motivo"], "sem_registro")

    @patch.object(mod, "get_headers", return_value={})
    @patch.object(mod.requests, "delete")
    @patch.object(mod.requests, "post")
    def test_200_segue_fluxo_atual(self, post, delete, _):
        post.return_value = resposta(200, {"arquivo": "BOLETO-10-20260828.pdf"})
        delete.return_value = resposta(200, content=b"%PDF")
        r = self.svc.emitir_segunda_via_boleto("10", self.boletos)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["filename"], "BOLETO-10-20260828.pdf")

    def test_mensagem_rejeicao_por_motivo(self):
        m = mensagem_rejeicao([{"nosso_numero": "A 1", "motivo": "inativo"}, {"nosso_numero": "B 2", "motivo": "nao_localizado"}])
        self.assertIn("2 boleto(s)", m)
        self.assertIn("A 1 (cancelado ou baixado)", m)
        self.assertIn("B 2 (não encontrado na fatura)", m)
        self.assertIn("Reconsulte", mensagem_rejeicao([]))


if __name__ == "__main__":
    unittest.main()
