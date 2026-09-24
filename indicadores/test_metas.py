"""CT-IEX-009 (metas: cadastro, upsert, replicação, validação, listagem, exclusão, JWT) e
CT-IEX-010 (`meta_mes` no resumo e no por-seguradora) — spec indicadores-executivos, RF-IEX-008,
PA-023; desde RF-IEX-010 (23/09/2026) as metas moram no LAKE e chegam pelo FedHub.

O FedHub é substituído por `FedHubFalso`: um servidor de metas em memória com a
mesma semântica das rotas `/api/lake/metas` (upsert pela chave, réplica de meses,
409 em chave ocupada, 404 em id inexistente). O que se prova aqui é o contrato
do FedConnect com o front, que não mudou, e o cálculo de `meta_mes`.

Dados sintéticos: o mesmo snapshot de `tests.py`. No mês 2026-09 (dia 1 a 22) o
universo padrão tem dois documentos com valor: 101 (ALLI × COND, prêmio líquido
900.45) e 102 (PORT × FIAN, 180.00) — realizado líquido do mês 1080.45. A meta
compara com o LÍQUIDO (decisão da gestão para o lake, 23/09/2026).
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status

from indicadores.services import fedhub_lake
from indicadores.services import metas as servico_metas
from indicadores.tests import REF, URLS, _ComCarga

URL_METAS = "/indicadores/metas/"

class _ComFedHub(_ComCarga):
    """`_ComCarga` já liga o FedHub falso; aqui só o atalho de cadastro."""

    def meta(self, seguradora, ramo, valor, competencia="2026-09"):
        return self.fedhub.criar(seguradora, ramo, valor, competencia)


class MetasCrudTests(_ComFedHub):
    """CT-IEX-009: cadastro, upsert na mesma chave, replicar_meses, validações, listagem, exclusão, 401."""

    def post(self, **corpo):
        dados = {"seguradora": "ALLI", "ramo": "COND", "competencia": "2026-09", "valor_meta": "1000000.00"}
        dados.update(corpo)
        return self.client.post(URL_METAS, dados, format="json")

    def put(self, meta_id, **corpo):
        dados = {"seguradora": "ALLI", "ramo": "COND", "competencia": "2026-09", "valor_meta": "1000000.00"}
        dados.update(corpo)
        return self.client.put(f"{URL_METAS}{meta_id}/", dados, format="json")

    def test_put_atualiza_a_propria_meta_mesmo_trocando_seguradora_ou_ramo(self):
        """Relato do dono (2026-09-23): editar criava outra meta quando a chave mudava."""
        criada = self.post().data["metas"][0]

        resposta = self.put(criada["id"], ramo="FIAN", valor_meta="10.00")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        linha = resposta.data["metas"][0]
        self.assertEqual((linha["id"], linha["ramo"], linha["valor_meta"]), (criada["id"], "FIAN", "10.00"))
        self.assertEqual(len(self.fedhub.metas), 1)  # não nasceu outra

    def test_put_recusa_chave_que_ja_tem_meta_e_404_para_id_inexistente(self):
        alli_cond = self.post().data["metas"][0]
        self.post(ramo="FIAN")

        colisao = self.put(alli_cond["id"], ramo="FIAN")
        self.assertEqual(colisao.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("meta", colisao.data["erro"])
        self.assertEqual(self.fedhub.metas[alli_cond["id"]]["ramo"], "COND")  # intacta

        self.assertEqual(self.put(999_999).status_code, status.HTTP_404_NOT_FOUND)

    def test_cria_meta_e_devolve_a_linha(self):
        resposta = self.post()

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertTrue(resposta.data["sucesso"])
        linha = resposta.data["metas"][0]
        self.assertEqual(linha["seguradora"], "ALLI")
        self.assertEqual(linha["ramo"], "COND")
        self.assertEqual(linha["competencia"], "2026-09")
        self.assertEqual(linha["valor_meta"], "1000000.00")
        self.assertEqual(linha["atualizado_por"], "usr@t.com")  # quem digitou vai para o lake
        self.assertEqual(set(linha), {"id", "seguradora", "seguradora_nome", "ramo", "ramo_nome", "competencia",
                                      "valor_meta", "atualizado_em", "atualizado_por"})

    def test_upsert_na_mesma_chave_atualiza_em_vez_de_duplicar(self):
        self.post()
        resposta = self.post(valor_meta="2000000.00")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(self.fedhub.metas), 1)
        self.assertEqual(resposta.data["metas"][0]["valor_meta"], "2000000.00")

    def test_replicar_meses_cria_os_seguintes_virando_o_ano(self):
        resposta = self.post(competencia="2026-11", valor_meta="5.00", replicar_meses=3)

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual([m["competencia"] for m in resposta.data["metas"]], ["2026-11", "2026-12", "2027-01", "2027-02"])
        self.assertEqual(len(self.fedhub.metas), 4)

        self.post(competencia="2026-11", valor_meta="7.00", replicar_meses=3)  # upsert em todas
        self.assertEqual(len(self.fedhub.metas), 4)
        janeiro = next(m for m in self.fedhub.metas.values() if m["competencia"] == "2027-01")
        self.assertEqual(janeiro["valor_meta"], "7.00")

    def test_somar_meses_e_competencia(self):
        self.assertEqual(servico_metas.somar_meses(date(2026, 12, 1), 1), date(2027, 1, 1))
        self.assertEqual(servico_metas.somar_meses(date(2026, 1, 1), 11), date(2026, 12, 1))
        self.assertEqual(servico_metas.competencia_de("2026-09"), date(2026, 9, 1))
        with self.assertRaises(ValueError):
            servico_metas.competencia_de("2026/09")

    def test_entradas_invalidas_dao_400(self):
        casos = [
            {"seguradora": "XXXX"},
            {"ramo": "NADA"},
            {"competencia": "2026-13"},
            {"competencia": "set/2026"},
            {"valor_meta": "0"},
            {"valor_meta": "-5"},
            {"replicar_meses": 12},
        ]
        for corpo in casos:
            resposta = self.post(**corpo)
            self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST, corpo)
            self.assertFalse(resposta.data["sucesso"])
        self.assertEqual(len(self.fedhub.metas), 0)

    def test_lista_por_competencia_ordenada_com_total(self):
        self.meta("PORT", "FIAN", "500.00")
        self.meta("ALLI", "FIAN", "20.00")
        self.meta("ALLI", "COND", "1000000.00")
        self.meta("ALLI", "COND", "999.00", competencia="2026-08")  # outro mês: fora

        resposta = self.client.get(URL_METAS, {"competencia": "2026-09"})

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["competencia"], "2026-09")
        self.assertEqual([(m["seguradora"], m["ramo"]) for m in resposta.data["metas"]],
                         [("ALLI", "COND"), ("ALLI", "FIAN"), ("PORT", "FIAN")])
        self.assertEqual(resposta.data["total_meta"], "1000520.00")

        vazio = self.client.get(URL_METAS, {"competencia": "2025-01"})
        self.assertEqual(vazio.data["metas"], [])
        self.assertIsNone(vazio.data["total_meta"])

    def test_lista_sem_competencia_usa_o_mes_corrente_local(self):
        from django.utils import timezone

        hoje = timezone.localdate()
        resposta = self.client.get(URL_METAS)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["competencia"], f"{hoje.year:04d}-{hoje.month:02d}")

    def test_apaga_meta_e_404_quando_nao_existe(self):
        criada = self.meta("ALLI", "COND", "10.00")

        resposta = self.client.delete(f"{URL_METAS}{criada['id']}/")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self.fedhub.metas), 0)

        resposta = self.client.delete(f"{URL_METAS}{criada['id']}/")
        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)

    def test_sem_jwt_401_em_listar_gravar_e_apagar(self):
        criada = self.meta("ALLI", "COND", "10.00")
        self.client.force_authenticate(None)

        self.assertEqual(self.client.get(URL_METAS).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.post().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.delete(f"{URL_METAS}{criada['id']}/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(len(self.fedhub.metas), 1)

    def test_lake_fora_da_503_nomeado_sem_derrubar_a_tela(self):
        """RF-IEX-010: a meta mora no lake; se ele não responde, a tela sabe por quê."""
        self.fedhub.fora = True
        for resposta in (self.client.get(URL_METAS, {"competencia": "2026-09"}), self.post()):
            self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertEqual(resposta.data["erro"], "lake_indisponivel")


class MetaMesTests(_ComFedHub):
    """CT-IEX-010: `meta_mes` do resumo e colunas de meta no por-seguradora, com metas vindas do lake."""

    def meta_mes(self, **params):
        resposta = self.get("resumo", **params)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        return resposta.data["meta_mes"]

    def test_sem_metas_meta_vem_null_e_realizado_do_mes_vem_mesmo_assim(self):
        bloco = self.meta_mes()

        self.assertEqual(bloco["competencia"], "2026-09")
        self.assertEqual(bloco["dias_no_mes"], 30)
        self.assertEqual(bloco["dias_decorridos"], 22)
        self.assertIsNone(bloco["meta"])
        self.assertEqual(bloco["realizado"], "1080.45")  # líquido: 900.45 + 180.00
        self.assertEqual(bloco["documentos_com_valor"], 2)
        self.assertIsNone(bloco["falta"])
        self.assertIsNone(bloco["percentual"])
        self.assertEqual(bloco["projecao"], "1473.34")  # 1080.45 / 22 × 30
        self.assertEqual(bloco["metas_consideradas"], 0)

    def test_meta_soma_conforme_o_filtro(self):
        self.meta("ALLI", "COND", "1000000.00")
        self.meta("PORT", "FIAN", "500.00")
        self.meta("TOKI", "AUTO", "100.00")
        self.meta("ALLI", "COND", "999.00", competencia="2026-08")  # outro mês: fora

        todas = self.meta_mes()
        self.assertEqual((todas["meta"], todas["metas_consideradas"]), ("1000600.00", 3))
        alli = self.meta_mes(seguradora="ALLI")
        self.assertEqual((alli["meta"], alli["metas_consideradas"]), ("1000000.00", 1))
        port_fian = self.client.get(URLS["resumo"], {"data_referencia": REF, "seguradora": "PORT", "ramo": "FIAN"}).data["meta_mes"]
        self.assertEqual(port_fian["meta"], "500.00")
        so_ramo = self.meta_mes(ramo="COND")
        self.assertEqual(so_ramo["meta"], "1000000.00")
        self.assertEqual(self.meta_mes(seguradora="TOKI", ramo="COND")["meta"], None)  # TOKI só tem meta em AUTO

    def test_realizado_usa_a_janela_do_mes_mesmo_com_periodo_semana_ou_hoje(self):
        self.meta("ALLI", "COND", "2000.00")
        for periodo in ("semana", "hoje", "ano", "mes"):
            resposta = self.get("resumo", periodo=periodo).data
            # Com meta cadastrada, o realizado é só do par com meta (ALLI × COND), não da carteira inteira.
            self.assertEqual(resposta["meta_mes"]["realizado"], "900.45", periodo)
            self.assertEqual(resposta["meta_mes"]["meta"], "2000.00", periodo)
        # O cartão do período, por sua vez, continua respeitando o período: na semana 21..22 não há valor.
        self.assertIsNone(self.get("resumo", periodo="semana").data["atual"]["valor_fechado"])
        # Referência em outro mês muda a competência e os dias.
        outubro = self.meta_mes(data_referencia="2026-10-05")
        self.assertEqual((outubro["competencia"], outubro["dias_no_mes"], outubro["dias_decorridos"]), ("2026-10", 31, 5))
        self.assertIsNone(outubro["meta"])

    def test_falta_percentual_e_projecao(self):
        self.meta("ALLI", "COND", "2000.00")
        self.meta("PORT", "FIAN", "100.00")

        alli = self.meta_mes(seguradora="ALLI")
        self.assertEqual(alli["realizado"], "900.45")
        self.assertEqual(alli["falta"], "1099.55")
        self.assertEqual(alli["percentual"], 45.0)  # 45.0225 arredonda para uma decimal
        self.assertIsInstance(alli["percentual"], float)
        self.assertEqual(alli["projecao"], "1227.89")  # 900.45 / 22 × 30

        port = self.meta_mes(seguradora="PORT")
        self.assertEqual(port["realizado"], "180.00")
        self.assertEqual(port["percentual"], 180.0)  # pode passar de 100

    def test_por_seguradora_traz_meta_realizado_e_percentual(self):
        self.meta("ALLI", "COND", "1800.90")

        resposta = self.get("por_seguradora")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        alli = next(l for l in resposta.data["linhas"] if l["seguradora"] == "ALLI")
        self.assertEqual((alli["meta_mes"], alli["realizado_mes"], alli["percentual_meta"]), ("1800.90", "900.45", 50.0))
        self.assertEqual(resposta.data["total"]["meta_mes"], "1800.90")


class MetaComLakeForaTests(_ComFedHub):
    """RF-IEX-010: lake fora não derruba o resumo — a meta some, avisada, e o resto segue."""

    def test_resumo_e_por_seguradora_seguem_sem_meta_quando_o_lake_nao_responde(self):
        self.fedhub.fora = True
        resumo = self.get("resumo")
        self.assertEqual(resumo.status_code, status.HTTP_200_OK, resumo.data)
        bloco = resumo.data["meta_mes"]
        self.assertIsNone(bloco["meta"])
        self.assertTrue(bloco["metas_indisponiveis"])
        self.assertEqual(bloco["realizado"], "1080.45")  # o realizado é do espelho e continua
        por_seg = self.get("por_seguradora")
        self.assertEqual(por_seg.status_code, status.HTTP_200_OK, por_seg.data)
        self.assertIsNone(por_seg.data["total"]["meta_mes"])


class ClienteFedHubLakeTests(SimpleTestCase):
    """`fedhub_lake.chamar`: as três famílias de resposta, com `requests` substituído.
    Fora de `_ComCarga` de propósito: lá `chamar` já é o FedHub falso."""

    def _resposta(self, status_code, corpo=None, texto=""):
        class R:
            pass
        r = R(); r.status_code = status_code; r.text = texto
        r.json = (lambda: corpo) if corpo is not None else (lambda: (_ for _ in ()).throw(ValueError()))
        return r

    def test_fedhub_sem_a_rota_e_indisponibilidade_nomeada_e_nao_recusa(self):
        with patch.object(fedhub_lake.requests, "request", return_value=self._resposta(404, {"detail": "Not Found"})):
            with self.assertRaises(fedhub_lake.LakeIndisponivel) as ctx:
                fedhub_lake.chamar("GET", "metas", params={"competencia": "2026-09"})
        self.assertEqual(ctx.exception.erro, "fedhub_sem_rota")

    def test_404_nomeado_pelo_fedhub_e_recusa(self):
        corpo = {"detail": {"erro": "meta_inexistente", "detalhe": "meta não encontrada."}}
        with patch.object(fedhub_lake.requests, "request", return_value=self._resposta(404, corpo)):
            with self.assertRaises(fedhub_lake.RecusaDoFedHub) as ctx:
                fedhub_lake.chamar("DELETE", "metas/9")
        self.assertEqual(ctx.exception.erro, "meta_inexistente")

    def test_503_do_fedhub_vira_lake_indisponivel_com_o_erro_dele(self):
        corpo = {"detail": {"erro": "contrato_nao_publicado", "detalhe": "view ausente"}}
        with patch.object(fedhub_lake.requests, "request", return_value=self._resposta(503, corpo)):
            with self.assertRaises(fedhub_lake.LakeIndisponivel) as ctx:
                fedhub_lake.chamar("GET", "metas", params={"competencia": "2026-09"})
        self.assertEqual(ctx.exception.erro, "contrato_nao_publicado")
