"""CT-IEX-009 (metas: cadastro, upsert, replicação, validação, listagem, exclusão, JWT) e
CT-IEX-010 (`meta_mes` no resumo e no por-seguradora) — spec indicadores-executivos, RF-IEX-008, PA-023.

Dados sintéticos: o mesmo snapshot de `tests.py`. No mês 2026-09 (dia 1 a 22) o
universo padrão tem dois documentos com valor: 101 (ALLI × COND, 1000.50) e
102 (PORT × FIAN, 200.00) — valor fechado do mês 1200.50.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status

from indicadores.models import MetaMensal, Ramo, Seguradora
from indicadores.services import metas as servico_metas
from indicadores.tests import REF, URLS, Usuario, _ComCarga

URL_METAS = "/indicadores/metas/"


def meta(seguradora, ramo, valor, competencia=date(2026, 9, 1), usuario=None):
    return MetaMensal.objects.create(
        seguradora_id=seguradora, ramo_id=ramo, competencia=competencia, valor_meta=Decimal(valor),
        criado_por=usuario, atualizado_por=usuario,
    )


class MetasCrudTests(_ComCarga):
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

        resposta = self.put(criada["id"], ramo="FIAN", valor_meta="750000.00")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        linha = resposta.data["metas"][0]
        self.assertEqual((linha["id"], linha["seguradora"], linha["ramo"], linha["valor_meta"]),
                         (criada["id"], "ALLI", "FIAN", "750000.00"))
        self.assertEqual(MetaMensal.objects.count(), 1)  # não nasceu outra

    def test_put_recusa_chave_que_ja_tem_meta_e_404_para_id_inexistente(self):
        alli_cond = self.post().data["metas"][0]
        self.post(ramo="FIAN", valor_meta="300000.00")

        colisao = self.put(alli_cond["id"], ramo="FIAN")
        self.assertEqual(colisao.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(colisao.data["sucesso"])
        self.assertIn("já existe meta", colisao.data["erro"])
        self.assertEqual(MetaMensal.objects.get(pk=alli_cond["id"]).ramo_id, "COND")  # intacta

        self.assertEqual(self.put(999999).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.put(alli_cond["id"], valor_meta="0").status_code, status.HTTP_400_BAD_REQUEST)

    def test_cria_meta_e_devolve_a_linha(self):
        resposta = self.post()

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertTrue(resposta.data["sucesso"])
        self.assertEqual(len(resposta.data["metas"]), 1)
        linha = resposta.data["metas"][0]
        self.assertEqual(linha["seguradora"], "ALLI")
        self.assertEqual(linha["seguradora_nome"], "ALLIANZ SEGUROS")
        self.assertEqual(linha["ramo"], "COND")
        self.assertEqual(linha["ramo_nome"], "CONDOMINIO")
        self.assertEqual(linha["competencia"], "2026-09")
        self.assertEqual(linha["valor_meta"], "1000000.00")
        self.assertEqual(linha["atualizado_por"], "usr@t.com")  # sem nome completo cai no e-mail
        self.assertIsNotNone(linha["atualizado_em"])
        gravada = MetaMensal.objects.get(pk=linha["id"])
        self.assertEqual(gravada.competencia, date(2026, 9, 1))
        self.assertEqual((gravada.criado_por, gravada.atualizado_por), (self.usuario, self.usuario))

    def test_upsert_na_mesma_chave_atualiza_em_vez_de_duplicar(self):
        primeira = self.post().data["metas"][0]
        outro = Usuario.objects.create_user(email="outro@t.com", password="x", nivel_acesso="ti", nome_completo="Fulano de Tal")
        self.client.force_authenticate(outro)

        segunda = self.post(valor_meta="1500000").data["metas"][0]

        self.assertEqual(MetaMensal.objects.count(), 1)
        self.assertEqual(segunda["id"], primeira["id"])
        self.assertEqual(segunda["valor_meta"], "1500000.00")
        self.assertEqual(segunda["atualizado_por"], "Fulano de Tal")
        gravada = MetaMensal.objects.get()
        self.assertEqual(gravada.criado_por, self.usuario)  # quem criou não muda
        self.assertEqual(gravada.atualizado_por, outro)

    def test_replicar_meses_cria_os_seguintes_virando_o_ano(self):
        resposta = self.post(competencia="2026-11", replicar_meses=3)

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual([m["competencia"] for m in resposta.data["metas"]], ["2026-11", "2026-12", "2027-01", "2027-02"])
        self.assertTrue(all(m["valor_meta"] == "1000000.00" for m in resposta.data["metas"]))
        self.assertEqual(MetaMensal.objects.count(), 4)
        self.assertEqual(MetaMensal.objects.filter(competencia=date(2027, 1, 1)).count(), 1)
        # Replicar de novo sobre meses já existentes atualiza, não duplica.
        self.post(competencia="2026-12", valor_meta="7", replicar_meses=1)
        self.assertEqual(MetaMensal.objects.count(), 4)
        self.assertEqual(str(MetaMensal.objects.get(competencia=date(2027, 1, 1)).valor_meta), "7.00")

    def test_somar_meses_e_competencia(self):
        self.assertEqual(servico_metas.somar_meses(date(2026, 12, 1), 1), date(2027, 1, 1))
        self.assertEqual(servico_metas.somar_meses(date(2026, 9, 1), 11), date(2027, 8, 1))
        self.assertEqual(servico_metas.competencia_de("2026-09"), date(2026, 9, 1))
        with self.assertRaises(ValueError):
            servico_metas.competencia_de("2026-9")

    def test_entradas_invalidas_dao_400(self):
        casos = (
            {"seguradora": "XXXX"}, {"ramo": "NADA"}, {"valor_meta": "0"}, {"valor_meta": "-5"},
            {"valor_meta": "abc"}, {"competencia": "09/2026"}, {"competencia": "2026-13"},
            {"replicar_meses": 12}, {"replicar_meses": -1},
        )
        for corpo in casos:
            resposta = self.post(**corpo)
            self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST, corpo)
            self.assertFalse(resposta.data["sucesso"])
            self.assertIn("erro", resposta.data)
        self.assertEqual(MetaMensal.objects.count(), 0)
        self.assertIn("seguradora", self.post(seguradora="XXXX").data["erro"])
        self.assertIn("maior que zero", self.post(valor_meta="0").data["erro"])

    def test_lista_por_competencia_ordenada_com_total(self):
        meta("PORT", "FIAN", "500.00")
        meta("ALLI", "COND", "1000000.00")
        meta("ALLI", "FIAN", "250.00", competencia=date(2026, 10, 1))

        resposta = self.client.get(URL_METAS, {"competencia": "2026-09"})

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["competencia"], "2026-09")
        self.assertEqual([(m["seguradora"], m["ramo"]) for m in resposta.data["metas"]], [("ALLI", "COND"), ("PORT", "FIAN")])
        self.assertEqual(resposta.data["total_meta"], "1000500.00")
        self.assertIsNone(resposta.data["metas"][0]["atualizado_por"])

        outubro = self.client.get(URL_METAS, {"competencia": "2026-10"}).data
        self.assertEqual(outubro["total_meta"], "250.00")
        vazio = self.client.get(URL_METAS, {"competencia": "2026-08"}).data
        self.assertEqual(vazio["metas"], [])
        self.assertIsNone(vazio["total_meta"])
        self.assertEqual(self.client.get(URL_METAS, {"competencia": "set/26"}).status_code, status.HTTP_400_BAD_REQUEST)

    def test_lista_sem_competencia_usa_o_mes_corrente_local(self):
        # 23h30 de 30/09 em São Paulo ainda é setembro; em UTC já é 1º de outubro.
        from datetime import datetime, timezone as tz_utc

        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 1, 2, 30, tzinfo=tz_utc.utc)):
            resposta = self.client.get(URL_METAS)
        self.assertEqual(resposta.data["competencia"], "2026-09")

    def test_apaga_meta_e_404_quando_nao_existe(self):
        criada = meta("ALLI", "COND", "10.00")

        resposta = self.client.delete(f"{URL_METAS}{criada.pk}/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, {"sucesso": True})
        self.assertEqual(MetaMensal.objects.count(), 0)
        de_novo = self.client.delete(f"{URL_METAS}{criada.pk}/")
        self.assertEqual(de_novo.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(de_novo.data["sucesso"])

    def test_sem_jwt_401_em_listar_gravar_e_apagar(self):
        criada = meta("ALLI", "COND", "10.00")
        self.client.force_authenticate(None)

        self.assertEqual(self.client.get(URL_METAS).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.post().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.delete(f"{URL_METAS}{criada.pk}/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(MetaMensal.objects.count(), 1)

    def test_seguradora_com_meta_nao_pode_ser_apagada(self):
        from django.db.models import ProtectedError

        meta("TOKI", "AUTO", "10.00")
        with self.assertRaises(ProtectedError):
            Seguradora.objects.get(sigla="TOKI").delete()
        with self.assertRaises(ProtectedError):
            Ramo.objects.get(abreviatura="AUTO").delete()


class MetaMesTests(_ComCarga):
    """CT-IEX-010: `meta_mes` do resumo e colunas de meta no por-seguradora."""

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
        self.assertEqual(bloco["realizado"], "1200.50")
        self.assertEqual(bloco["documentos_com_valor"], 2)
        self.assertIsNone(bloco["falta"])
        self.assertIsNone(bloco["percentual"])
        self.assertEqual(bloco["projecao"], "1637.05")  # 1200.50 / 22 × 30
        self.assertEqual(bloco["metas_consideradas"], 0)

    def test_meta_soma_conforme_o_filtro(self):
        meta("ALLI", "COND", "1000000.00")
        meta("PORT", "FIAN", "500.00")
        meta("TOKI", "AUTO", "100.00")
        meta("ALLI", "COND", "999.00", competencia=date(2026, 8, 1))  # outro mês: fora

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
        meta("ALLI", "COND", "2000.00")
        for periodo in ("semana", "hoje", "ano", "mes"):
            resposta = self.get("resumo", periodo=periodo).data
            # Com meta cadastrada, o realizado é só do par com meta (ALLI × COND), não da carteira inteira.
            self.assertEqual(resposta["meta_mes"]["realizado"], "1000.50", periodo)
            self.assertEqual(resposta["meta_mes"]["meta"], "2000.00", periodo)
        # O cartão do período, por sua vez, continua respeitando o período: na semana 21..22 não há valor.
        self.assertIsNone(self.get("resumo", periodo="semana").data["atual"]["valor_fechado"])
        # Referência em outro mês muda a competência e os dias.
        outubro = self.meta_mes(data_referencia="2026-10-05")
        self.assertEqual((outubro["competencia"], outubro["dias_no_mes"], outubro["dias_decorridos"]), ("2026-10", 31, 5))
        self.assertIsNone(outubro["meta"])

    def test_falta_percentual_e_projecao(self):
        meta("ALLI", "COND", "2000.00")
        meta("PORT", "FIAN", "100.00")

        alli = self.meta_mes(seguradora="ALLI")
        self.assertEqual(alli["realizado"], "1000.50")
        self.assertEqual(alli["falta"], "999.50")
        self.assertEqual(alli["percentual"], 50.0)  # 50.025 arredonda para uma decimal
        self.assertIsInstance(alli["percentual"], float)
        self.assertEqual(alli["projecao"], "1364.32")  # 1000.50 / 22 × 30

        port = self.meta_mes(seguradora="PORT")
        self.assertEqual(port["realizado"], "200.00")
        self.assertEqual(port["percentual"], 200.0)  # pode passar de 100
        self.assertEqual(port["falta"], "0.00")  # max(meta − realizado, 0)

        geral = self.meta_mes()
        self.assertEqual((geral["meta"], geral["realizado"], geral["falta"]), ("2100.00", "1200.50", "899.50"))
        self.assertEqual(geral["percentual"], 57.2)

    def test_meta_sem_realizado_falta_e_a_meta_inteira(self):
        meta("TOKI", "AUTO", "100.00")

        toki = self.meta_mes(seguradora="TOKI")

        self.assertEqual(toki["meta"], "100.00")
        self.assertIsNone(toki["realizado"])
        self.assertEqual(toki["documentos_com_valor"], 0)
        self.assertEqual(toki["falta"], "100.00")
        self.assertEqual(toki["percentual"], 0.0)
        self.assertIsNone(toki["projecao"])

    def test_toggles_valem_para_o_realizado(self):
        from indicadores.models import Documento, Producao

        # 112 (tipdoc X, ALLI/COND, 11/09) ganha valor: só entra no realizado com todos_tipdoc.
        Documento.objects.create(producao=Producao.objects.get(nosnum=112), pretot=Decimal("50.00"), fonte="D")
        self.assertEqual(self.meta_mes()["realizado"], "1200.50")
        self.assertEqual(self.meta_mes(todos_tipdoc="true")["realizado"], "1250.50")

    def test_por_seguradora_traz_meta_realizado_e_percentual_e_inclui_quem_so_tem_meta(self):
        meta("ALLI", "COND", "2000.00")
        meta("TOKI", "AUTO", "100.00")

        dados = self.get("por_seguradora", periodo="hoje").data

        linhas = {l["seguradora"]: l for l in dados["linhas"]}
        # Hoje (22/09) só a PORT fechou; ALLI entra pelas não fechadas; TOKI entra só pela meta.
        self.assertEqual(set(linhas), {"PORT", "ALLI", "TOKI"})
        self.assertEqual((linhas["TOKI"]["fechados"], linhas["TOKI"]["nao_fechadas"]), (0, 0))
        self.assertEqual(linhas["TOKI"]["nome"], "TOKIO MARINE")
        self.assertEqual((linhas["TOKI"]["meta_mes"], linhas["TOKI"]["realizado_mes"], linhas["TOKI"]["percentual_meta"]), ("100.00", None, 0.0))
        self.assertEqual((linhas["ALLI"]["meta_mes"], linhas["ALLI"]["realizado_mes"], linhas["ALLI"]["percentual_meta"]), ("2000.00", "1000.50", 50.0))
        # PORT não tem meta: o realizado da meta não a considera (só pares com meta).
        self.assertEqual((linhas["PORT"]["meta_mes"], linhas["PORT"]["realizado_mes"], linhas["PORT"]["percentual_meta"]), (None, None, None))
        total = dados["total"]
        # Total: metas 2000 + 100; realizado só de ALLI × COND (1000.50) — TOKI × AUTO não tem valor.
        self.assertEqual((total["meta_mes"], total["realizado_mes"], total["percentual_meta"]), ("2100.00", "1000.50", 47.6))
        # As colunas do Bloco continuam as do período pedido (hoje).
        self.assertEqual(total["fechados"], 1)

    def test_por_seguradora_respeita_o_filtro_de_ramo_na_meta(self):
        meta("ALLI", "COND", "2000.00")
        meta("ALLI", "FIAN", "300.00")

        sem_filtro = {l["seguradora"]: l for l in self.get("por_seguradora").data["linhas"]}
        self.assertEqual(sem_filtro["ALLI"]["meta_mes"], "2300.00")
        so_fian = self.get("por_seguradora", ramo="FIAN").data
        linhas = {l["seguradora"]: l for l in so_fian["linhas"]}
        self.assertEqual(linhas["ALLI"]["meta_mes"], "300.00")
        self.assertIsNone(linhas["ALLI"]["realizado_mes"])  # ALLI não tem FIAN com valor no mês
        self.assertEqual(linhas["ALLI"]["percentual_meta"], 0.0)
        self.assertEqual(so_fian["total"]["meta_mes"], "300.00")
        # PORT × FIAN (102) tem valor, mas não tem meta: fica fora do realizado da meta.
        self.assertIsNone(so_fian["total"]["realizado_mes"])

    def test_sem_metas_por_seguradora_mantem_as_linhas_de_antes(self):
        dados = self.get("por_seguradora").data
        self.assertEqual([l["seguradora"] for l in dados["linhas"]], ["PORT", "ALLI", "TOKI"])
        for linha in dados["linhas"] + [dados["total"]]:
            self.assertIsNone(linha["meta_mes"])
            self.assertIsNone(linha["percentual_meta"])
        self.assertEqual(dados["total"]["realizado_mes"], "1200.50")
