# condomed/tests.py
"""Cobre CT-CIP-001..013 da matriz de specs/curso-cipa/matriz.csv."""
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
    """Turma: local e dia. O cliente é de cada inscrito (ADR-0004)."""
    base = {
        "local": AUDITORIO,
        "data": DIA.isoformat(),
    }
    base.update(overrides)
    return base


def dados_vinculo(**overrides):
    """Administradora e condomínio de um participante (obrigatórios)."""
    base = {
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
            **dados_vinculo(),
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
            criado_por=self.operador,
        )
        for i in range(10):
            InscricaoCipa.objects.create(
                turma=turma_sala,
                nome="Inscrito %s" % i,
                cpf="%011d" % i,
                **dados_vinculo(),
            )

        resposta = self.client.post(
            "/cursos-cipa/%s/inscricoes/" % turma_sala.id,
            {"nome": "Excedente", "cpf": CPF_B, **dados_vinculo()},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(turma_sala.inscricoes.count(), 10)

    def test_edita_inscrito(self):
        criada = self.inscrever()

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, criada.data["id"]),
            {"nome": "Fulano Editado", "funcao": "Sindico"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        inscrito = self.turma.inscricoes.get(pk=criada.data["id"])
        self.assertEqual(inscrito.nome, "Fulano Editado")
        self.assertEqual(inscrito.funcao, "Sindico")
        self.assertEqual(inscrito.cpf, CPF_A)  # não informado no PATCH, preservado

    def test_edita_o_proprio_cpf_sem_colidir_consigo_mesmo(self):
        criada = self.inscrever()

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, criada.data["id"]),
            {"cpf": "529.982.247-25"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(self.turma.inscricoes.get(pk=criada.data["id"]).cpf, CPF_A)

    def test_edicao_com_cpf_de_outro_inscrito_da_400(self):
        primeira = self.inscrever()
        self.inscrever(nome="Beltrano", cpf=CPF_B)

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, primeira.data["id"]),
            {"cpf": CPF_B},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cpf", resposta.data)

    def test_edicao_com_cpf_invalido_da_400(self):
        criada = self.inscrever()

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, criada.data["id"]),
            {"cpf": "11111111111"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edita_inscrito_em_turma_lotada(self):
        """Editar quem já está na lista não consome vaga."""
        turma_sala = TurmaCipa.objects.create(
            local=SALA_REUNIAO,
            data=DIA,
            criado_por=self.operador,
        )
        for i in range(10):
            InscricaoCipa.objects.create(
                turma=turma_sala,
                nome="Inscrito %s" % i,
                cpf="%011d" % i,
                **dados_vinculo(),
            )
        alvo = turma_sala.inscricoes.first()

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (turma_sala.id, alvo.id),
            {"funcao": "Zelador"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(turma_sala.inscricoes.count(), 10)

    def test_edicao_de_inscrito_de_outra_turma_da_404(self):
        criada = self.inscrever()
        outra = TurmaCipa.objects.create(
            local=SALA_REUNIAO,
            data=DIA,
            criado_por=self.operador,
        )

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (outra.id, criada.data["id"]),
            {"nome": "Invasor"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)

    def test_verificar_cpf_lista_outras_turmas(self):
        self.inscrever()
        outra = TurmaCipa.objects.create(
            local=SALA_REUNIAO,
            data=date(2026, 9, 22),
            criado_por=self.operador,
        )
        InscricaoCipa.objects.create(
            turma=outra,
            nome="Fulano de Tal",
            cpf=CPF_A,
            **dados_vinculo(condominio_nome="Condomínio Vizinho"),
        )

        resposta = self.client.get(
            "/cursos-cipa/verificar-cpf/",
            {"cpf": CPF_A, "excluir_turma": self.turma.id},
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data), 1)
        self.assertEqual(resposta.data[0]["turma_id"], outra.id)
        self.assertEqual(resposta.data[0]["condominio_nome"], "Condomínio Vizinho")
        self.assertEqual(
            resposta.data[0]["administradora_nome"], "Administradora Teste"
        )
        self.assertEqual(resposta.data[0]["local_nome"], "Sala de reunião")

    def test_verificar_cpf_sem_outras_turmas_volta_vazio(self):
        self.inscrever()

        resposta = self.client.get(
            "/cursos-cipa/verificar-cpf/",
            {"cpf": CPF_A, "excluir_turma": self.turma.id},
        )

        self.assertEqual(resposta.data, [])

    def test_verificar_cpf_aceita_com_mascara(self):
        self.inscrever()

        resposta = self.client.get("/cursos-cipa/verificar-cpf/", {"cpf": "529.982.247-25"})

        self.assertEqual(len(resposta.data), 1)

    def test_verificar_cpf_invalido_da_400(self):
        resposta = self.client.get("/cursos-cipa/verificar-cpf/", {"cpf": "11111111111"})

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verificar_cpf_exige_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        resposta = self.client.get("/cursos-cipa/verificar-cpf/", {"cpf": CPF_A})

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_inscricao_em_outra_turma_continua_permitida(self):
        """A duplicidade entre turmas é avisada na tela, não bloqueada na API."""
        self.inscrever()
        outra = TurmaCipa.objects.create(
            local=SALA_REUNIAO,
            data=date(2026, 9, 22),
            criado_por=self.operador,
        )

        resposta = self.client.post(
            "/cursos-cipa/%s/inscricoes/" % outra.id,
            {
                "nome": "Fulano de Tal",
                "cpf": CPF_A,
                "funcao": "Zelador",
                **dados_vinculo(condominio_nome="Condomínio Vizinho"),
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

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


class VinculoDoInscritoTests(CipaTestBase):
    """Fase 4 / ADR-0004: o cliente é do participante, não da turma."""

    def setUp(self):
        super().setUp()
        resposta = self.client.post("/cursos-cipa/", dados_turma(), format="json")
        self.turma = TurmaCipa.objects.get(pk=resposta.data["id"])

    def inscrever(self, **overrides):
        dados = {"nome": "Fulano de Tal", "cpf": CPF_A, "funcao": "Zelador"}
        dados.update(dados_vinculo())
        dados.update(overrides)
        return self.client.post(
            "/cursos-cipa/%s/inscricoes/" % self.turma.id, dados, format="json"
        )

    def test_ct_cip_011_inscricao_sem_administradora_da_400(self):
        resposta = self.inscrever(administradora_codigo="")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("administradora_codigo", resposta.data)
        self.assertEqual(self.turma.inscricoes.count(), 0)

    def test_ct_cip_011_inscricao_sem_condominio_da_400(self):
        resposta = self.inscrever(condominio_nome="   ")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("condominio_nome", resposta.data)
        self.assertEqual(self.turma.inscricoes.count(), 0)

    def test_ct_cip_011_vinculo_e_gravado_na_inscricao(self):
        resposta = self.inscrever(condominio_nome="  Condomínio Girassol  ")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        inscricao = self.turma.inscricoes.get()
        self.assertEqual(inscricao.administradora_codigo, "001")
        self.assertEqual(inscricao.administradora_nome, "Administradora Teste")
        # O nome do condomínio é digitado: espaços nas pontas não entram.
        self.assertEqual(inscricao.condominio_nome, "Condomínio Girassol")

    def test_ct_cip_012_turma_deriva_administradoras_e_condominios(self):
        self.inscrever()
        self.inscrever(
            nome="Beltrano",
            cpf=CPF_B,
            administradora_codigo="002",
            administradora_nome="Outra Administradora",
            condominio_nome="Condomínio Bem-Te-Vi",
        )
        # Terceiro pela mesma administradora do primeiro: não deve repetir.
        self.inscrever(nome="Ciclano", cpf="11144477735")

        resposta = self.client.get("/cursos-cipa/%s/" % self.turma.id)

        self.assertEqual(
            resposta.data["administradoras"],
            [
                {"codigo": "001", "nome": "Administradora Teste"},
                {"codigo": "002", "nome": "Outra Administradora"},
            ],
        )
        self.assertEqual(
            resposta.data["condominios"],
            ["Condomínio Bem-Te-Vi", "Condomínio Teste"],
        )
        self.assertEqual(resposta.data["total_inscritos"], 3)

    def test_ct_cip_012_turma_vazia_deriva_listas_vazias(self):
        resposta = self.client.get("/cursos-cipa/%s/" % self.turma.id)

        self.assertEqual(resposta.data["administradoras"], [])
        self.assertEqual(resposta.data["condominios"], [])

    def test_ct_cip_013_turma_ignora_vinculo_enviado_por_engano(self):
        """Cliente antigo mandando administradora na turma não cria campo nem quebra."""
        resposta = self.client.post(
            "/cursos-cipa/",
            dados_turma(
                data=date(2026, 9, 16),
                administradora_codigo="001",
                condominio_nome="Condomínio Fantasma",
            ),
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("condominio_nome", resposta.data)
        self.assertNotIn("administradora_codigo", resposta.data)

    def test_conflito_409_identifica_a_turma_por_local_e_ocupacao(self):
        self.inscrever()

        resposta = self.client.post("/cursos-cipa/", dados_turma(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_409_CONFLICT)
        conflito = resposta.data["conflito"]
        self.assertEqual(conflito["local_nome"], "Auditório")
        self.assertEqual(conflito["ocupacao"], "1/30")
        self.assertNotIn("condominio_nome", conflito)

    def test_espelho_na_agenda_tem_tema_por_local(self):
        turma_sala = self.client.post(
            "/cursos-cipa/",
            dados_turma(local=SALA_REUNIAO, data=date(2026, 9, 17).isoformat()),
            format="json",
        )

        reserva = TurmaCipa.objects.get(pk=turma_sala.data["id"]).reserva_sala
        self.assertEqual(reserva.tema, "Curso CIPA — Sala de reunião")

    def test_edicao_troca_o_vinculo_do_inscrito(self):
        criada = self.inscrever()

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, criada.data["id"]),
            {
                "administradora_codigo": "003",
                "administradora_nome": "Terceira Administradora",
                "condominio_nome": "Condomínio Novo",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        inscricao = self.turma.inscricoes.get()
        self.assertEqual(inscricao.administradora_codigo, "003")
        self.assertEqual(inscricao.condominio_nome, "Condomínio Novo")
        # O CPF não enviado é preservado (PATCH parcial).
        self.assertEqual(inscricao.cpf, CPF_A)


class ExclusaoDeTurmaTests(CipaTestBase):
    """CT-CIP-014: apagar a turma inteira leva inscritos e reserva com ela."""

    def setUp(self):
        super().setUp()
        resposta = self.client.post(
            "/cursos-cipa/",
            dados_turma(local=SALA_REUNIAO),
            format="json",
        )
        self.turma = TurmaCipa.objects.get(pk=resposta.data["id"])
        for indice, cpf in enumerate((CPF_A, CPF_B)):
            InscricaoCipa.objects.create(
                turma=self.turma,
                nome="Inscrito %s" % indice,
                cpf=cpf,
                **dados_vinculo(),
            )

    def test_ct_cip_014_exclusao_remove_inscritos_e_reserva(self):
        reserva_id = self.turma.reserva_sala_id
        self.assertIsNotNone(reserva_id)

        resposta = self.client.delete("/cursos-cipa/%s/" % self.turma.id)

        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TurmaCipa.objects.filter(pk=self.turma.id).exists())
        self.assertFalse(InscricaoCipa.objects.filter(turma_id=self.turma.id).exists())
        self.assertFalse(Reserva.objects.filter(pk=reserva_id).exists())

    def test_ct_cip_014_cancelar_preserva_inscritos_e_libera_a_sala(self):
        """A alternativa que a tela oferece: cancelar em vez de apagar."""
        reserva_id = self.turma.reserva_sala_id

        resposta = self.client.patch(
            "/cursos-cipa/%s/" % self.turma.id, {"status": "cancelada"}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.status, "cancelada")
        self.assertEqual(self.turma.inscricoes.count(), 2)
        # A sala volta a ficar livre na agenda.
        self.assertIsNone(self.turma.reserva_sala_id)
        self.assertFalse(Reserva.objects.filter(pk=reserva_id).exists())

    def test_ct_cip_014_exclusao_exige_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        resposta = self.client.delete("/cursos-cipa/%s/" % self.turma.id)

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(TurmaCipa.objects.filter(pk=self.turma.id).exists())

    def test_ct_cip_014_dia_fica_livre_para_nova_turma_depois_da_exclusao(self):
        self.client.delete("/cursos-cipa/%s/" % self.turma.id)

        resposta = self.client.post(
            "/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)


class ImportacaoPorPlanilhaTests(CipaTestBase):
    """CT-CIP-015..018: turma + inscritos de uma planilha, na mesma transação."""

    def linha(self, **overrides):
        base = {
            "nome": "Fulano de Tal",
            "cpf": CPF_A,
            "funcao": "Zelador",
            **dados_vinculo(),
        }
        base.update(overrides)
        return base

    def importar(self, inscricoes, **overrides):
        corpo = {
            "local": AUDITORIO,
            "data": DIA.isoformat(),
            "inscricoes": inscricoes,
        }
        corpo.update(overrides)
        return self.client.post("/cursos-cipa/importar/", corpo, format="json")

    def test_ct_cip_015_importa_turma_com_inscritos(self):
        resposta = self.importar([
            self.linha(),
            self.linha(nome="Beltrano", cpf=CPF_B, condominio_nome="Ed. Bem-Te-Vi"),
        ])

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        turma = TurmaCipa.objects.get(pk=resposta.data["id"])
        self.assertEqual(turma.inscricoes.count(), 2)
        self.assertEqual(resposta.data["total_inscritos"], 2)
        self.assertEqual(len(resposta.data["condominios"]), 2)

    def test_ct_cip_016_linha_invalida_nao_grava_nada(self):
        resposta = self.importar([
            self.linha(),
            self.linha(nome="Sem CPF", cpf="11111111111"),
        ])

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("1", resposta.data["inscricoes"])
        self.assertFalse(TurmaCipa.objects.exists())

    def test_ct_cip_016_linha_sem_vinculo_nao_grava_nada(self):
        resposta = self.importar([self.linha(condominio_nome="")])

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("condominio_nome", resposta.data["inscricoes"]["0"])
        self.assertFalse(TurmaCipa.objects.exists())

    def test_ct_cip_016_cpf_repetido_na_planilha_aponta_a_linha(self):
        resposta = self.importar([self.linha(), self.linha(nome="Homônimo")])

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("linha 1", str(resposta.data["inscricoes"]["1"]["cpf"]))
        self.assertFalse(TurmaCipa.objects.exists())

    def test_ct_cip_017_planilha_maior_que_a_capacidade_nao_grava_nada(self):
        linhas = [
            self.linha(nome="Inscrito %s" % i, cpf="%011d" % i) for i in range(11)
        ]

        resposta = self.importar(linhas, local=SALA_REUNIAO)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("11 pessoas", str(resposta.data["inscricoes"]))
        self.assertIn("comporta 10", str(resposta.data["inscricoes"]))
        self.assertFalse(TurmaCipa.objects.exists())

    def test_ct_cip_017_conflito_de_dia_nao_grava_nada(self):
        self.client.post("/cursos-cipa/", dados_turma(), format="json")

        resposta = self.importar([self.linha()])

        self.assertEqual(resposta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(TurmaCipa.objects.count(), 1)
        self.assertEqual(InscricaoCipa.objects.count(), 0)

    def test_ct_cip_017_importacao_na_sala_cria_o_espelho_na_agenda(self):
        resposta = self.importar([self.linha()], local=SALA_REUNIAO)

        turma = TurmaCipa.objects.get(pk=resposta.data["id"])
        self.assertIsNotNone(turma.reserva_sala)
        self.assertEqual(turma.reserva_sala.tema, "Curso CIPA — Sala de reunião")

    def test_ct_cip_017_planilha_vazia_da_400(self):
        resposta = self.importar([])

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(TurmaCipa.objects.exists())

    def test_ct_cip_018_planilha_modelo_baixa_com_os_cabecalhos(self):
        resposta = self.client.get("/cursos-cipa/planilha-modelo/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn("spreadsheetml", resposta["Content-Type"])
        self.assertIn("modelo-inscritos-cipa.xlsx", resposta["Content-Disposition"])

        import io as _io

        import openpyxl

        aba = openpyxl.load_workbook(_io.BytesIO(resposta.content)).active
        cabecalhos = [celula.value for celula in aba[1]]
        self.assertEqual(
            cabecalhos,
            [
                "administradora",
                "condominio",
                "nome",
                "cpf",
                "funcao",
                "email",
                "telefone",
            ],
        )
        # Sem colunas de local e data: a turma é escolhida na tela.
        self.assertNotIn("local", cabecalhos)
        self.assertNotIn("data", cabecalhos)

    def test_ct_cip_018_importacao_e_modelo_exigem_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        self.assertEqual(
            self.client.get("/cursos-cipa/planilha-modelo/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.importar([self.linha()]).status_code, status.HTTP_403_FORBIDDEN
        )
