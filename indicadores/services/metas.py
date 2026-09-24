"""Metas mensais por seguradora × ramo — gravadas NO LAKE (RF-IEX-010; antes RF-IEX-008).

Decisão da gestão em 23/09/2026: a meta mora no lake (`casa_meta_mensal`),
onde o realizado é calculado, para a comparação ter um dono só. Este módulo
deixou de ser dono do dado e virou a porta: cada operação é uma chamada ao
FedHub (`/api/lake/metas`), que grava no lake. O CONTRATO que a tela consome
não mudou — `id, seguradora, seguradora_nome, ramo, ramo_nome, competencia,
valor_meta, atualizado_em, atualizado_por` — porque o FedHub o devolve pronto
no mesmo formato.

A regra continua a mesma (PA-023): meta sempre em valor, por seguradora × ramo
× competência (dia 1), upsert pela chave, `replicar_meses` repete nos N meses
seguintes. `MetaMensal` (o modelo local) fica no repositório só como histórico
do que foi cadastrado antes da virada; nenhuma leitura nova sai dele.
"""
from datetime import date
from decimal import Decimal

from indicadores.services import fedhub_lake

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


def _nome_ou_email(usuario) -> str | None:
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return None
    return getattr(usuario, "nome_completo", "") or usuario.email


def serializar(meta: dict) -> dict:
    """Linha do contrato de `GET/POST indicadores/metas/`. O FedHub já a devolve
    neste formato; aqui só se garante o conjunto de chaves que o front conhece."""
    return {
        "id": meta["id"],
        "seguradora": meta["seguradora"],
        "seguradora_nome": meta.get("seguradora_nome") or "",
        "ramo": meta["ramo"],
        "ramo_nome": meta.get("ramo_nome") or "",
        "competencia": meta["competencia"],
        "valor_meta": meta["valor_meta"],
        "atualizado_em": meta.get("atualizado_em"),
        "atualizado_por": meta.get("atualizado_por"),
    }


class MetaNaoEncontrada(LookupError):
    """`PUT`/`DELETE` em id inexistente."""


class MetaDuplicada(ValueError):
    """`PUT` mudando a chave para uma combinação que já tem meta no mês."""


class ReferenciaDesconhecida(ValueError):
    """Seguradora ou ramo que o lake não conhece."""


def _traduzir_recusa(erro: fedhub_lake.RecusaDoFedHub):
    if erro.erro == "meta_inexistente":
        return MetaNaoEncontrada("meta não encontrada.")
    if erro.erro == "meta_duplicada":
        return MetaDuplicada(erro.detalhe)
    if erro.erro == "referencia_desconhecida":
        return ReferenciaDesconhecida(erro.detalhe)
    return ValueError(erro.detalhe)


def listar(competencia: date) -> dict:
    """Metas da competência ordenadas por seguradora e ramo, mais a soma (`null` sem nenhuma)."""
    corpo = fedhub_lake.chamar("GET", "metas", params={"competencia": rotulo(competencia)})
    return {
        "competencia": corpo["competencia"],
        "metas": [serializar(m) for m in corpo["metas"]],
        "total_meta": corpo.get("total_meta"),
    }


def metas_da_competencia(competencia: date, ramos=(), seguradoras=()) -> list[dict]:
    """As metas do mês para as agregações, já restritas aos ramos/seguradoras do filtro (vazio = todas)."""
    metas = listar(competencia)["metas"]
    if ramos:
        metas = [m for m in metas if m["ramo"] in set(ramos)]
    if seguradoras:
        metas = [m for m in metas if m["seguradora"] in set(seguradoras)]
    return metas


def gravar(seguradora: str, ramo: str, competencia: date, valor_meta: Decimal, usuario, replicar_meses: int = 0) -> list:
    """Upsert em (seguradora, ramo, competência) e nos `replicar_meses` seguintes; devolve as linhas gravadas."""
    if not 0 <= replicar_meses <= REPLICAR_MAXIMO:
        raise ValueError(f"replicar_meses deve estar entre 0 e {REPLICAR_MAXIMO}.")
    try:
        corpo = fedhub_lake.chamar("POST", "metas", json={
            "seguradora": seguradora, "ramo": ramo, "competencia": rotulo(competencia),
            "valor_meta": str(Decimal(valor_meta).quantize(Decimal("0.01"))),
            "replicar_meses": replicar_meses, "usuario": _nome_ou_email(usuario),
        })
    except fedhub_lake.RecusaDoFedHub as erro:
        raise _traduzir_recusa(erro) from erro
    return [serializar(m) for m in corpo["metas"]]


def atualizar(meta_id: int, seguradora: str, ramo: str, competencia: date, valor_meta: Decimal, usuario) -> dict:
    """Edita **esta** meta, inclusive seguradora, ramo e mês — sem criar outra (pedido do dono, 2026-09-23)."""
    try:
        corpo = fedhub_lake.chamar("PUT", f"metas/{int(meta_id)}", json={
            "seguradora": seguradora, "ramo": ramo, "competencia": rotulo(competencia),
            "valor_meta": str(Decimal(valor_meta).quantize(Decimal("0.01"))),
            "usuario": _nome_ou_email(usuario),
        })
    except fedhub_lake.RecusaDoFedHub as erro:
        raise _traduzir_recusa(erro) from erro
    return serializar(corpo["metas"][0])


def apagar(meta_id: int) -> None:
    try:
        fedhub_lake.chamar("DELETE", f"metas/{int(meta_id)}")
    except fedhub_lake.RecusaDoFedHub as erro:
        raise _traduzir_recusa(erro) from erro
