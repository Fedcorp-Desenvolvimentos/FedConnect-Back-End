# condomed/services.py
"""Regras de conflito e espelho da turma CIPA na agenda atual (ADR-0001)."""
from datetime import datetime

from django.db import connection

from agenda.models import Reserva

from .models import DURACAO_MINUTOS, LOCAIS_CIPA, SALA_REUNIAO, TurmaCipa

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
        tema=f"Curso CIPA — {turma.condominio_nome}",
        participantes="Curso CIPA (Condomed)",
        data=turma.data,
        horario=turma.hora_inicio.strftime("%H:%M"),
        duracao=DURACAO_MINUTOS,
        criado_por=usuario,
    )


def sincronizar_espelho(turma, usuario):
    """Garante que a turma tenha (ou não) espelho conforme local e status."""
    precisa_espelho = turma.local == SALA_REUNIAO and turma.status in STATUS_ATIVOS
    if precisa_espelho and turma.reserva_sala is None:
        turma.reserva_sala = criar_reserva_espelho(turma, usuario)
        turma.save(update_fields=["reserva_sala"])
    elif not precisa_espelho and turma.reserva_sala is not None:
        remover_espelho(turma)
    elif precisa_espelho:
        reserva = turma.reserva_sala
        reserva.data = turma.data
        reserva.horario = turma.hora_inicio.strftime("%H:%M")
        reserva.tema = f"Curso CIPA — {turma.condominio_nome}"
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
    return LOCAIS_CIPA[local]["capacidade"]


def travar_turma(turma_id):
    """Recarrega a turma com lock de linha, para a checagem de capacidade (INV-CIP-003).

    Em produção (PostgreSQL) usa SELECT ... FOR UPDATE; em backends sem suporte
    (SQLite dos testes locais) apenas recarrega — a escrita já é serializada.
    """
    qs = TurmaCipa.objects.all()
    if connection.features.has_select_for_update:
        qs = qs.select_for_update()
    return qs.get(pk=turma_id)
