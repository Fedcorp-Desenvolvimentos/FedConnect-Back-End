# condomed/tests.py
"""Cobre CT-CIP-001..013 da matriz de specs/curso-cipa/matriz.csv."""
from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from agenda.models import Reserva

from .models import AUDITORIO, SALA_REUNIAO, CertificadoCipa, InscricaoCipa, InstrutorCipa, LocalCipa, TurmaCipa
from .serializers import InscricaoCipaSerializer

Usuario = get_user_model()

DIA = date(2026, 9, 15)
CPF_A = "52998224725"  # CPF sintético válido (dígitos verificadores corretos)
CPF_B = "16899535009"


def cpf_sintetico(indice):
    """CPF válido a partir de um índice, para listas grandes nos testes.

    Os nove primeiros dígitos vêm do índice; os dois últimos são calculados,
    senão a validação de CPF recusa a linha antes de a regra em teste rodar.
    """
    base = f"{indice:09d}"
    for _ in range(2):
        peso = len(base) + 1
        soma = sum(int(digito) * (peso - i) for i, digito in enumerate(base))
        verificador = (soma * 10) % 11
        base += str(0 if verificador == 10 else verificador)
    return base


def local_por_codigo(codigo):
    """Registro do local semeado pela migração 0005 (AUDITORIO / SALA_REUNIAO)."""
    return LocalCipa.objects.get(codigo=codigo)


def instrutor_por_codigo(codigo):
    return InstrutorCipa.objects.get(codigo=codigo)


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
        # Código derivado: ano do curso + id com 4 dígitos. É o nome que a turma não tem.
        self.assertEqual(resposta.data["codigo"], f"CIPA-2026-{turma.pk:04d}")

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

    def test_ct_cip_006_inscricao_acima_da_capacidade_entra_e_e_sinalizada(self):
        """Capacidade é referência, não trava (ADR-0006): extra de última hora entra."""
        turma_sala = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO),
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

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(turma_sala.inscricoes.count(), 11)

        turma = self.client.get("/cursos-cipa/%s/" % turma_sala.id)
        self.assertEqual(turma.data["capacidade"], 10)
        self.assertEqual(turma.data["total_inscritos"], 11)
        self.assertEqual(turma.data["acima_da_capacidade"], 1)

    def test_ct_cip_006_turma_dentro_da_capacidade_nao_sinaliza_excesso(self):
        self.inscrever()

        resposta = self.client.get("/cursos-cipa/%s/" % self.turma.id)

        self.assertEqual(resposta.data["acima_da_capacidade"], 0)

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

    def test_edita_inscrito_em_turma_cheia(self):
        """Editar quem já está na lista não depende de vaga."""
        turma_sala = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO),
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
            local=local_por_codigo(SALA_REUNIAO),
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
            local=local_por_codigo(SALA_REUNIAO),
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
            local=local_por_codigo(SALA_REUNIAO),
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

    def test_ct_cip_017_planilha_maior_que_a_capacidade_entra_e_sinaliza(self):
        """A planilha que passa da capacidade importa inteira (ADR-0006)."""
        linhas = [
            self.linha(nome="Inscrito %s" % i, cpf=cpf_sintetico(i + 1))
            for i in range(11)
        ]

        resposta = self.importar(linhas, local=SALA_REUNIAO)

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resposta.data["total_inscritos"], 11)
        self.assertEqual(resposta.data["capacidade"], 10)
        self.assertEqual(resposta.data["acima_da_capacidade"], 1)

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
                "cnpj_condominio",
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


class DuplicidadeDeCpfNaTurmaTests(CipaTestBase):
    """CT-CIP-019: o mesmo CPF nunca fica duas vezes na mesma turma."""

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

    def test_ct_cip_019_segunda_inscricao_do_mesmo_cpf_da_400(self):
        self.assertEqual(self.inscrever().status_code, status.HTTP_201_CREATED)

        repetida = self.inscrever(nome="Outro Nome")

        self.assertEqual(repetida.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cpf", repetida.data)
        self.assertEqual(self.turma.inscricoes.count(), 1)

    def test_ct_cip_019_mascara_nao_burla_a_duplicidade(self):
        """CPF com e sem pontuação é o mesmo CPF: normaliza antes de comparar."""
        self.inscrever()

        repetida = self.inscrever(cpf="529.982.247-25", nome="Com máscara")

        self.assertEqual(repetida.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.turma.inscricoes.count(), 1)

    def test_ct_cip_019_corrida_recebe_400_e_nao_500(self):
        """Duas requisições simultâneas: a validação não vê, o banco vê.

        Sem o `select_for_update` (removido no ADR-0006, que era de
        capacidade), as duas passam pela checagem do serializer. O
        `unique_together` continua barrando — e o erro tem de chegar como 400,
        não como um 500 de IntegrityError.
        """
        self.inscrever()

        # Simula a janela da corrida: a validação passa, o banco recusa.
        with patch.object(
            InscricaoCipaSerializer, "validate", side_effect=lambda attrs: attrs
        ):
            repetida = self.inscrever(nome="Chegou junto")

        self.assertEqual(repetida.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cpf", repetida.data)
        self.assertEqual(self.turma.inscricoes.count(), 1)

    def test_ct_cip_019_edicao_nao_acusa_o_proprio_cpf(self):
        criada = self.inscrever()

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, criada.data["id"]),
            {"funcao": "Porteiro", "cpf": CPF_A},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_ct_cip_019_edicao_para_cpf_de_outro_inscrito_da_400(self):
        primeira = self.inscrever()
        self.inscrever(nome="Beltrano", cpf=CPF_B)

        resposta = self.client.patch(
            "/cursos-cipa/%s/inscricoes/%s/" % (self.turma.id, primeira.data["id"]),
            {"cpf": CPF_B},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cpf", resposta.data)

    def test_ct_cip_019_mesmo_cpf_em_outra_turma_continua_permitido(self):
        self.inscrever()
        outra = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO), data=DIA, criado_por=self.operador
        )

        resposta = self.client.post(
            "/cursos-cipa/%s/inscricoes/" % outra.id,
            {
                "nome": "Fulano de Tal",
                "cpf": CPF_A,
                "funcao": "Zelador",
                **dados_vinculo(),
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)


class HistoricoEConsultaTests(CipaTestBase):
    """CT-HIS-001..004: histórico paginado de turmas e consulta de participantes."""

    def setUp(self):
        super().setUp()
        # Três turmas em meses diferentes, com gente de duas administradoras.
        self.antiga = TurmaCipa.objects.create(
            local=local_por_codigo(AUDITORIO), data=date(2026, 6, 10), status="realizada",
            criado_por=self.operador,
        )
        self.recente = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO), data=date(2026, 9, 15), criado_por=self.operador,
        )
        self.cancelada = TurmaCipa.objects.create(
            local=local_por_codigo(AUDITORIO), data=date(2026, 9, 20), status="cancelada",
            criado_por=self.operador,
        )
        InscricaoCipa.objects.create(
            turma=self.antiga, nome="Maria Aparecida", cpf=CPF_A,
            **dados_vinculo(),
        )
        InscricaoCipa.objects.create(
            turma=self.recente, nome="Maria Aparecida", cpf=CPF_A,
            **dados_vinculo(condominio_nome="Edifício Bem-Te-Vi"),
        )
        InscricaoCipa.objects.create(
            turma=self.recente, nome="João Batista", cpf=CPF_B,
            administradora_codigo="002", administradora_nome="Habitar Imóveis",
            condominio_nome="Residencial Aurora",
        )

    # --- histórico de turmas -------------------------------------------------

    def test_ct_his_001_historico_lista_paginado_do_mais_recente_ao_mais_antigo(self):
        resposta = self.client.get("/cursos-cipa/historico/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["count"], 3)
        datas = [turma["data"] for turma in resposta.data["results"]]
        self.assertEqual(datas, ["2026-09-20", "2026-09-15", "2026-06-10"])
        # Sem a lista de inscritos: o histórico traz só contagens e derivados.
        self.assertNotIn("inscricoes", resposta.data["results"][0])
        self.assertEqual(resposta.data["results"][1]["total_inscritos"], 2)
        self.assertEqual(len(resposta.data["results"][1]["administradoras"]), 2)

    def test_ct_his_001_historico_filtra_por_periodo_local_e_situacao(self):
        por_periodo = self.client.get(
            "/cursos-cipa/historico/",
            {"data_inicio": "2026-09-01", "data_fim": "2026-09-30"},
        )
        self.assertEqual(por_periodo.data["count"], 2)

        por_local = self.client.get("/cursos-cipa/historico/", {"local": SALA_REUNIAO})
        self.assertEqual(por_local.data["count"], 1)
        self.assertEqual(por_local.data["results"][0]["id"], self.recente.id)

        por_status = self.client.get("/cursos-cipa/historico/", {"status": "cancelada"})
        self.assertEqual(por_status.data["count"], 1)

    def test_ct_his_001_historico_filtra_por_administradora_e_condominio_dos_inscritos(self):
        por_adm = self.client.get("/cursos-cipa/historico/", {"administradora": "002"})
        self.assertEqual(por_adm.data["count"], 1)
        self.assertEqual(por_adm.data["results"][0]["id"], self.recente.id)

        por_cond = self.client.get("/cursos-cipa/historico/", {"condominio": "teste"})
        # "Condomínio Teste" só na turma antiga (a recente tem outro condomínio).
        self.assertEqual(por_cond.data["count"], 1)
        self.assertEqual(por_cond.data["results"][0]["id"], self.antiga.id)

    def test_ct_his_001_busca_livre_nao_duplica_turma_com_varios_inscritos_casando(self):
        # "Maria" casa em duas turmas; "a" casaria em vários inscritos da mesma
        # turma — o distinct evita a turma repetida.
        resposta = self.client.get("/cursos-cipa/historico/", {"busca": "a"})

        ids = [turma["id"] for turma in resposta.data["results"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ct_his_001_busca_por_cpf_com_mascara(self):
        resposta = self.client.get("/cursos-cipa/historico/", {"busca": "529.982.247-25"})

        self.assertEqual(resposta.data["count"], 2)

    def test_ct_his_002_paginacao_respeita_page_size_e_teto(self):
        resposta = self.client.get("/cursos-cipa/historico/", {"page_size": 2})
        self.assertEqual(len(resposta.data["results"]), 2)
        self.assertIsNotNone(resposta.data["next"])

        acima_do_teto = self.client.get("/cursos-cipa/historico/", {"page_size": 999})
        self.assertLessEqual(len(acima_do_teto.data["results"]), 100)

    def test_ct_his_002_calendario_continua_sem_paginacao(self):
        """A rota nova não pode mudar o contrato da agenda."""
        resposta = self.client.get("/cursos-cipa/", {"mes": 9, "ano": 2026})

        self.assertIsInstance(resposta.data, list)
        self.assertEqual(len(resposta.data), 2)

    # --- consulta de participantes -------------------------------------------

    def test_ct_his_003_participantes_uma_linha_por_inscricao_com_a_turma(self):
        resposta = self.client.get("/cursos-cipa/participantes/", {"cpf": CPF_A})

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["count"], 2)
        linha = resposta.data["results"][0]
        self.assertEqual(linha["nome"], "Maria Aparecida")
        self.assertEqual(linha["turma"]["id"], self.recente.id)
        self.assertEqual(linha["turma"]["local_nome"], "Sala de reunião")
        self.assertEqual(linha["turma"]["status"], "agendada")
        self.assertEqual(linha["turma"]["codigo"], f"CIPA-2026-{self.recente.pk:04d}")

    def test_ct_his_003_participantes_busca_por_nome_condominio_e_administradora(self):
        por_nome = self.client.get("/cursos-cipa/participantes/", {"busca": "joão"})
        self.assertEqual(por_nome.data["count"], 1)

        por_cond = self.client.get("/cursos-cipa/participantes/", {"busca": "aurora"})
        self.assertEqual(por_cond.data["count"], 1)

        por_adm = self.client.get("/cursos-cipa/participantes/", {"busca": "habitar"})
        self.assertEqual(por_adm.data["count"], 1)
        self.assertEqual(por_adm.data["results"][0]["nome"], "João Batista")

    def test_ct_his_003_participantes_busca_por_inicio_de_cpf(self):
        resposta = self.client.get("/cursos-cipa/participantes/", {"busca": "529.98"})

        self.assertEqual(resposta.data["count"], 2)

    def test_ct_his_003_participantes_filtra_por_periodo(self):
        resposta = self.client.get(
            "/cursos-cipa/participantes/", {"cpf": CPF_A, "data_inicio": "2026-09-01"}
        )

        self.assertEqual(resposta.data["count"], 1)
        self.assertEqual(resposta.data["results"][0]["turma"]["id"], self.recente.id)

    def test_ct_his_004_historico_e_participantes_exigem_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        self.assertEqual(
            self.client.get("/cursos-cipa/historico/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/cursos-cipa/participantes/").status_code,
            status.HTTP_403_FORBIDDEN,
        )


class CadastroParaCertificadoTests(CipaTestBase):
    """CT-CIP-020: CNPJ do condomínio na inscrição e instrutor na turma."""

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

    def test_ct_cip_020_cnpj_e_opcional_e_gravado_so_com_digitos(self):
        sem = self.inscrever()
        self.assertEqual(sem.status_code, status.HTTP_201_CREATED)
        self.assertEqual(sem.data["condominio_cnpj"], "")

        com = self.inscrever(cpf=CPF_B, condominio_cnpj="01.998.690/0001-82")
        self.assertEqual(com.status_code, status.HTTP_201_CREATED)
        self.assertEqual(com.data["condominio_cnpj"], "01998690000182")

    def test_ct_cip_020_cnpj_invalido_da_400(self):
        resposta = self.inscrever(condominio_cnpj="01.998.690/0001-83")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("condominio_cnpj", resposta.data)

    def test_ct_cip_020_turma_aceita_instrutor_da_lista_e_recusa_fora_dela(self):
        ok = self.client.patch(
            "/cursos-cipa/%s/" % self.turma.id, {"instrutor": "FELIPE"}, format="json"
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.data["instrutor_nome"], "Felipe Barboza de Oliveira")

        fora = self.client.patch(
            "/cursos-cipa/%s/" % self.turma.id, {"instrutor": "QUALQUER"}, format="json"
        )
        self.assertEqual(fora.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ct_cip_020_turma_sem_instrutor_continua_valida(self):
        resposta = self.client.get("/cursos-cipa/%s/" % self.turma.id)

        self.assertEqual(resposta.data["instrutor"], "")
        self.assertEqual(resposta.data["instrutor_nome"], "")

    def test_ct_cip_020_lista_de_instrutores_sem_expor_arquivo_de_assinatura(self):
        resposta = self.client.get("/cursos-cipa/instrutores/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        codigos = {item["codigo"] for item in resposta.data}
        self.assertEqual(codigos, {"FELIPE", "VINICIUS"})
        self.assertEqual(resposta.data[0]["registro"], "MTE/RJ 0060169")
        self.assertNotIn("assinatura", resposta.data[0])

    def test_ct_cip_020_locais_trazem_a_unidade_emissora(self):
        resposta = self.client.get("/cursos-cipa/locais/")

        for local in resposta.data:
            self.assertEqual(local["unidade"]["cidade"], "Rio de Janeiro")
            self.assertIn("Alfândega", local["unidade"]["endereco"])

    def test_ct_cip_020_importacao_aceita_cnpj_e_instrutor(self):
        resposta = self.client.post(
            "/cursos-cipa/importar/",
            {
                "local": AUDITORIO,
                "data": date(2026, 9, 16).isoformat(),
                "instrutor": "VINICIUS",
                "inscricoes": [
                    {
                        "nome": "Fulano de Tal",
                        "cpf": CPF_A,
                        "funcao": "Zelador",
                        "condominio_cnpj": "01580092000199",
                        **dados_vinculo(),
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resposta.data["instrutor"], "VINICIUS")
        turma = TurmaCipa.objects.get(pk=resposta.data["id"])
        self.assertEqual(turma.inscricoes.get().condominio_cnpj, "01580092000199")

    def test_ct_cip_020_importacao_com_cnpj_invalido_nao_grava_nada(self):
        resposta = self.client.post(
            "/cursos-cipa/importar/",
            {
                "local": AUDITORIO,
                "data": date(2026, 9, 16).isoformat(),
                "inscricoes": [
                    {
                        "nome": "Fulano de Tal",
                        "cpf": CPF_A,
                        "funcao": "Zelador",
                        "condominio_cnpj": "123",
                        **dados_vinculo(),
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("condominio_cnpj", resposta.data["inscricoes"]["0"])
        self.assertEqual(TurmaCipa.objects.count(), 1)  # só a do setUp


class ListaPresencaTests(CipaTestBase):
    """CT-HIS-005: lista de presença em PDF, ordenada por condomínio e com linhas extras."""

    def setUp(self):
        super().setUp()
        self.turma = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO), data=DIA, instrutor=instrutor_por_codigo("FELIPE"), criado_por=self.operador
        )
        # Inserção fora de ordem de propósito: a lista tem de ordenar.
        InscricaoCipa.objects.create(
            turma=self.turma, nome="Zuleica", cpf=cpf_sintetico(3),
            administradora_codigo="002", administradora_nome="Habitar",
            condominio_nome="Residencial Aurora",
        )
        InscricaoCipa.objects.create(
            turma=self.turma, nome="Bruno", cpf=cpf_sintetico(1),
            administradora_codigo="001", administradora_nome="Delforte",
            condominio_nome="edifício bem-te-vi",
        )
        InscricaoCipa.objects.create(
            turma=self.turma, nome="Ana", cpf=cpf_sintetico(2),
            administradora_codigo="002", administradora_nome="Habitar",
            condominio_nome="Residencial Aurora",
        )

    def test_ct_his_005_linhas_ordenadas_por_condominio_depois_nome_com_extras(self):
        from condomed.documentos import linhas_lista_presenca

        linhas = linhas_lista_presenca(self.turma, linhas_extras=5)

        nomes = [l["nome"] for l in linhas if not l["extra"]]
        # "edifício bem-te-vi" < "Residencial Aurora" sem distinguir caixa/acento inicial
        self.assertEqual(nomes, ["Bruno", "Ana", "Zuleica"])
        self.assertEqual([l["numero"] for l in linhas], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(sum(1 for l in linhas if l["extra"]), 5)
        self.assertEqual(linhas[0]["cpf"], "000.000.001-91")  # formatado

    def test_ct_his_005_cabecalho_resolve_unidade_e_instrutor(self):
        from condomed.documentos import cabecalho_lista_presenca

        cab = cabecalho_lista_presenca(self.turma)

        self.assertEqual(cab["unidade_nome"], "CondoMed Rio")
        self.assertIn("Felipe Barboza de Oliveira", cab["instrutor"])
        self.assertIn("MTE/RJ 0060169", cab["instrutor"])
        self.assertEqual(cab["local"], "Sala de reunião")
        self.assertEqual(cab["total"], 3)
        self.assertEqual(cab["capacidade"], 10)

    def test_ct_his_005_sem_instrutor_o_cabecalho_diz_a_definir(self):
        from condomed.documentos import cabecalho_lista_presenca

        self.turma.instrutor = None
        self.assertEqual(cabecalho_lista_presenca(self.turma)["instrutor"], "a definir")

    def test_ct_his_005_endpoint_devolve_pdf_para_download(self):
        resposta = self.client.get("/cursos-cipa/%s/lista-presenca/" % self.turma.id)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn(
            'filename="lista-presenca-cipa-2026-09-15-sala_reuniao.pdf"',
            resposta["Content-Disposition"],
        )
        self.assertEqual(resposta["Access-Control-Expose-Headers"], "Content-Disposition")
        self.assertTrue(resposta.content.startswith(b"%PDF-"))
        self.assertGreater(len(resposta.content), 2000)

    def test_ct_his_005_disponivel_para_turma_vazia_e_futura(self):
        """É para levar impressa: existe antes do curso e mesmo sem inscritos."""
        vazia = TurmaCipa.objects.create(
            local=local_por_codigo(AUDITORIO), data=date(2026, 12, 20), criado_por=self.operador
        )

        resposta = self.client.get("/cursos-cipa/%s/lista-presenca/" % vazia.id)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.content.startswith(b"%PDF-"))

    def test_ct_his_005_exige_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        resposta = self.client.get("/cursos-cipa/%s/lista-presenca/" % self.turma.id)

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)


class PresencaTests(CipaTestBase):
    """CT-HIS-006: presença em lote, com auditoria, e turma realizada por inferência."""

    def setUp(self):
        super().setUp()
        # Turma de um dia que já passou: presença é fato do dia (PA-009).
        self.ontem = timezone.localdate() - timedelta(days=1)
        self.turma = TurmaCipa.objects.create(
            local=local_por_codigo(AUDITORIO), data=self.ontem, instrutor=instrutor_por_codigo("FELIPE"), criado_por=self.operador
        )
        self.a = InscricaoCipa.objects.create(
            turma=self.turma, nome="Ana", cpf=cpf_sintetico(1), **dados_vinculo()
        )
        self.b = InscricaoCipa.objects.create(
            turma=self.turma, nome="Bruno", cpf=cpf_sintetico(2), **dados_vinculo()
        )
        self.c = InscricaoCipa.objects.create(
            turma=self.turma, nome="Carla", cpf=cpf_sintetico(3), **dados_vinculo()
        )
        self.url = f"/cursos-cipa/{self.turma.id}/presenca/"

    def lote(self, *pares):
        return {"presencas": [{"inscricao_id": i.id, "presente": p} for i, p in pares]}

    def test_ct_his_006_lote_grava_presente_ausente_com_auditoria_e_realiza_a_turma(self):
        resposta = self.client.post(
            self.url, self.lote((self.a, True), (self.b, False)), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.a.refresh_from_db(); self.b.refresh_from_db(); self.c.refresh_from_db()
        self.assertIs(self.a.presenca, True)
        self.assertIs(self.b.presenca, False)
        self.assertIsNone(self.c.presenca)  # não veio no lote: segue sem registro
        self.assertEqual(self.a.presenca_registrada_por, self.operador)
        self.assertIsNotNone(self.a.presenca_registrada_em)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.status, "realizada")
        # A resposta é a turma completa, com as contagens que a tela usa.
        self.assertEqual(resposta.data["status"], "realizada")
        self.assertEqual(resposta.data["presentes"], 1)
        self.assertEqual(resposta.data["ausentes"], 1)
        self.assertEqual(resposta.data["sem_registro"], 1)
        por_id = {i["id"]: i for i in resposta.data["inscricoes"]}
        self.assertIs(por_id[self.a.id]["presenca"], True)
        self.assertEqual(por_id[self.a.id]["presenca_registrada_por_nome"], self.operador.email)
        self.assertIsNone(por_id[self.c.id]["presenca"])

    def test_ct_his_006_inscricao_de_outra_turma_recusa_o_lote_inteiro(self):
        outra = TurmaCipa.objects.create(local=local_por_codigo(SALA_REUNIAO), data=self.ontem, criado_por=self.operador)
        estranho = InscricaoCipa.objects.create(
            turma=outra, nome="Zé", cpf=cpf_sintetico(9), **dados_vinculo()
        )

        resposta = self.client.post(
            self.url, self.lote((self.a, True), (estranho, True)), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("1", resposta.data["presencas"])  # aponta o índice do lote
        self.a.refresh_from_db()
        self.assertIsNone(self.a.presenca)  # nada gravado
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.status, "agendada")

    def test_ct_his_006_regravar_e_aceito_e_atualiza_a_auditoria(self):
        self.client.post(self.url, self.lote((self.a, False)), format="json")
        self.a.refresh_from_db()
        primeira = self.a.presenca_registrada_em

        self.client.force_authenticate(self.admin)
        resposta = self.client.post(self.url, self.lote((self.a, True)), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.a.refresh_from_db()
        self.assertIs(self.a.presenca, True)
        self.assertEqual(self.a.presenca_registrada_por, self.admin)
        self.assertGreaterEqual(self.a.presenca_registrada_em, primeira)

    def test_ct_his_006_turma_cancelada_recusa(self):
        self.turma.status = "cancelada"
        self.turma.save()

        resposta = self.client.post(self.url, self.lote((self.a, True)), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cancelada", resposta.data["detail"])

    def test_ct_his_006_turma_futura_recusa(self):
        futura = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO),
            data=timezone.localdate() + timedelta(days=1),
            criado_por=self.operador,
        )
        inscrito = InscricaoCipa.objects.create(
            turma=futura, nome="Dora", cpf=cpf_sintetico(4), **dados_vinculo()
        )

        resposta = self.client.post(
            f"/cursos-cipa/{futura.id}/presenca/", self.lote((inscrito, True)), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("a partir do dia da turma", resposta.data["detail"])
        futura.refresh_from_db()
        self.assertEqual(futura.status, "agendada")

    def test_ct_his_006_turma_do_proprio_dia_aceita(self):
        hoje = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO), data=timezone.localdate(), criado_por=self.operador
        )
        inscrito = InscricaoCipa.objects.create(
            turma=hoje, nome="Eva", cpf=cpf_sintetico(5), **dados_vinculo()
        )

        resposta = self.client.post(
            f"/cursos-cipa/{hoje.id}/presenca/", self.lote((inscrito, True)), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)

    def test_ct_his_006_lote_vazio_ou_repetido_da_400(self):
        vazio = self.client.post(self.url, {"presencas": []}, format="json")
        repetido = self.client.post(
            self.url, self.lote((self.a, True), (self.a, False)), format="json"
        )

        self.assertEqual(vazio.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(repetido.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ct_his_006_contagens_aparecem_na_turma_no_historico_e_nos_participantes(self):
        self.client.post(self.url, self.lote((self.a, True), (self.b, False)), format="json")

        turma = self.client.get(f"/cursos-cipa/{self.turma.id}/")
        historico = self.client.get(
            "/cursos-cipa/historico/",
            {"data_inicio": self.ontem.isoformat(), "data_fim": self.ontem.isoformat()},
        )
        participantes = self.client.get("/cursos-cipa/participantes/", {"cpf": self.a.cpf})

        self.assertEqual((turma.data["presentes"], turma.data["ausentes"], turma.data["sem_registro"]), (1, 1, 1))
        linha = next(t for t in historico.data["results"] if t["id"] == self.turma.id)
        self.assertEqual(linha["presentes"], 1)
        self.assertNotIn("inscricoes", linha)
        self.assertIs(participantes.data["results"][0]["presenca"], True)

    def test_ct_his_006_inscrito_novo_em_turma_realizada_nasce_sem_registro(self):
        self.client.post(self.url, self.lote((self.a, True)), format="json")

        resposta = self.client.post(
            f"/cursos-cipa/{self.turma.id}/inscricoes/",
            {"nome": "Extra", "cpf": cpf_sintetico(6), **dados_vinculo()},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertIsNone(resposta.data["presenca"])

    def test_ct_his_006_presenca_nao_muda_por_patch_na_inscricao(self):
        resposta = self.client.patch(
            f"/cursos-cipa/{self.turma.id}/inscricoes/{self.a.id}/",
            {"presenca": True},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.a.refresh_from_db()
        self.assertIsNone(self.a.presenca)  # campo é só leitura fora do lote

    def test_ct_his_006_exige_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        resposta = self.client.post(self.url, self.lote((self.a, True)), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)


def png_minusculo(largura=8, altura=4):
    """PNG válido gerado na hora (Pillow), para o upload da assinatura nos testes."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (largura, altura), "black").save(buffer, format="PNG")
    return SimpleUploadedFile("assinatura.png", buffer.getvalue(), content_type="image/png")


class CadastrosCipaTests(CipaTestBase):
    """CT-CIP-021..023 (`specs/curso-cipa-cadastros/`): palestrantes e locais editáveis."""

    # ---- migração / semente -------------------------------------------------

    def test_ct_cip_021_semente_preserva_os_dois_instrutores_e_as_assinaturas(self):
        felipe = instrutor_por_codigo("FELIPE")
        vinicius = instrutor_por_codigo("VINICIUS")

        self.assertEqual(felipe.registro, "MTE/RJ 0060169")
        self.assertEqual(vinicius.registro, "MTE/RJ 0056876")
        self.assertTrue(felipe.tem_assinatura)
        self.assertTrue(vinicius.tem_assinatura)

    def test_ct_cip_022_semente_preserva_os_dois_locais_e_a_marca_da_sala(self):
        auditorio = local_por_codigo(AUDITORIO)
        sala = local_por_codigo(SALA_REUNIAO)

        self.assertEqual((auditorio.capacidade, auditorio.compartilha_sala_reuniao), (30, False))
        self.assertEqual((sala.capacidade, sala.compartilha_sala_reuniao), (10, True))
        self.assertEqual(sala.unidade_dados["cidade"], "Rio de Janeiro")

    # ---- instrutores --------------------------------------------------------

    def test_ct_cip_021_cria_palestrante_com_assinatura_e_lista_sem_expor_o_arquivo(self):
        resposta = self.client.post(
            "/cursos-cipa/instrutores/",
            {"nome": "Nova Palestrante", "registro_mte": "0099999", "registro_uf": "rj",
             "assinatura": png_minusculo()},
            format="multipart",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(resposta.data["codigo"], "NOVA_PALESTRANTE")
        self.assertEqual(resposta.data["registro"], "MTE/RJ 0099999")
        self.assertEqual(resposta.data["titulo"], "Técnico em Segurança no Trabalho")
        self.assertTrue(resposta.data["tem_assinatura"])
        self.assertNotIn("assinatura", resposta.data)
        lista = self.client.get("/cursos-cipa/instrutores/")
        self.assertIn("NOVA_PALESTRANTE", {i["codigo"] for i in lista.data})

    def test_ct_cip_021_palestrante_sem_assinatura_e_aceito_e_pode_recebe_la_depois(self):
        criado = self.client.post(
            "/cursos-cipa/instrutores/",
            {"nome": "Sem Assinatura", "registro_mte": "0011111", "registro_uf": "SP"},
            format="json",
        )
        self.assertEqual(criado.status_code, status.HTTP_201_CREATED, criado.data)
        self.assertFalse(criado.data["tem_assinatura"])

        editado = self.client.patch(
            f"/cursos-cipa/instrutores/{criado.data['id']}/",
            {"assinatura": png_minusculo()},
            format="multipart",
        )

        self.assertEqual(editado.status_code, status.HTTP_200_OK, editado.data)
        self.assertTrue(editado.data["tem_assinatura"])

    def test_ct_cip_021_registro_mte_repetido_na_mesma_uf_da_400(self):
        resposta = self.client.post(
            "/cursos-cipa/instrutores/",
            {"nome": "Outro Felipe", "registro_mte": "0060169", "registro_uf": "RJ"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("registro_mte", resposta.data)

    def test_ct_cip_021_assinatura_grande_ou_nao_imagem_da_400(self):
        grande = SimpleUploadedFile("a.png", b"x" * (500 * 1024 + 1), content_type="image/png")
        resposta = self.client.post(
            "/cursos-cipa/instrutores/",
            {"nome": "Pesada", "registro_mte": "0022222", "registro_uf": "RJ", "assinatura": grande},
            format="multipart",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assinatura", resposta.data)

    def test_ct_cip_021_excluir_com_turma_da_400_e_desativar_tira_da_lista_mas_nao_da_turma(self):
        felipe = instrutor_por_codigo("FELIPE")
        turma = TurmaCipa.objects.create(
            local=local_por_codigo(AUDITORIO), data=DIA, instrutor=felipe, criado_por=self.operador
        )

        excluir = self.client.delete(f"/cursos-cipa/instrutores/{felipe.id}/")
        self.assertEqual(excluir.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Desative", excluir.data["detail"])

        desativar = self.client.patch(
            f"/cursos-cipa/instrutores/{felipe.id}/", {"ativo": False}, format="json"
        )
        self.assertEqual(desativar.status_code, status.HTTP_200_OK)

        ativos = {i["codigo"] for i in self.client.get("/cursos-cipa/instrutores/").data}
        todos = {i["codigo"] for i in self.client.get("/cursos-cipa/instrutores/", {"todos": 1}).data}
        self.assertNotIn("FELIPE", ativos)
        self.assertIn("FELIPE", todos)
        # A turma antiga segue apontando para ele e continua legível.
        detalhe = self.client.get(f"/cursos-cipa/{turma.id}/")
        self.assertEqual(detalhe.data["instrutor"], "FELIPE")
        self.assertEqual(detalhe.data["instrutor_nome"], "Felipe Barboza de Oliveira")
        # Mas turma nova não pode escolhê-lo.
        nova = self.client.post("/cursos-cipa/", dados_turma(instrutor="FELIPE"), format="json")
        self.assertEqual(nova.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("instrutor", nova.data)

    def test_ct_cip_021_excluir_sem_turma_e_permitido(self):
        criado = self.client.post(
            "/cursos-cipa/instrutores/",
            {"nome": "Temporario", "registro_mte": "0033333", "registro_uf": "RJ"},
            format="json",
        )

        resposta = self.client.delete(f"/cursos-cipa/instrutores/{criado.data['id']}/")

        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

    # ---- locais -------------------------------------------------------------

    def test_ct_cip_022_cria_local_e_ele_aparece_para_turma_nova(self):
        resposta = self.client.post(
            "/cursos-cipa/locais/",
            {"nome": "Sala 2", "predio": "Anexo", "capacidade": 12},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(resposta.data["codigo"], "SALA_2")
        self.assertEqual(resposta.data["unidade"]["nome"], "CondoMed Rio")
        self.assertFalse(resposta.data["compartilha_sala_reuniao"])

        turma = self.client.post("/cursos-cipa/", dados_turma(local="SALA_2"), format="json")
        self.assertEqual(turma.status_code, status.HTTP_201_CREATED, turma.data)
        self.assertEqual(turma.data["local_nome"], "Sala 2")
        self.assertEqual(turma.data["capacidade"], 12)
        self.assertIsNone(turma.data["tem_espelho"])  # não é a sala da agenda

    def test_ct_cip_022_nome_repetido_capacidade_zero_e_segunda_sala_da_agenda_dao_400(self):
        repetido = self.client.post(
            "/cursos-cipa/locais/", {"nome": "auditório", "capacidade": 5}, format="json"
        )
        zero = self.client.post(
            "/cursos-cipa/locais/", {"nome": "Vazio", "capacidade": 0}, format="json"
        )
        segunda_sala = self.client.post(
            "/cursos-cipa/locais/",
            {"nome": "Sala B", "capacidade": 8, "compartilha_sala_reuniao": True},
            format="json",
        )

        self.assertEqual(repetido.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nome", repetido.data)
        self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(segunda_sala.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("compartilha_sala_reuniao", segunda_sala.data)

    def test_ct_cip_022_capacidade_alterada_reflete_no_acima_da_capacidade(self):
        sala = local_por_codigo(SALA_REUNIAO)
        turma = TurmaCipa.objects.create(local=sala, data=DIA, criado_por=self.operador)
        for i in range(3):
            InscricaoCipa.objects.create(
                turma=turma, nome=f"P{i}", cpf=cpf_sintetico(i + 1), **dados_vinculo()
            )

        self.client.patch(f"/cursos-cipa/locais/{sala.id}/", {"capacidade": 2}, format="json")

        detalhe = self.client.get(f"/cursos-cipa/{turma.id}/")
        self.assertEqual(detalhe.data["capacidade"], 2)
        self.assertEqual(detalhe.data["acima_da_capacidade"], 1)

    def test_ct_cip_022_espelho_na_agenda_segue_a_marca_do_local(self):
        resposta = self.client.post("/cursos-cipa/", dados_turma(local=SALA_REUNIAO), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resposta.data["tem_espelho"])
        self.assertEqual(Reserva.objects.count(), 1)
        self.assertIn("Sala de reunião", Reserva.objects.get().tema)

    def test_ct_cip_022_excluir_com_turma_da_400_e_desativado_sai_das_opcoes(self):
        auditorio = local_por_codigo(AUDITORIO)
        TurmaCipa.objects.create(local=auditorio, data=DIA, criado_por=self.operador)

        excluir = self.client.delete(f"/cursos-cipa/locais/{auditorio.id}/")
        self.assertEqual(excluir.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.patch(f"/cursos-cipa/locais/{auditorio.id}/", {"ativo": False}, format="json")
        ativos = {l["codigo"] for l in self.client.get("/cursos-cipa/locais/").data}
        self.assertNotIn(AUDITORIO, ativos)
        nova = self.client.post("/cursos-cipa/", dados_turma(local=AUDITORIO, data="2026-10-01"), format="json")
        self.assertEqual(nova.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("local", nova.data)
        # O histórico continua listando a turma antiga com o nome do local.
        historico = self.client.get("/cursos-cipa/historico/", {"local": AUDITORIO})
        self.assertEqual(historico.data["count"], 1)
        self.assertEqual(historico.data["results"][0]["local_nome"], "Auditório")

    # ---- contrato e acesso --------------------------------------------------

    def test_ct_cip_023_contrato_continua_por_codigo_e_local_invalido_da_400(self):
        ok = self.client.post("/cursos-cipa/", dados_turma(instrutor="VINICIUS"), format="json")
        invalido = self.client.post("/cursos-cipa/", dados_turma(local="NAO_EXISTE"), format="json")

        self.assertEqual(ok.status_code, status.HTTP_201_CREATED, ok.data)
        self.assertEqual(ok.data["local"], AUDITORIO)
        self.assertEqual(ok.data["instrutor"], "VINICIUS")
        self.assertEqual(invalido.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("local", invalido.data)

    def test_ct_cip_023_cadastros_exigem_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        locais = self.client.get("/cursos-cipa/locais/")
        instrutores = self.client.post(
            "/cursos-cipa/instrutores/", {"nome": "X", "registro_mte": "1", "registro_uf": "RJ"}, format="json"
        )

        self.assertEqual(locais.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(instrutores.status_code, status.HTTP_403_FORBIDDEN)

    def test_ct_cip_023_usuario_condomed_cadastra(self):
        # PA-010: quem cadastra é o próprio nível condomed (self.operador), não só admin.
        resposta = self.client.post(
            "/cursos-cipa/locais/", {"nome": "Sala Condomed", "capacidade": 6}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)


def paginas_do_pdf(conteudo):
    """Páginas de um PDF sem compressão: objetos /Type /Page, descontando o /Pages."""
    return conteudo.count(b"/Type /Page") - conteudo.count(b"/Type /Pages")


class CertificadoTests(CipaTestBase):
    """CT-HIS-007 (emissão em lote) e CT-HIS-008 (PDF e reemissão)."""

    CNPJ = "11222333000181"

    def setUp(self):
        super().setUp()
        self.ontem = timezone.localdate() - timedelta(days=1)
        self.felipe = instrutor_por_codigo("FELIPE")
        self.turma = TurmaCipa.objects.create(
            local=local_por_codigo(AUDITORIO), data=self.ontem, instrutor=self.felipe, criado_por=self.operador
        )
        vinc = dados_vinculo(condominio_cnpj=self.CNPJ)
        self.a = InscricaoCipa.objects.create(turma=self.turma, nome="Ana Apta", cpf=cpf_sintetico(1), **vinc)
        self.b = InscricaoCipa.objects.create(turma=self.turma, nome="Bruno Apto", cpf=cpf_sintetico(2), **vinc)
        self.sem_cnpj = InscricaoCipa.objects.create(
            turma=self.turma, nome="Carla Sem CNPJ", cpf=cpf_sintetico(3), **dados_vinculo()
        )
        self.ausente = InscricaoCipa.objects.create(turma=self.turma, nome="Dora Ausente", cpf=cpf_sintetico(4), **vinc)
        self.sem_registro = InscricaoCipa.objects.create(turma=self.turma, nome="Eva Sem Registro", cpf=cpf_sintetico(5), **vinc)
        self.url = f"/cursos-cipa/{self.turma.id}/certificados/"

    def marcar_presenca(self):
        self.client.post(
            f"/cursos-cipa/{self.turma.id}/presenca/",
            {"presencas": [
                {"inscricao_id": self.a.id, "presente": True},
                {"inscricao_id": self.b.id, "presente": True},
                {"inscricao_id": self.sem_cnpj.id, "presente": True},
                {"inscricao_id": self.ausente.id, "presente": False},
            ]},
            format="json",
        )

    # ---- CT-HIS-007: emissão --------------------------------------------------

    def test_ct_his_007_emite_so_presentes_aptos_e_lista_impedidos(self):
        self.marcar_presenca()

        resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        emitidos = {c["inscricao_id"] for c in resposta.data["emitidos"]}
        self.assertEqual(emitidos, {self.a.id, self.b.id})
        self.assertEqual(resposta.data["ja_existentes"], [])
        self.assertEqual([i["inscricao_id"] for i in resposta.data["impedidos"]], [self.sem_cnpj.id])
        self.assertIn("CNPJ", resposta.data["impedidos"][0]["motivo"])
        self.assertEqual(CertificadoCipa.objects.count(), 2)
        self.assertFalse(CertificadoCipa.objects.filter(inscricao__in=[self.ausente, self.sem_registro]).exists())
        # Número: ano da turma + sequencial de 6 dígitos; código de verificação presente.
        numeros = sorted(c["numero"] for c in resposta.data["emitidos"])
        ano = self.ontem.year
        self.assertEqual(numeros, [f"CIPA-{ano}-000001", f"CIPA-{ano}-000002"])
        self.assertTrue(all(len(c["codigo_verificacao"]) == 36 for c in resposta.data["emitidos"]))
        # Contagens na turma devolvida e no GET.
        self.assertEqual(resposta.data["turma"]["certificados_emitidos"], 2)
        self.assertEqual(resposta.data["turma"]["aptos_sem_certificado"], 0)
        self.assertEqual(resposta.data["turma"]["presentes_sem_cnpj"], 1)
        detalhe = self.client.get(f"/cursos-cipa/{self.turma.id}/")
        por_id = {i["id"]: i for i in detalhe.data["inscricoes"]}
        self.assertEqual(por_id[self.a.id]["certificado"]["numero"], f"CIPA-{ano}-000001")
        self.assertIsNone(por_id[self.sem_cnpj.id]["certificado"])

    def test_ct_his_007_idempotente_e_emite_o_impedido_depois_de_corrigir_o_cnpj(self):
        self.marcar_presenca()
        self.client.post(self.url)

        de_novo = self.client.post(self.url)
        self.assertEqual(de_novo.status_code, status.HTTP_200_OK)
        self.assertEqual(de_novo.data["emitidos"], [])
        self.assertEqual(len(de_novo.data["ja_existentes"]), 2)
        self.assertEqual(CertificadoCipa.objects.count(), 2)

        self.client.patch(
            f"/cursos-cipa/{self.turma.id}/inscricoes/{self.sem_cnpj.id}/",
            {"condominio_cnpj": self.CNPJ}, format="json",
        )
        terceira = self.client.post(self.url)
        self.assertEqual([c["inscricao_id"] for c in terceira.data["emitidos"]], [self.sem_cnpj.id])
        self.assertEqual(terceira.data["emitidos"][0]["numero"], f"CIPA-{self.ontem.year}-000003")
        self.assertEqual(terceira.data["impedidos"], [])

    def test_ct_his_007_sem_presenca_registrada_recusa(self):
        resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("presença", resposta.data["detail"])

    def test_ct_his_007_sem_instrutor_ou_sem_assinatura_recusa_o_lote_inteiro(self):
        self.marcar_presenca()
        self.turma.instrutor = None
        self.turma.save()
        sem_instrutor = self.client.post(self.url)

        sem_assinatura = InstrutorCipa.objects.create(
            codigo="SEM_ASS", nome="Sem Assinatura", registro_mte="1", registro_uf="RJ"
        )
        self.turma.instrutor = sem_assinatura
        self.turma.save()
        sem_ass = self.client.post(self.url)

        self.assertEqual(sem_instrutor.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("instrutor", sem_instrutor.data["detail"].lower())
        self.assertEqual(sem_ass.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assinatura", sem_ass.data["detail"])
        self.assertEqual(CertificadoCipa.objects.count(), 0)

    def test_ct_his_007_turma_cancelada_recusa(self):
        self.marcar_presenca()
        TurmaCipa.objects.filter(pk=self.turma.pk).update(status="cancelada")

        resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ct_his_007_sequencial_e_por_ano_da_turma(self):
        self.marcar_presenca()
        self.client.post(self.url)
        ano_passado = self.ontem.replace(year=self.ontem.year - 1)
        antiga = TurmaCipa.objects.create(
            local=local_por_codigo(SALA_REUNIAO), data=ano_passado, instrutor=self.felipe, criado_por=self.operador
        )
        inscrito = InscricaoCipa.objects.create(
            turma=antiga, nome="Zé Antigo", cpf=cpf_sintetico(9), **dados_vinculo(condominio_cnpj=self.CNPJ)
        )
        self.client.post(f"/cursos-cipa/{antiga.id}/presenca/", {"presencas": [{"inscricao_id": inscrito.id, "presente": True}]}, format="json")

        resposta = self.client.post(f"/cursos-cipa/{antiga.id}/certificados/")

        self.assertEqual(resposta.data["emitidos"][0]["numero"], f"CIPA-{ano_passado.year}-000001")

    def test_ct_his_007_turma_e_inscricao_com_certificado_sao_intocaveis(self):
        self.marcar_presenca()
        self.client.post(self.url)

        excluir_turma = self.client.delete(f"/cursos-cipa/{self.turma.id}/")
        cancelar = self.client.patch(f"/cursos-cipa/{self.turma.id}/", {"status": "cancelada"}, format="json")
        excluir_inscrito = self.client.delete(f"/cursos-cipa/{self.turma.id}/inscricoes/{self.a.id}/")
        excluir_sem_certificado = self.client.delete(f"/cursos-cipa/{self.turma.id}/inscricoes/{self.sem_registro.id}/")

        self.assertEqual(excluir_turma.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cancelar.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", cancelar.data)
        self.assertEqual(excluir_inscrito.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(excluir_sem_certificado.status_code, status.HTTP_204_NO_CONTENT)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.status, "realizada")
        self.assertTrue(TurmaCipa.objects.filter(pk=self.turma.pk).exists())

    def test_ct_his_007_historico_traz_as_contagens_de_certificado(self):
        self.marcar_presenca()
        self.client.post(self.url)

        historico = self.client.get(
            "/cursos-cipa/historico/",
            {"data_inicio": self.ontem.isoformat(), "data_fim": self.ontem.isoformat()},
        )

        linha = historico.data["results"][0]
        self.assertEqual(linha["certificados_emitidos"], 2)
        self.assertEqual(linha["presentes_sem_cnpj"], 1)

    def test_ct_his_007_exige_nivel_autorizado(self):
        self.client.force_authenticate(self.comum)

        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_403_FORBIDDEN)

    # ---- CT-HIS-008: PDF ------------------------------------------------------

    def test_ct_his_008_pdf_da_turma_tem_frente_e_verso_por_certificado(self):
        self.marcar_presenca()
        self.client.post(self.url)

        resposta = self.client.get(f"/cursos-cipa/{self.turma.id}/certificados/pdf/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertEqual(
            resposta["Content-Disposition"], f'attachment; filename="certificados-{self.turma.codigo}.pdf"'
        )
        self.assertEqual(resposta["Access-Control-Expose-Headers"], "Content-Disposition")
        pdf = resposta.content
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(paginas_do_pdf(pdf), 4)  # 2 certificados x (frente + verso)
        self.assertIn(b"Ana Apta", pdf)
        self.assertIn(b"Bruno Apto", pdf)
        self.assertIn(f"CIPA-{self.ontem.year}-000001".encode(), pdf)
        self.assertIn(b"FELIPE BARBOZA DE OLIVEIRA", pdf)
        self.assertIn(b"CONDOMED RIO", pdf)

    def test_ct_his_008_pdf_individual_pelo_numero_reflete_a_inscricao_corrigida(self):
        self.marcar_presenca()
        numero = self.client.post(self.url).data["emitidos"][0]["numero"]
        certificado = CertificadoCipa.objects.get(numero=numero)
        self.client.patch(
            f"/cursos-cipa/{self.turma.id}/inscricoes/{certificado.inscricao_id}/",
            {"nome": "Nome Corrigido"}, format="json",
        )

        resposta = self.client.get(f"/certificados/{numero}/pdf/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta["Content-Disposition"], f'attachment; filename="certificado-{numero}.pdf"')
        self.assertEqual(paginas_do_pdf(resposta.content), 2)
        self.assertIn(b"Nome Corrigido", resposta.content)
        self.assertIn(numero.encode(), resposta.content)
        certificado.refresh_from_db()
        self.assertEqual(certificado.numero, numero)  # número não muda com a correção

    def test_ct_his_008_sem_certificado_da_404(self):
        self.marcar_presenca()

        turma = self.client.get(f"/cursos-cipa/{self.turma.id}/certificados/pdf/")
        inexistente = self.client.get("/certificados/CIPA-2026-999999/pdf/")

        self.assertEqual(turma.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(inexistente.status_code, status.HTTP_404_NOT_FOUND)

    def test_ct_his_008_pdf_exige_nivel_autorizado(self):
        self.marcar_presenca()
        numero = self.client.post(self.url).data["emitidos"][0]["numero"]
        self.client.force_authenticate(self.comum)

        self.assertEqual(self.client.get(f"/certificados/{numero}/pdf/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.get(f"/cursos-cipa/{self.turma.id}/certificados/pdf/").status_code, status.HTTP_403_FORBIDDEN
        )
