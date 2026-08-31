# condomed/tests.py
"""Cobre CT-CIP-001..008 da matriz de specs/curso-cipa/matriz.csv."""
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from agenda.models import Reserva

from .models import AUDITORIO, SALA_REUNIAO, InscricaoCipa, TurmaCipa

Usuario = get_user_model()

DIA = date(2026, 9, 15)
CPF_A = "52998224725"  # CPF sintético válido (dígitos verificadores corretos)
CPF_B = "16899535009"


def dados_turma(**overrides):
    base = {
        "local": AUDITORIO,
        "data": DIA.isoformat(),
        "administradora_codigo": "001",
        "administradora_nome": "Administradora Teste",
        "condominio_nome": "Condomínio Teste",
    }
    base.update(overrides)
    return base


class CipaTestBase(APITestCase):
    def setUp(self):
        self.operador = Usuario.objects.create_user(
            email="condomed@teste.com", password="x", nivel_acesso="condomed"
        )
        self.admin = Usuario.objects.create_user(
            email="admin@teste.com", password="x", nivel_acesso="admin"
        )
        self.comum = Usuario.objects.create_user(
            email="comum@teste.com", password="x", nivel_acesso="usuario"
        )
        self.client.force_authenticate(self.operador)


class TurmaCipaTests(CipaTestBase):
    def test_ct_cip_001_cria_turma_com_horario_padrao(self):
        resposta = self.client.post("/cursos-cipa/", dados_turma(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        turma = TurmaCipa.objects.get(pk=resposta.data["id"])
        self.assertEqual(turma.hora_inicio, time(9, 0))
        self.assertEqual(turma.hora_fim, time(17, 30))
        self.assertEqual(turma.status, "agendada")
        self.assertEqual(turma.criado_por, self.operador)
        self.assertEqual(resposta.data["capacidade"], 30)
        self.assertEqual(resposta.data["total_inscritos"], 0)

    def test_ct_cip_002_segunda_turma_no_mesmo_local_e_dia_da_409(self):
        self.client.post("/cursos-cipa/", dados_turma(), format="json")

        resposta = self.client.post("/cursos-cipa/", dados_turma(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resposta.data["conflito"]["tipo"], "turma")
        self.assertEqual(TurmaCipa.objects.count(), 1)

    def test_turma_no_outro_local_no_mesmo_dia_e_permitida(self):
        self.client.post("/cursos-cipa/", dados_turma(), format="json")

        resposta = self.client.post(
            "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

    def test_ct_cip_003_sala_cria_e_remove_reserva_espelho(self):
        resposta = self.client.post(
            "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

        turma = TurmaCipa.objects.get(pk=resposta.data["id"])
        self.assertIsNotNone(turma.reserva_sala)
        self.assertEqual(turma.reserva_sala.data, DIA)
        self.assertEqual(turma.reserva_sala.horario, "09:00")
        self.assertEqual(turma.reserva_sala.duracao, 510)
        self.assertEqual(Reserva.objects.count(), 1)

        self.client.delete("/cursos-cipa/%s/" % turma.id)

        self.assertEqual(Reserva.objects.count(), 0)
        self.assertEqual(TurmaCipa.objects.count(), 0)

    def test_auditorio_nao_cria_espelho(self):
        self.client.post("/cursos-cipa/", dados_turma(), format="json")

        self.assertEqual(Reserva.objects.count(), 0)

    def test_cancelar_turma_na_sala_remove_espelho(self):
        resposta = self.client.post(
            "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
        )
        turma_id = resposta.data["id"]

        self.client.patch(
            "/cursos-cipa/%s/" % turma_id, {"status": "cancelada"}, format="json"
        )

        self.assertEqual(Reserva.objects.count(), 0)
        self.assertIsNone(TurmaCipa.objects.get(pk=turma_id).reserva_sala)

    def test_ct_cip_004_reserva_existente_na_sala_bloqueia_turma(self):
        Reserva.objects.create(
            tema="Reunião comercial",
            participantes="Fulano",
            data=DIA,
            horario="10:00",
            duracao=120,
            criado_por=self.admin,
        )

        resposta = self.client.post(
            "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resposta.data["conflito"]["tipo"], "reserva")
        self.assertEqual(TurmaCipa.objects.count(), 0)

    def test_reserva_fora_do_horario_do_curso_nao_bloqueia(self):
        Reserva.objects.create(
            tema="Reunião noturna",
            participantes="Fulano",
            data=DIA,
            horario="18:00",
            duracao=60,
            criado_por=self.admin,
        )

        resposta = self.client.post(
            "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

    def test_ct_cip_008_falha_no_espelho_nao_persiste_turma(self):
        with patch(
            "condomed.services.criar_reserva_espelho",
            side_effect=RuntimeError("falhou"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
                )

        self.assertEqual(TurmaCipa.objects.count(), 0)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_lista_filtra_por_local_mes_e_ano(self):
        self.client.post("/cursos-cipa/", dados_turma(), format="json")
        self.client.post("/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json")

        resposta = self.client.get(
            "/cursos-cipa/", {"local": AUDITORIO, "mes": 9, "ano": 2026}
        )

        self.assertEqual(len(resposta.data), 1)
        self.assertEqual(resposta.data[0]["local"], AUDITORIO)

        vazio = self.client.get(
            "/cursos-cipa/", {"local": AUDITORIO, "mes": 10, "ano": 2026}
        )
        self.assertEqual(len(vazio.data), 0)


class InscricaoCipaTests(CipaTestBase):
    def setUp(self):
        super().setUp()
        resposta = self.client.post("/cursos-cipa/", dados_turma(), format="json")
        self.turma = TurmaCipa.objects.get(pk=resposta.data["id"])

    def inscrever(self, **overrides):
        dados = {
            "nome": "Fulano de Tal",
            "cpf": CPF_A,
            "funcao": "Zelador",
            "email": "fulano@teste.com",
            "telefone": "11999999999",
        }
        dados.update(overrides)
        return self.client.post(
            "/cursos-cipa/%s/inscricoes/" % self.turma.id, dados, format="json"
        )

    def test_ct_cip_005_inscricao_valida_cpf_repetido_e_cpf_invalido(self):
        criada = self.inscrever()
        self.assertEqual(criada.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.turma.inscricoes.count(), 1)

        repetida = self.inscrever(nome="Outro Nome")
        self.assertEqual(repetida.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cpf", repetida.data)

        invalida = self.inscrever(cpf="11111111111")
        self.assertEqual(invalida.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(self.turma.inscricoes.count(), 1)

    def test_cpf_e_gravado_apenas_com_digitos(self):
        self.inscrever(cpf="529.982.247-25")

        self.assertEqual(self.turma.inscricoes.first().cpf, CPF_A)

    def test_ct_cip_006_inscricao_alem_da_capacidade_da_400(self):
        turma_sala = TurmaCipa.objects.create(
            local=SALA_REUNIAO,
            data=DIA,
            administradora_codigo="001",
            criado_por=self.operador,
        )
        for i in range(10):
            InscricaoCipa.objects.create(
                turma=turma_sala, nome="Inscrito %s" % i, cpf="%011d" % i
            )

        resposta = self.client.post(
            "/cursos-cipa/%s/inscricoes/" % turma_sala.id,
            {"nome": "Excedente", "cpf": CPF_B},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(turma_sala.inscricoes.count(), 10)

    def test_lista_e_remove_inscrito(self):
        criada = self.inscrever()

        listagem = self.client.get("/cursos-cipa/%s/inscricoes/" % self.turma.id)
        self.assertEqual(len(listagem.data), 1)

        removida = self.client.delete(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, criada.data["id"])
        )
        self.assertEqual(removida.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.turma.inscricoes.count(), 0)


class AcessoCipaTests(CipaTestBase):
    def test_ct_cip_007_nivel_comum_recebe_403(self):
        self.client.force_authenticate(self.comum)

        self.assertEqual(
            self.client.get("/cursos-cipa/").status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.post("/cursos-cipa/", dados_turma(), format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_ct_cip_007_condomed_e_admin_acessam(self):
        for usuario in (self.operador, self.admin):
            self.client.force_authenticate(usuario)
            self.assertEqual(
                self.client.get("/cursos-cipa/").status_code, status.HTTP_200_OK
            )

    def test_anonimo_nao_acessa(self):
        self.client.force_authenticate(None)

        self.assertIn(
            self.client.get("/cursos-cipa/").status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
