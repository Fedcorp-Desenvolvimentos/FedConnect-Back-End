# condomed/exceptions.py
from rest_framework import status
from rest_framework.exceptions import APIException


class ConflitoAgendamento(APIException):
    """Local/dia já ocupado por outra turma ou por uma reserva da agenda (409)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Já existe um agendamento neste local e horário."
    default_code = "conflito_agendamento"

    def __init__(self, detail=None, conflito=None):
        super().__init__({
            "detail": detail or self.default_detail,
            "conflito": conflito or {},
        })
