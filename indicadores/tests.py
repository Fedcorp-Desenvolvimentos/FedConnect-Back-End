"""CT-IEX-001..008 — spec indicadores-executivos."""
import copy
import re
from datetime import date, datetime, timezone as tz_utc
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework import status
from rest_framework.test import APITestCase

from indicadores.models import CargaCorp, Cliente, Documento, DocumentoNegocio, Producao, Ramo, Seguradora
from indicadores.services import agregacao, carga as servico_carga, nao_fechadas
from indicadores.services.periodos import Filtros, ParametroInvalido, janela, janela_anterior
from indicadores.services.nao_fechadas import mascarar

Usuario = get_user_model()

REF = "2026-09-22"  # terça-feira; a semana é 21..22
URLS = {
    "dominios": "/indicadores/dominios/",
    "resumo": "/indicadores/resumo/",
    "por_seguradora": "/indicadores/por-seguradora/",
    "serie": "/indicadores/serie/",
    "nao_fechadas": "/indicadores/nao-fechadas/",
    "composicao": "/indicadores/composicao/",
}
COLUNAS = ["nosnum", "tipdoc", "seg", "ramo", "cli", "inivig", "fimvig", "datemi", "nosnum_ren", "cancelado", "renov_sit", "sin", "cliente"]

# CPFs/CNPJs fictícios evidentes (repetições e sequências), nunca dado real.
CLIENTES = {
    "1": ["00000000191", "F"], "2": ["00000000000191", "J"], "3": ["", "F"], "4": ["11111111111", "F"],
    "5": ["22222222222", "F"], "6": ["33333333333", "F"], "7": ["44444444444", "F"], "8": ["55555555555", "F"],
    "9": ["66666666666", "F"], "10": ["77777777777", "F"], "11": ["88888888888", "F"], "12": ["99999999999", "F"],
    "13": ["12312312312", "F"], "14": ["13113113113", "F"], "15": ["14114114114", "F"],
}


def doc(nosnum, tipdoc, seg, ramo, cli, inivig, fimvig, datemi, ren=0, cancelado=0, sit=1, sin=0):
    return [nosnum, tipdoc, seg, ramo, cli, inivig, fimvig, datemi, ren, cancelado, sit, sin, f"Cliente {cli}"]


def snapshot():
    return {
        "gerado_em": "2026-09-22 12:57",
        "extracao": "2026-09-22",
        "colunas": list(COLUNAS),
        "docs": [
            # cliente 1: primeira apólice (captação), renovada pela cadeia, e outra em outro ramo/seguradora (renovação por CPF)
            doc(100, "A", "ALLI", "COND", 1, "2025-09-01", "2026-09-01", "2025-08-25", sit=2),
            doc(101, "A", "ALLI", "COND", 1, "2026-09-01", "2027-09-01", "2026-09-02", ren=100),
            doc(102, "A", "PORT", "FIAN", 1, "2026-09-10", "2027-09-10", "2026-09-10"),
            # cliente 4: primeira apólice cancelada ainda conta como anterior
            doc(103, "A", "ALLI", "COND", 4, "2025-01-01", "2026-01-01", "2024-12-20", cancelado=1, sit=6),
            doc(104, "A", "ALLI", "COND", 4, "2026-09-05", "2027-09-05", "2026-09-05"),
            # cliente 5: empate de inivig resolvido por nosnum
            doc(105, "A", "PORT", "AUTO", 5, "2026-09-15", "2027-09-15", "2026-09-15"),
            doc(106, "A", "PORT", "AUTO", 5, "2026-09-15", "2027-09-15", "2026-09-15"),
            # cliente 3 sem CPF: só a cadeia nosnum_ren classifica
            doc(107, "A", "TOKI", "COND", 3, "2025-03-01", "2026-03-01", "2025-02-20"),
            doc(108, "A", "TOKI", "COND", 3, "2026-03-01", "2027-03-01", "2026-03-01"),
            doc(109, "A", "TOKI", "COND", 3, "2026-09-03", "2027-09-03", "2026-09-03", ren=108),
            # cliente desconhecido (999) e data de emissão inválida
            doc(110, "A", "ALLI", "COND", 999, "2026-09-08", "2027-09-08", "2026-09-08"),
            doc(111, "A", "ALLI", "COND", 2, "2026-09-09", "2027-09-09", "15/08/205"),
            # fora do universo padrão: tipdoc X e cancelado
            doc(112, "X", "ALLI", "COND", 2, "2026-09-11", "2027-09-11", "2026-09-11"),
            doc(113, "A", "PORT", "COND", 2, "2026-09-12", "2027-09-12", "2026-09-12", cancelado=1),
            # cortes: domingo antes da semana, hoje, segunda-feira, mês anterior, ano anterior
            doc(114, "A", "ALLI", "COND", 9, "2026-09-20", "2027-09-20", "2026-09-20"),
            doc(115, "A", "PORT", "FIAN", 9, "2026-09-22", "2027-09-22", "2026-09-22"),
            doc(116, "A", "TOKI", "AUTO", 10, "2026-09-21", "2027-09-21", "2026-09-21"),
            doc(117, "A", "ALLI", "COND", 11, "2026-08-10", "2027-08-10", "2026-08-10"),
            doc(118, "A", "ALLI", "COND", 12, "2026-08-25", "2027-08-25", "2026-08-25"),
            doc(119, "A", "ALLI", "COND", 13, "2025-05-05", "2026-05-05", "2025-05-05"),
            # não fechadas do mês 2026-09
            doc(120, "A", "ALLI", "COND", 6, "2025-09-10", "2026-09-10", "2025-09-05", sit=3),
            doc(121, "A", "PORT", "FIAN", 6, "2026-09-15", "2027-09-15", "2026-09-15"),  # mesmo CPF, outro ramo, na janela
            doc(122, "A", "ALLI", "COND", 7, "2025-09-05", "2026-09-05", "2025-09-01", sit=3),
            doc(123, "A", "ALLI", "COND", 7, "2026-11-20", "2027-11-20", "2026-11-15"),  # fora da janela e no futuro
            doc(124, "A", "ALLI", "COND", 8, "2025-09-15", "2026-09-15", "2025-09-10", sit=1),  # CORP diz vigente
            doc(125, "A", "PORT", "COND", 14, "2025-09-28", "2026-09-28", "2025-09-20", sit=1),  # a vencer
            doc(126, "A", "PORT", "COND", 15, "2025-09-20", "2026-09-20", "2025-09-15", sit=2, sin=3),  # sem nova apólice
        ],
        "clientes": copy.deepcopy(CLIENTES),
        "seguradoras": {"ALLI": "ALLIANZ SEGUROS", "PORT": "PORTO SEGURO", "TOKI": "TOKIO MARINE"},
        "ramos": {"COND": "CONDOMINIO", "FIAN": "FIANCA", "AUTO": "AUTOMOVEL"},
        "valores": {"101": [1000.50, 100.05, 900.45, "D"], "102": [200.0, None, 180.0, "R"]},
        "negocios": {"101": ["NEG-1", "2026-08-30"]},
        "fontes": {"producao": 27},
    }


def filtros(**kw):
    kw.setdefault("data_referencia", date.fromisoformat(REF))
    return Filtros(**kw)


class _ComCarga(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carga = servico_carga.carregar_snapshot(snapshot(), arquivo="sintetico.json")
        cls.usuario = Usuario.objects.create_user(email="usr@t.com", password="x", nivel_acesso="admin")
        cls.comum = Usuario.objects.create_user(email="comum@t.com", password="x", nivel_acesso="usuario")

    def setUp(self):
        self.client.force_authenticate(self.usuario)

    def get(self, nome, **params):
        params.setdefault("data_referencia", REF)
        return self.client.get(URLS[nome], params)


class CargaTests(APITestCase):
    """CT-IEX-001: contagens, rejeitos nomeados, datas inválidas, CargaCorp, idempotência."""

    def test_carga_grava_tudo_e_registra_contagens_e_rejeitos(self):
        carga = servico_carga.carregar_snapshot(snapshot(), arquivo="sintetico.json")

        self.assertTrue(carga.sucesso)
        self.assertEqual(carga.origem, CargaCorp.ORIGEM_SNAPSHOT)
        self.assertEqual(carga.extraido_em, date(2026, 9, 22))
        self.assertEqual(carga.gerado_em, "2026-09-22 12:57")
        self.assertIsNotNone(carga.concluida_em)
        self.assertIsNotNone(carga.duracao_ms)
        self.assertEqual(Cliente.objects.count(), 15)
        self.assertEqual(Ramo.objects.count(), 3)
        self.assertEqual(Seguradora.objects.count(), 3)
        self.assertEqual(Producao.objects.count(), 27)
        self.assertEqual(Documento.objects.count(), 2)
        self.assertEqual(DocumentoNegocio.objects.count(), 1)
        self.assertEqual(carga.contagens["producao"], 27)
        self.assertEqual(carga.contagens["producao_sem_datemi"], 1)
        self.assertEqual(carga.rejeitos["cliente_desconhecido"], 1)
        self.assertEqual(carga.rejeitos["datemi_invalida"], 1)
        self.assertEqual(carga.rejeitos["ramo_desconhecido"], 0)
        self.assertEqual(carga.rejeitos["seguradora_desconhecida"], 0)

    def test_cliente_desconhecido_fica_nulo_e_data_invalida_guarda_o_texto(self):
        servico_carga.carregar_snapshot(snapshot())

        sem_cliente = Producao.objects.get(nosnum=110)
        self.assertIsNone(sem_cliente.cliente)
        self.assertEqual(sem_cliente.cliente_nome, "Cliente 999")
        invalida = Producao.objects.get(nosnum=111)
        self.assertIsNone(invalida.datemi)
        self.assertEqual(invalida.datemi_bruta, "15/08/205")
        self.assertEqual(Producao.objects.get(nosnum=101).datemi_bruta, "")
        # Nome do cliente vem da produção; CPF e pessoa do mapa `clientes`.
        cliente = Cliente.objects.get(codigo=1)
        self.assertEqual((cliente.nome, cliente.cpf_cnpj, cliente.pessoa), ("Cliente 1", "00000000191", "F"))

    def test_valores_e_negocios_ligados_por_nosnum_com_decimal(self):
        servico_carga.carregar_snapshot(snapshot())

        documento = Documento.objects.get(pk=101)
        self.assertEqual(str(documento.pretot), "1000.50")
        self.assertEqual(str(documento.val_c), "100.05")
        self.assertEqual(documento.fonte, "D")
        self.assertIsNone(Documento.objects.get(pk=102).val_c)
        negocio = DocumentoNegocio.objects.get(pk=101)
        self.assertEqual((negocio.codigo_negocio, negocio.datinc_negocio), ("NEG-1", date(2026, 8, 30)))

    def test_segunda_carga_nao_duplica_e_aponta_a_carga_nova(self):
        primeira = servico_carga.carregar_snapshot(snapshot())
        segunda = servico_carga.carregar_snapshot(snapshot())

        self.assertEqual(Producao.objects.count(), 27)
        self.assertEqual(Cliente.objects.count(), 15)
        self.assertEqual(Documento.objects.count(), 2)
        self.assertEqual(primeira.contagens, segunda.contagens)
        self.assertEqual(CargaCorp.objects.count(), 2)
        self.assertTrue(all(p.carga_id == segunda.pk for p in Producao.objects.all()))  # INV-IEX-004

    def test_contrato_quebrado_registra_falha_e_levanta(self):
        dados = snapshot()
        del dados["docs"]

        with self.assertRaises(servico_carga.SnapshotInvalido) as contexto:
            servico_carga.carregar_snapshot(dados)

        self.assertIn("docs", str(contexto.exception))
        falha = CargaCorp.objects.get()
        self.assertFalse(falha.sucesso)
        self.assertIn("docs", falha.erro)
        self.assertEqual(Producao.objects.count(), 0)

    def test_coluna_ausente_e_recusada(self):
        dados = snapshot()
        dados["colunas"].remove("datemi")

        with self.assertRaises(servico_carga.SnapshotInvalido) as contexto:
            servico_carga.carregar_snapshot(dados)
        self.assertIn("datemi", str(contexto.exception))

    def test_comando_com_arquivo_inexistente_da_command_error(self):
        with self.assertRaises(CommandError) as contexto:
            call_command("carregar_snapshot_corp", "nao-existe.json")
        self.assertIn("não encontrado", str(contexto.exception))
        self.assertFalse(CargaCorp.objects.get().sucesso)

    def test_comando_carrega_arquivo_e_resume(self):
        import json
        import tempfile
        from io import StringIO

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as arquivo:
            json.dump(snapshot(), arquivo)
        saida = StringIO()
        call_command("carregar_snapshot_corp", arquivo.name, stdout=saida)

        self.assertIn("concluída", saida.getvalue())
        self.assertIn("producao: 27", saida.getvalue())
        self.assertIn("cliente_desconhecido: 1", saida.getvalue())
        self.assertEqual(Producao.objects.count(), 27)


class RenovacaoTests(_ComCarga):
    """CT-IEX-002: regra de renovação do gestor, persistida na carga."""

    def renovacao(self, nosnum):
        return Producao.objects.get(nosnum=nosnum).renovacao

    def test_cadeia_nosnum_ren(self):
        self.assertTrue(self.renovacao(101))

    def test_mesmo_cpf_com_apolice_anterior_em_outro_ramo_e_seguradora(self):
        self.assertTrue(self.renovacao(102))

    def test_apolice_anterior_cancelada_ainda_conta(self):
        self.assertTrue(self.renovacao(104))

    def test_empate_de_inivig_resolvido_por_nosnum(self):
        self.assertFalse(self.renovacao(105))
        self.assertTrue(self.renovacao(106))

    def test_cliente_sem_cpf_so_pela_cadeia(self):
        self.assertFalse(self.renovacao(107))
        self.assertFalse(self.renovacao(108))  # anterior existe, mas sem CPF não liga
        self.assertTrue(self.renovacao(109))

    def test_primeira_apolice_do_cpf_e_captacao(self):
        self.assertFalse(self.renovacao(100))
        self.assertFalse(self.renovacao(114))
        self.assertFalse(self.renovacao(110))  # cliente desconhecido, sem cadeia

    def test_recarga_mantem_a_classificacao(self):
        servico_carga.carregar_snapshot(snapshot())
        self.assertTrue(self.renovacao(102))
        self.assertFalse(self.renovacao(105))


class PeriodosTests(APITestCase):
    """CT-IEX-003 (parte pura): janelas e janelas anteriores."""

    def test_janelas_da_referencia(self):
        ref = date(2026, 9, 22)
        self.assertEqual(janela("hoje", ref), (ref, ref))
        self.assertEqual(janela("semana", ref), (date(2026, 9, 21), ref))
        self.assertEqual(janela("mes", ref), (date(2026, 9, 1), ref))
        self.assertEqual(janela("ano", ref), (date(2026, 1, 1), ref))

    def test_janelas_anteriores(self):
        ref = date(2026, 9, 22)
        self.assertEqual(janela_anterior("hoje", ref), (date(2026, 9, 21), date(2026, 9, 21)))
        self.assertEqual(janela_anterior("semana", ref), (date(2026, 9, 14), date(2026, 9, 15)))
        self.assertEqual(janela_anterior("mes", ref), (date(2026, 8, 1), date(2026, 8, 22)))
        self.assertEqual(janela_anterior("ano", ref), (date(2025, 1, 1), date(2025, 9, 22)))
        # Dia limitado ao último do mês anterior; janeiro volta para dezembro.
        self.assertEqual(janela_anterior("mes", date(2026, 3, 31)), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(janela_anterior("mes", date(2026, 1, 15)), (date(2025, 12, 1), date(2025, 12, 15)))
        self.assertEqual(janela_anterior("ano", date(2028, 2, 29)), (date(2027, 1, 1), date(2027, 2, 28)))
        self.assertEqual(
            janela_anterior("faixa", ref, date(2026, 9, 10), date(2026, 9, 19)), (date(2026, 8, 31), date(2026, 9, 9))
        )

    def test_faixa_invertida_e_trocada_e_sem_datas_e_recusada(self):
        f = filtros(periodo="faixa", data_ini=date(2026, 9, 19), data_fim=date(2026, 9, 10))
        self.assertEqual(f.janela, (date(2026, 9, 10), date(2026, 9, 19)))
        with self.assertRaises(ParametroInvalido):
            filtros(periodo="faixa")
        with self.assertRaises(ParametroInvalido):
            filtros(janela_dias=181)


class ResumoTests(_ComCarga):
    """CT-IEX-003: universo padrão, toggles, períodos, cobertura, dados_parciais, domínios."""

    def test_resumo_do_mes_com_universo_padrao(self):
        resposta = self.get("resumo", periodo="mes")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertTrue(resposta.data["sucesso"])
        atual = resposta.data["atual"]
        self.assertEqual(atual["fechados"], 11)
        self.assertEqual(atual["renovacoes"], 7)
        self.assertEqual(atual["captacoes"], 4)
        self.assertEqual(atual["com_negocio_origem"], 1)
        self.assertEqual(atual["valor_fechado"], "1200.50")
        self.assertEqual(atual["documentos_com_valor"], 2)
        self.assertEqual(atual["comissao"], "100.05")
        self.assertEqual(atual["documentos_com_comissao"], 1)
        self.assertEqual(resposta.data["filtros"]["periodo_ini"], "2026-09-01")
        self.assertEqual(resposta.data["filtros"]["periodo_fim"], REF)
        self.assertEqual(resposta.data["filtros"]["anterior_ini"], "2026-08-01")
        self.assertEqual(resposta.data["filtros"]["anterior_fim"], "2026-08-22")
        self.assertFalse(resposta.data["dados_parciais"])

    def test_toggles_incluem_tipdoc_x_e_cancelados(self):
        self.assertEqual(self.get("resumo", todos_tipdoc="true").data["atual"]["fechados"], 12)
        self.assertEqual(self.get("resumo", incluir_cancelados="true").data["atual"]["fechados"], 12)
        self.assertEqual(
            self.get("resumo", incluir_cancelados="true", todos_tipdoc="true").data["atual"]["fechados"], 13
        )

    def test_periodos_hoje_semana_mes_ano_e_anterior(self):
        periodos = self.get("resumo").data["periodos"]

        self.assertEqual(periodos["hoje"]["fechados"], 1)
        self.assertEqual(periodos["semana"]["fechados"], 2)  # segunda 21 e terça 22; domingo 20 fica fora
        self.assertEqual(periodos["mes"]["fechados"], 11)
        self.assertEqual(periodos["ano"]["fechados"], 14)
        self.assertEqual(self.get("resumo", periodo="mes").data["anterior"]["fechados"], 1)  # 2026-08-10; 25/08 fora
        self.assertEqual(self.get("resumo", periodo="hoje").data["anterior"]["fechados"], 1)  # 21/09
        self.assertEqual(self.get("resumo", periodo="semana").data["anterior"]["fechados"], 3)  # 14..15/09

    def test_faixa_e_filtros_de_ramo_e_seguradora(self):
        faixa = self.get("resumo", periodo="faixa", data_ini="2026-09-15", data_fim="2026-09-01").data
        self.assertEqual(faixa["filtros"]["periodo_ini"], "2026-09-01")
        self.assertEqual(faixa["atual"]["fechados"], 8)

        resposta = self.client.get(URLS["resumo"] + f"?data_referencia={REF}&seguradora=PORT&ramo=FIAN&ramo=AUTO")
        self.assertEqual(resposta.data["atual"]["fechados"], 5)
        self.assertEqual(resposta.data["filtros"]["ramos"], ["FIAN", "AUTO"])

    def test_sem_valor_no_periodo_vem_null_e_nao_zero(self):
        hoje = self.get("resumo", periodo="hoje").data["atual"]
        self.assertEqual(hoje["fechados"], 1)
        self.assertIsNone(hoje["valor_fechado"])
        self.assertEqual(hoje["documentos_com_valor"], 0)
        self.assertIsNone(hoje["comissao"])

    def test_dados_parciais_quando_referencia_depois_da_extracao(self):
        self.assertTrue(self.get("resumo", data_referencia="2026-09-25").data["dados_parciais"])
        self.assertFalse(self.get("resumo", data_referencia="2026-09-22").data["dados_parciais"])

    def test_parametros_invalidos_dao_400(self):
        casos = (
            {"periodo": "trimestre"}, {"periodo": "faixa"}, {"janela_dias": "200"},
            {"data_referencia": "22/09/2026"}, {"incluir_cancelados": "talvez"},
        )
        for params in casos:
            resposta = self.get("resumo", **params)
            self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST, params)
            self.assertFalse(resposta.data["sucesso"])
            self.assertIn("erro", resposta.data)

    def test_dominios_com_contadores_cruzados_e_metadados(self):
        resposta = self.get("dominios", seguradora="PORT")

        dados = resposta.data
        self.assertEqual(dados["extraido_em"], "2026-09-22")
        self.assertEqual(dados["gerado_em"], "2026-09-22 12:57")
        self.assertEqual(dados["total_documentos"], 27)
        self.assertEqual(dados["documentos_sem_datemi"], 1)
        self.assertEqual(dados["carga"]["origem"], "snapshot")
        self.assertEqual(dados["carga"]["rejeitos"]["cliente_desconhecido"], 1)
        ramos = {r["sigla"]: r for r in dados["ramos"]}
        # total_base decrescente; FIAN e AUTO empatam (3) e desempatam por sigla.
        self.assertEqual([r["sigla"] for r in dados["ramos"]], ["COND", "AUTO", "FIAN"])
        self.assertEqual(ramos["COND"]["total_base"], 21)
        # O contador de ramo respeita a seguradora escolhida (PORT): FIAN 102, 115, 121; COND só o cancelado.
        self.assertEqual(ramos["FIAN"]["fechados_periodo"], 3)
        self.assertEqual(ramos["AUTO"]["fechados_periodo"], 2)
        self.assertEqual(ramos["COND"]["fechados_periodo"], 0)
        # E vice-versa: sem filtro de ramo, a seguradora conta tudo dela.
        seguradoras = {s["sigla"]: s for s in dados["seguradoras"]}
        self.assertEqual(seguradoras["PORT"]["fechados_periodo"], 5)
        self.assertEqual(seguradoras["ALLI"]["fechados_periodo"], 4)
        por_ramo = {s["sigla"]: s for s in self.get("dominios", ramo="FIAN").data["seguradoras"]}
        self.assertEqual((por_ramo["PORT"]["fechados_periodo"], por_ramo["ALLI"]["fechados_periodo"]), (3, 0))

    def test_base_vazia_responde_200_com_blocos_zerados(self):
        Producao.objects.all().delete()
        CargaCorp.objects.all().delete()

        resumo = self.get("resumo")
        dominios = self.get("dominios")

        self.assertEqual(resumo.status_code, status.HTTP_200_OK)
        self.assertEqual(resumo.data["atual"]["fechados"], 0)
        self.assertIsNone(resumo.data["atual"]["valor_fechado"])
        self.assertIsNone(dominios.data["extraido_em"])
        self.assertIsNone(dominios.data["carga"])
        self.assertEqual(dominios.data["total_documentos"], 0)

    def test_resposta_do_resumo_em_menos_de_dois_segundos(self):
        import time

        inicio = time.monotonic()
        for nome in URLS:
            self.assertEqual(self.get(nome).status_code, status.HTTP_200_OK, nome)
        self.assertLess(time.monotonic() - inicio, 2.0 * len(URLS))


class PorSeguradoraTests(_ComCarga):
    """CT-IEX-004: soma das linhas = total; fechados = renovacoes + captacoes; ordem."""

    def test_linhas_e_total(self):
        dados = self.get("por_seguradora").data

        linhas = dados["linhas"]
        total = dados["total"]
        self.assertEqual([l["seguradora"] for l in linhas], ["PORT", "ALLI", "TOKI"])
        self.assertEqual(linhas[0]["nome"], "PORTO SEGURO")
        for chave in ("fechados", "renovacoes", "captacoes", "com_negocio_origem", "documentos_com_valor", "nao_fechadas"):
            self.assertEqual(sum(l[chave] for l in linhas), total[chave], chave)
        for linha in linhas + [total]:
            self.assertEqual(linha["fechados"], linha["renovacoes"] + linha["captacoes"])  # INV-IEX-001
        self.assertEqual(total["fechados"], 11)
        self.assertEqual(total["valor_fechado"], "1200.50")
        self.assertEqual({l["seguradora"]: l["nao_fechadas"] for l in linhas}, {"ALLI": 1, "PORT": 1, "TOKI": 0})
        self.assertEqual({l["seguradora"]: l["valor_fechado"] for l in linhas}, {"ALLI": "1000.50", "PORT": "200.00", "TOKI": None})

    def test_seguradora_sem_fechados_entra_se_tem_nao_fechadas(self):
        dados = self.get("por_seguradora", periodo="hoje").data

        self.assertEqual({l["seguradora"]: l["fechados"] for l in dados["linhas"]}, {"PORT": 1, "ALLI": 0})
        self.assertEqual(dados["total"]["nao_fechadas"], 2)


class SerieTests(_ComCarga):
    """CT-IEX-005: 30 dias, 12 meses com futuro, fuso local."""

    def test_serie_por_dia(self):
        dados = self.get("serie", tipo="dia").data

        pontos = dados["pontos"]
        self.assertEqual(len(pontos), 30)
        self.assertEqual(pontos[0]["periodo"], "2026-08-24")
        self.assertEqual(pontos[-1]["periodo"], REF)
        self.assertEqual(pontos[-1]["rotulo"], "22/09")
        self.assertEqual(pontos[-1]["fechados"], 1)
        self.assertEqual(pontos[-2]["fechados"], 1)  # 21/09
        por_dia = {p["periodo"]: p for p in pontos}
        self.assertEqual(por_dia["2026-09-15"]["fechados"], 3)  # 105, 106, 121
        self.assertEqual(por_dia["2026-09-15"]["renovacoes"], 2)
        self.assertEqual(por_dia["2026-08-25"]["fechados"], 1)
        self.assertEqual(sum(p["fechados"] for p in pontos), 12)  # mês (11) + 25/08

    def test_serie_por_mes_com_futuro_marcado(self):
        dados = self.get("serie", tipo="mes").data

        self.assertEqual(dados["ano"], 2026)
        pontos = dados["pontos"]
        self.assertEqual(len(pontos), 12)
        self.assertEqual([p["futuro"] for p in pontos], [False] * 9 + [True] * 3)
        por_mes = {p["periodo"]: p for p in pontos}
        self.assertEqual(por_mes["2026-09"]["fechados"], 11)
        self.assertEqual(por_mes["2026-09"]["valor_fechado"], "1200.50")
        self.assertEqual(por_mes["2026-08"]["fechados"], 2)
        self.assertEqual(por_mes["2026-03"]["fechados"], 1)
        self.assertEqual(por_mes["2026-03"]["rotulo"], "mar")
        self.assertEqual(por_mes["2026-11"]["fechados"], 0)  # 123 emitida em 15/11, futuro: zerada
        self.assertEqual(por_mes["2026-01"]["fechados"], 0)

    def test_tipo_invalido_da_400(self):
        self.assertEqual(self.get("serie", tipo="semana").status_code, status.HTTP_400_BAD_REQUEST)

    def test_referencia_padrao_usa_o_dia_local_nao_utc(self):
        # 23h30 de 22/09 em São Paulo = 02h30 de 23/09 em UTC: a referência tem de ser 22/09.
        with patch("django.utils.timezone.now", return_value=datetime(2026, 9, 23, 2, 30, tzinfo=tz_utc.utc)):
            resposta = self.client.get(URLS["resumo"], {"periodo": "hoje"})

        self.assertEqual(resposta.data["filtros"]["data_referencia"], "2026-09-22")
        self.assertEqual(resposta.data["atual"]["fechados"], 1)


class NaoFechadasTests(_ComCarga):
    """CT-IEX-006: janela, nova apólice por cadeia e por CPF, situação CORP, mascaramento, corte."""

    def test_resumo_do_mes(self):
        dados = self.get("nao_fechadas").data

        self.assertEqual(dados["mes"], "2026-09")
        self.assertEqual(dados["janela_dias"], 30)
        resumo = dados["resumo"]
        self.assertEqual(resumo["vencem_no_mes"], 6)
        self.assertEqual(resumo["vencidas"], 5)
        self.assertEqual(resumo["vencidas_decididas"], 4)
        self.assertEqual(resumo["vencidas_ainda_vigentes"], 1)
        self.assertEqual(resumo["vencidas_sem_nova_apolice"], 2)
        self.assertEqual(resumo["a_vencer"], 1)
        self.assertEqual(
            {c["situacao"]: c["quantidade"] for c in resumo["corp_diz"]}, {1: 1, 2: 2, 3: 2}
        )
        self.assertEqual({c["situacao"]: c["rotulo"] for c in resumo["corp_diz"]}[3], "não renovada")

    def test_listas_fechadas_por_cadeia_e_por_cpf_e_nao_fechadas(self):
        dados = self.get("nao_fechadas").data

        vencidas = {l["nosnum"]: l for l in dados["vencidas"]["linhas"]}
        self.assertEqual(dados["vencidas"]["total"], 4)
        self.assertEqual(set(vencidas), {100, 120, 122, 126})
        self.assertNotIn(124, vencidas)  # renovacao_situacao = 1 fica fora das decididas
        self.assertTrue(vencidas[100]["fechada"])
        # 101 pela cadeia; 102 (mesmo CPF, outro ramo, inivig 10/09) também cai na janela de 01/09 ± 30.
        self.assertEqual([n["nosnum"] for n in vencidas[100]["novas_apolices"]], [101, 102])
        self.assertTrue(vencidas[120]["fechada"])  # mesmo CPF, outro ramo (FIAN/PORT), inivig dentro da janela
        self.assertEqual(vencidas[120]["novas_apolices"][0], {"nosnum": 121, "seguradora": "PORT", "seguradora_nome": "PORTO SEGURO"})
        self.assertFalse(vencidas[122]["fechada"])  # nova apólice só em novembro: fora da janela
        self.assertFalse(vencidas[126]["fechada"])
        # Não fechadas primeiro, depois fimvig crescente.
        self.assertEqual([l["nosnum"] for l in dados["vencidas"]["linhas"]], [122, 126, 100, 120])
        self.assertEqual([l["nosnum"] for l in dados["a_vencer"]["linhas"]], [125])
        linha = vencidas[126]
        self.assertEqual(linha["renovacao_situacao_rotulo"], "renovada")
        self.assertEqual(linha["sin_situacao"], 3)
        self.assertEqual(linha["seguradora_nome"], "PORTO SEGURO")
        self.assertEqual(linha["ramo"], "COND")
        self.assertEqual(linha["cliente"], "Cliente 15")

    def test_janela_maior_fecha_a_de_novembro(self):
        dados = self.get("nao_fechadas", janela_dias="90").data
        vencidas = {l["nosnum"]: l for l in dados["vencidas"]["linhas"]}
        self.assertTrue(vencidas[122]["fechada"])
        self.assertEqual(dados["resumo"]["vencidas_sem_nova_apolice"], 1)

    def test_cpf_mascarado_e_cnpj_completo(self):
        self.assertEqual(mascarar("00000000191", "F"), "***.000.001-**")
        self.assertEqual(mascarar("000.000.001-91", "F"), "***.000.001-**")
        self.assertEqual(mascarar("00000000000191", "J"), "00.000.000/0001-91")
        self.assertEqual(mascarar("", "F"), "")
        self.assertEqual(mascarar("123", "F"), "123")
        linhas = self.get("nao_fechadas").data["vencidas"]["linhas"]
        self.assertEqual({l["nosnum"]: l["cpf_cnpj"] for l in linhas}[126], "***.141.141-**")

    def test_filtro_de_seguradora_restringe_as_vencidas_mas_nao_a_busca_da_nova_apolice(self):
        dados = self.get("nao_fechadas", seguradora="ALLI").data
        vencidas = {l["nosnum"]: l for l in dados["vencidas"]["linhas"]}
        self.assertEqual(set(vencidas), {100, 120, 122})
        self.assertTrue(vencidas[120]["fechada"])  # a nova é da PORT e continua contando

    def test_corte_em_400(self):
        seg = Seguradora.objects.get(sigla="ALLI")
        Producao.objects.bulk_create(
            Producao(
                nosnum=10000 + i, tipdoc="A", seguradora=seg, cliente_nome=f"Cliente massa {i}",
                inivig=date(2025, 9, 3), fimvig=date(2026, 9, 3), datemi=date(2025, 9, 1), renovacao_situacao=3,
            )
            for i in range(450)
        )

        dados = self.get("nao_fechadas").data

        self.assertEqual(dados["vencidas"]["total"], 454)
        self.assertEqual(dados["vencidas"]["exibidas"], 400)
        self.assertEqual(len(dados["vencidas"]["linhas"]), 400)
        self.assertEqual(dados["resumo"]["vencidas_sem_nova_apolice"], 452)


class ComposicaoTests(_ComCarga):
    """CT-IEX-007: as listas batem com os cartões (INV-IEX-005)."""

    def test_totais_iguais_aos_cartoes(self):
        resumo = self.get("resumo").data["atual"]
        nf = self.get("nao_fechadas").data["resumo"]
        composicao = self.get("composicao").data

        self.assertEqual(composicao["captacoes"]["total"], resumo["captacoes"])
        self.assertEqual(composicao["renovacoes"]["total"], resumo["renovacoes"])
        self.assertEqual(composicao["vencidas_sem_nova_apolice"]["total"], nf["vencidas_sem_nova_apolice"])
        self.assertEqual(composicao["captacoes"]["exibidas"], len(composicao["captacoes"]["linhas"]))

    def test_ordem_e_campos_das_linhas(self):
        composicao = self.get("composicao").data

        captacoes = composicao["captacoes"]["linhas"]
        self.assertEqual([l["nosnum"] for l in captacoes], [116, 114, 105, 110])  # datemi decrescente
        self.assertEqual(captacoes[0], {
            "nosnum": 116, "cliente": "Cliente 10", "seguradora": "TOKI", "seguradora_nome": "TOKIO MARINE",
            "ramo": "AUTO", "data": "2026-09-21",
        })
        vencidas = composicao["vencidas_sem_nova_apolice"]["linhas"]
        self.assertEqual([l["nosnum"] for l in vencidas], [126, 122])  # fimvig decrescente
        self.assertEqual(vencidas[0]["data"], "2026-09-20")

    def test_composicao_respeita_os_mesmos_filtros(self):
        resumo = self.get("resumo", seguradora="PORT", todos_tipdoc="true").data["atual"]
        composicao = self.get("composicao", seguradora="PORT", todos_tipdoc="true").data
        self.assertEqual(composicao["renovacoes"]["total"], resumo["renovacoes"])
        self.assertEqual(composicao["captacoes"]["total"], resumo["captacoes"])


class SegurancaTests(_ComCarga):
    """CT-IEX-008: sem JWT → 401; `usuario` comum → 403; `admin` e `ti` → 200; nenhum CPF completo na resposta."""

    def test_sem_login_401_em_todas_as_rotas(self):
        self.client.force_authenticate(None)
        for nome in URLS:
            self.assertEqual(self.get(nome).status_code, status.HTTP_401_UNAUTHORIZED, nome)

    def test_usuario_comum_403_em_todas_as_rotas(self):
        self.client.force_authenticate(self.comum)
        for nome in URLS:
            self.assertEqual(self.get(nome).status_code, status.HTTP_403_FORBIDDEN, nome)

    def test_admin_le_todas_as_rotas(self):
        for nome in URLS:
            resposta = self.get(nome)
            self.assertEqual(resposta.status_code, status.HTTP_200_OK, nome)

    def test_ti_le_todas_as_rotas(self):
        ti = Usuario.objects.create_user(email="ti@t.com", password="x", nivel_acesso="ti")
        self.client.force_authenticate(ti)
        for nome in URLS:
            self.assertEqual(self.get(nome).status_code, status.HTTP_200_OK, nome)

    def test_nenhuma_resposta_traz_cpf_com_onze_digitos(self):
        for nome in ("nao_fechadas", "composicao", "por_seguradora", "resumo", "dominios"):
            conteudo = self.get(nome, incluir_cancelados="true", todos_tipdoc="true").content.decode()
            self.assertNotRegex(conteudo, r"\d{11}", nome)
        # E o CNPJ sai formatado, não cru.
        conteudo = self.get("nao_fechadas", incluir_cancelados="true").content.decode()
        self.assertNotIn("00000000000191", conteudo)


class ServicosDiretosTests(_ComCarga):
    """Apoio: os serviços respondem sem a camada HTTP (usados pelo shell e pela fase 2)."""

    def test_bloco_direto_e_nao_fechadas_por_seguradora(self):
        f = filtros()
        bloco = agregacao.bloco(agregacao.queryset_base(f), *f.janela)
        self.assertEqual((bloco["fechados"], bloco["renovacoes"], bloco["captacoes"]), (11, 7, 4))
        self.assertEqual(dict(nao_fechadas.calcular(f).sem_nova_por_seguradora()), {"ALLI": 1, "PORT": 1})
