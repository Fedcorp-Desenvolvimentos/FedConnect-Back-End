# condomed/services.py
"""Regras de conflito e espelho da turma CIPA na agenda atual (ADR-0001)."""
from datetime import datetime

from agenda.models import Reserva

from .models import DURACAO_MINUTOS, TurmaCipa

STATUS_ATIVOS = ("agendada", "realizada")


def _minutos(hora):
    return hora.hour * 60 + hora.minute


def _intervalo_reserva(reserva):
    """Início e fim da reserva em minutos; None se o horário estiver malformado."""
    try:
        inicio = datetime.strptime(reserva.horario.strip(), "%H:%M")
    except (ValueError, AttributeError):
        return None
    inicio_min = inicio.hour * 60 + inicio.minute
    return inicio_min, inicio_min + (reserva.duracao or 0)


def turma_conflitante(local, data, hora_inicio, hora_fim, excluir_id=None):
    """Turma ativa no mesmo local/dia com intervalo sobreposto (INV-CIP-001)."""
    qs = TurmaCipa.objects.filter(
        local=local,
        data=data,
        status__in=STATUS_ATIVOS,
        hora_inicio__lt=hora_fim,
        hora_fim__gt=hora_inicio,
    )
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return qs.first()


def reserva_conflitante(data, hora_inicio, hora_fim, excluir_reserva_id=None):
    """Reserva da agenda atual que sobrepõe o intervalo na sala de reunião (RF-CIP-002)."""
    inicio = _minutos(hora_inicio)
    fim = _minutos(hora_fim)
    qs = Reserva.objects.filter(data=data)
    if excluir_reserva_id:
        qs = qs.exclude(pk=excluir_reserva_id)
    for reserva in qs:
        intervalo = _intervalo_reserva(reserva)
        if intervalo is None:
            continue
        r_inicio, r_fim = intervalo
        if r_inicio < fim and r_fim > inicio:
            return reserva
    return None


def criar_reserva_espelho(turma, usuario):
    """Cria a Reserva espelho da turma na sala de reunião (INV-CIP-002).

    Chamado dentro de transaction.atomic() pela view.
    """
    return Reserva.objects.create(
        tema=f"Curso CIPA — {turma.local.nome}",
        participantes="Curso CIPA (Condomed)",
        data=turma.data,
        horario=turma.hora_inicio.strftime("%H:%M"),
        duracao=DURACAO_MINUTOS,
        criado_por=usuario,
    )


def sincronizar_espelho(turma, usuario):
    """Garante que a turma tenha (ou não) espelho conforme local e status."""
    precisa_espelho = turma.local.compartilha_sala_reuniao and turma.status in STATUS_ATIVOS
    if precisa_espelho and turma.reserva_sala is None:
        turma.reserva_sala = criar_reserva_espelho(turma, usuario)
        turma.save(update_fields=["reserva_sala"])
    elif not precisa_espelho and turma.reserva_sala is not None:
        remover_espelho(turma)
    elif precisa_espelho:
        reserva = turma.reserva_sala
        reserva.data = turma.data
        reserva.horario = turma.hora_inicio.strftime("%H:%M")
        reserva.tema = f"Curso CIPA — {turma.local.nome}"
        reserva.save(update_fields=["data", "horario", "tema"])
    return turma.reserva_sala


def remover_espelho(turma):
    """Remove a Reserva espelho, se houver (INV-CIP-002)."""
    reserva = turma.reserva_sala
    if reserva is None:
        return
    turma.reserva_sala = None
    turma.save(update_fields=["reserva_sala"])
    reserva.delete()


def capacidade_do_local(local):
    """Mantida por compatibilidade com quem chama; a capacidade é do registro."""
    return local.capacidade


def sala_compartilhada_em_uso(excluir_id=None):
    """Há outro local ativo marcado como a sala da agenda? (RF-CIP-007: no máximo um.)"""
    from .models import LocalCipa

    qs = LocalCipa.objects.filter(ativo=True, compartilha_sala_reuniao=True)
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return qs.exists()


# ---------------------------------------------------------------------------
# Presença (RF-HIS-004). Regras aqui, fora da view, para o teste cobrir a regra
# e não o transporte.
# ---------------------------------------------------------------------------

def validar_turma_para_presenca(turma, hoje=None):
    """Devolve a mensagem que impede registrar presença nesta turma, ou None.

    Cancelada não recebe presença (não houve curso). Antes da data também não
    (PA-009): presença é fato do dia; marcar antes só produz registro falso.
    """
    from django.utils import timezone

    hoje = hoje or timezone.localdate()
    if turma.status == "cancelada":
        return "Turma cancelada não recebe presença."
    if turma.data > hoje:
        return (
            "A presença só pode ser registrada a partir do dia da turma "
            f"({turma.data.strftime('%d/%m/%Y')})."
        )
    return None


def registrar_presenca(turma, presencas, usuario, hoje=None):
    """Grava presente/ausente em lote, com auditoria, e realiza a turma.

    `presencas`: lista de dicts já validados `{inscricao_id, presente}`.
    Ou grava todas, ou nenhuma. A primeira gravação (e qualquer outra) deixa a
    turma `realizada` — a situação é inferida da presença, não digitada.
    Devolve um dict de erros por índice quando alguma inscrição não é da turma;
    nesse caso nada foi gravado.
    """
    from django.db import transaction
    from django.utils import timezone

    inscricoes = {inscricao.pk: inscricao for inscricao in turma.inscricoes.all()}
    erros = {}
    for indice, item in enumerate(presencas):
        if item["inscricao_id"] not in inscricoes:
            erros[str(indice)] = {
                "inscricao_id": [
                    f"Inscrição {item['inscricao_id']} não pertence a esta turma."
                ]
            }
    if erros:
        return erros

    agora = timezone.now()
    with transaction.atomic():
        for item in presencas:
            inscricao = inscricoes[item["inscricao_id"]]
            inscricao.presenca = item["presente"]
            inscricao.presenca_registrada_em = agora
            inscricao.presenca_registrada_por = usuario
            inscricao.save(
                update_fields=[
                    "presenca", "presenca_registrada_em", "presenca_registrada_por",
                ]
            )
        if turma.status != "realizada":
            turma.status = "realizada"
            turma.save(update_fields=["status"])
    return {}


# ---------------------------------------------------------------------------
# Certificados (RF-HIS-005). Só presente recebe; um por inscrição; número
# sequencial por ano; emissão parcial quando falta CNPJ (PA-012); turma e
# inscrição com certificado ficam intocáveis (PA-013).
# ---------------------------------------------------------------------------

MOTIVO_SEM_CNPJ = "Sem CNPJ do condomínio — obrigatório para emitir o certificado."


def validar_turma_para_certificado(turma):
    """Mensagem que impede emitir para esta turma, ou None.

    O que impede é o que afeta todos os certificados: turma cancelada, presença
    nunca registrada, instrutor ausente ou sem assinatura (o certificado sai
    assinado ou não sai — PA-008).
    """
    if turma.status == "cancelada":
        return "Turma cancelada não emite certificado."
    contagem = turma.contagem_presenca()
    if contagem["presentes"] + contagem["ausentes"] == 0:
        return "Registre a presença antes de emitir os certificados."
    if turma.instrutor is None:
        return "Defina o instrutor da turma antes de emitir: ele assina o certificado."
    if not turma.instrutor.tem_assinatura:
        return (
            f"O instrutor {turma.instrutor.nome} está sem assinatura digitalizada "
            "cadastrada. Anexe a assinatura em Cadastros e emita de novo."
        )
    return None


def proximo_numero_certificado(ano):
    """CIPA-AAAA-000000, sequencial por ano, sem furo nem repetição.

    Chamado dentro de `transaction.atomic()`: a linha do contador é travada até
    o commit, então dois lotes simultâneos saem em ordem.
    """
    from .models import ContadorCertificado

    contador, _ = ContadorCertificado.objects.select_for_update().get_or_create(ano=ano)
    contador.ultimo += 1
    contador.save(update_fields=["ultimo"])
    return f"CIPA-{ano}-{contador.ultimo:06d}"


def emitir_certificados(turma, usuario):
    """Emite para todo presente apto que ainda não tem; devolve o resultado do lote.

    `{"emitidos": [...], "ja_existentes": [...], "impedidos": [{inscricao_id, nome, motivo}]}`
    Tudo em uma transação; chamar de novo não duplica (ADR-0007). Ausente e
    não registrado nunca entram (PA-007).
    """
    from django.db import transaction

    from .models import CertificadoCipa

    emitidos, ja_existentes, impedidos = [], [], []
    with transaction.atomic():
        for inscricao in turma.inscricoes.all():
            if inscricao.presenca is not True:
                continue
            existente = inscricao.certificado_ou_none
            if existente is not None:
                ja_existentes.append(existente)
                continue
            if not inscricao.condominio_cnpj:
                impedidos.append(
                    {"inscricao_id": inscricao.id, "nome": inscricao.nome, "motivo": MOTIVO_SEM_CNPJ}
                )
                continue
            certificado = CertificadoCipa.objects.create(
                inscricao=inscricao,
                numero=proximo_numero_certificado(turma.data.year),
                emitido_por=usuario,
            )
            emitidos.append(certificado)
    return {"emitidos": emitidos, "ja_existentes": ja_existentes, "impedidos": impedidos}


def motivo_turma_intocavel(turma):
    """PA-013: turma com certificado emitido não se exclui nem se cancela."""
    if turma.tem_certificado:
        return (
            "Esta turma tem certificados emitidos e não pode ser excluída nem cancelada: "
            "o documento está na mão do participante."
        )
    return None
