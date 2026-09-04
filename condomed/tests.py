# condomed/tests.py
"""Cobre CT-CIP-001..013 da matriz de specs/curso-cipa/matriz.csv."""
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from agenda.models import Reserva

from .models import AUDITORIO, SALA_REUNIAO, InscricaoCipa, TurmaCipa
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

    def test_ct_cip_006_inscricao_acima_da_capacidade_entra_e_e_sinalizada(self):
        """Capacidade é referência, não trava (ADR-0006): extra de última hora entra."""
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
            local=SALA_REUNIAO, data=DIA, criado_por=self.operador
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
            local=AUDITORIO, data=date(2026, 6, 10), status="realizada",
            criado_por=self.operador,
        )
        self.recente = TurmaCipa.objects.create(
            local=SALA_REUNIAO, data=date(2026, 9, 15), criado_por=self.operador,
        )
        self.cancelada = TurmaCipa.objects.create(
            local=AUDITORIO, data=date(2026, 9, 20), status="cancelada",
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
