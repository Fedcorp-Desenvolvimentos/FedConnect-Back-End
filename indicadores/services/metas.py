"""Metas mensais por seguradora × ramo (RF-IEX-008, PA-023, T-IEX-4.2).

A meta é sempre em valor (R$) e vale contra o valor fechado do mês inteiro —
não olha captação nem renovação (decisão do dono em PA-023). Uma linha por
seguradora × ramo × competência (INV-IEX-007): cadastrar de novo a mesma
chave atualiza o valor (upsert). `replicar_meses` repete o mesmo valor nos N
meses seguintes, virando o ano quando preciso.
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from indicadores.models import MetaMensal

REPLICAR_MAXIMO = 11


def competencia_de(texto: str) -> date:
    """`"2026-09"` → `date(2026, 9, 1)`. Fora do formato levanta `ValueError`."""
    partes = texto.split("-")
    if len(partes) != 2 or not (len(partes[0]) == 4 and len(partes[1]) == 2):
        raise ValueError("competencia deve estar no formato AAAA-MM.")
    return date(int(partes[0]), int(partes[1]), 1)


def somar_meses(competencia: date, meses: int) -> date:
    """Dia 1 do mês `meses` adiante (dezembro + 1 → janeiro do ano seguinte)."""
    indice = competencia.year * 12 + (competencia.month - 1) + meses
    return date(indice // 12, indice % 12 + 1, 1)


def rotulo(competencia: date) -> str:
    return f"{competencia.year:04d}-{competencia.month:02d}"


def _decimal_texto(valor) -> str | None:
    return None if valor is None else str(Decimal(valor).quantize(Decimal("0.01")))


def _nome_ou_email(usuario) -> str | None:
    if usuario is None:
        return None
    return getattr(usuario, "nome_completo", "") or usuario.email


def serializar(meta: MetaMensal) -> dict:
    """Linha do contrato de `GET/POST indicadores/metas/` (design, "Metas mensais")."""
    return {
        "id": meta.pk,
        "seguradora": meta.seguradora_id,
        "seguradora_nome": meta.seguradora.nome,
        "ramo": meta.ramo_id,
        "ramo_nome": meta.ramo.nome,
        "competencia": rotulo(meta.competencia),
        "valor_meta": _decimal_texto(meta.valor_meta),
        "atualizado_em": meta.atualizado_em.isoformat() if meta.atualizado_em else None,
        "atualizado_por": _nome_ou_email(meta.atualizado_por),
    }


def listar(competencia: date) -> dict:
    """Metas da competência ordenadas por seguradora e ramo, mais a soma (`null` sem nenhuma)."""
    metas = list(
        MetaMensal.objects.filter(competencia=competencia)
        .select_related("seguradora", "ramo", "atualizado_por")
        .order_by("seguradora_id", "ramo_id")
    )
    total = MetaMensal.objects.filter(competencia=competencia).aggregate(total=Sum("valor_meta"))["total"]
    return {
        "competencia": rotulo(competencia),
        "metas": [serializar(m) for m in metas],
        "total_meta": _decimal_texto(total) if metas else None,
    }


class MetaNaoEncontrada(LookupError):
    """`PUT` em id inexistente."""


class MetaDuplicada(ValueError):
    """`PUT` mudando a chave para uma combinação que já tem meta no mês."""


@transaction.atomic
def atualizar(meta_id: int, seguradora, ramo, competencia: date, valor_meta: Decimal, usuario) -> MetaMensal:
    """Edita **esta** meta, inclusive seguradora, ramo e mês — sem criar outra.

    Pedido do dono em 2026-09-23: editar uma linha e salvar criava uma meta
    nova quando a chave mudava (o `POST` é upsert pela chave). Se a chave nova
    já tem meta, recusa: são duas linhas distintas e cabe ao usuário decidir
    qual fica.
    """
    try:
        meta = MetaMensal.objects.select_for_update().get(pk=meta_id)
    except MetaMensal.DoesNotExist as erro:
        raise MetaNaoEncontrada("meta não encontrada.") from erro
    colisao = (
        MetaMensal.objects.filter(seguradora=seguradora, ramo=ramo, competencia=competencia)
        .exclude(pk=meta.pk)
        .exists()
    )
    if colisao:
        raise MetaDuplicada(
            f"já existe meta para {seguradora.sigla} × {ramo.abreviatura} em {rotulo(competencia)}; "
            "edite aquela ou exclua uma das duas."
        )
    meta.seguradora = seguradora
    meta.ramo = ramo
    meta.competencia = competencia
    meta.valor_meta = valor_meta
    meta.atualizado_por = usuario
    meta.save()
    return MetaMensal.objects.select_related("seguradora", "ramo", "atualizado_por").get(pk=meta.pk)


@transaction.atomic
def gravar(seguradora, ramo, competencia: date, valor_meta: Decimal, usuario, replicar_meses: int = 0) -> list:
    """Upsert em (seguradora, ramo, competência) e nos `replicar_meses` seguintes; devolve as linhas gravadas."""
    if not 0 <= replicar_meses <= REPLICAR_MAXIMO:
        raise ValueError(f"replicar_meses deve estar entre 0 e {REPLICAR_MAXIMO}.")
    gravadas = []
    for deslocamento in range(replicar_meses + 1):
        meta, criada = MetaMensal.objects.update_or_create(
            seguradora=seguradora,
            ramo=ramo,
            competencia=somar_meses(competencia, deslocamento),
            defaults={"valor_meta": valor_meta, "atualizado_por": usuario},
        )
        if criada and usuario is not None:
            meta.criado_por = usuario
            meta.save(update_fields=("criado_por",))
        gravadas.append(meta)
    ids = [m.pk for m in gravadas]
    return list(
        MetaMensal.objects.filter(pk__in=ids)
        .select_related("seguradora", "ramo", "atualizado_por")
        .order_by("competencia", "seguradora_id", "ramo_id")
    )
