"""Espelho do voucher: o que entrou na emissão é o que a consulta devolve.

Spec `consulta-espelho-voucher` (RF-VOU-002..004, ADR-0008). Duas operações:

* `registrar_emissao` — depois que o FedHub gerou o PDF e carimbou o Firebird,
  grava aqui as parcelas que compuseram o documento. É idempotente: reemitir
  ou reutilizar o mesmo número só acrescenta o que faltava.
* `aplicar_espelho` — na consulta por número de voucher, deixa passar apenas
  as linhas do FedHub que estão no registro. Voucher sem registro (emitido
  antes desta spec) passa inteiro, com `espelho=False`, para a tela avisar.

Chave de uma parcela: fatura, favorecido, tipo da comissão, parcela do boleto
e documento — os mesmos campos que identificam a linha na consulta do FedHub.
Favorecido e fatura são comparados sem zeros à esquerda e sem espaços, porque
o Firebird devolve `0000005912` e o payload manda `5912`.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from fedhub.models import VoucherEmitido, VoucherEmitidoItem

logger = logging.getLogger(__name__)


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _codigo(valor: Any) -> str:
    """'0000005912' e '5912' são o mesmo favorecido; '00' continua '00'."""
    t = _texto(valor)
    if t.isdigit():
        return t.lstrip("0") or "0"
    return t


def _decimal(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor if valor not in (None, "") else 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _primeiro(d: Dict[str, Any], *chaves: str) -> Any:
    for k in chaves:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def chave_da_linha(linha: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    """Mesma chave para uma comissão do payload (minúsculas) e uma linha do FedHub (MAIÚSCULAS)."""
    return (
        _codigo(_primeiro(linha, "fatura", "FATURA")),
        _codigo(_primeiro(linha, "favorecido", "favor", "FAVOR")),
        _texto(_primeiro(linha, "tipo", "TIPO") or "BENEFICIO").upper(),
        _codigo(_primeiro(linha, "parcela", "PARCELA")),
        _texto(_primeiro(linha, "documento", "DOCUMENTO")),
    )


@transaction.atomic
def registrar_emissao(
    numero: str,
    tipo_documento: str,
    payload: Dict[str, Any],
    usuario=None,
    resultado: Optional[Dict[str, Any]] = None,
) -> VoucherEmitido:
    """Grava (ou completa) o registro do documento `numero` a partir do payload enviado ao FedHub."""
    numero = _texto(numero)
    if not numero:
        raise ValueError("Documento sem número: nada a registrar.")

    comissoes: List[Dict[str, Any]] = payload.get("comissoes") or []
    resumo = payload.get("resumo") or {}
    primeira = comissoes[0] if comissoes else {}

    voucher, criado = VoucherEmitido.objects.get_or_create(
        numero=numero,
        defaults={
            "tipo_documento": tipo_documento if tipo_documento in ("voucher", "recibo") else "voucher",
            "favorecido": _codigo(_primeiro(primeira, "favorecido", "favor", "FAVOR")),
            "favorecido_nome": _texto(_primeiro(primeira, "favorecido_nome", "NOME"))[:150],
            "empresa_pagadora_nome": _texto(payload.get("empresa_pagadora_nome"))[:150],
            "empresa_pagadora_cnpj": _texto(payload.get("empresa_pagadora_cnpj"))[:20],
            "total_bruto": _decimal(resumo.get("valor_total_bruto")),
            "total_retencoes": _decimal(resumo.get("total_retencoes")),
            "total_liquido": _decimal(resumo.get("valor_liquido_final")),
            "emitido_por": usuario if getattr(usuario, "pk", None) else None,
        },
    )

    existentes = {
        (i.fatura, i.favor, i.tipo, i.parcela, i.documento) for i in voucher.itens.all()
    }
    novos = []
    for c in comissoes:
        chave = chave_da_linha(c)
        if chave in existentes:
            continue
        existentes.add(chave)
        fatura, favor, tipo, parcela, documento = chave
        novos.append(
            VoucherEmitidoItem(
                voucher=voucher,
                fatura=fatura,
                tipo_fat=_texto(_primeiro(c, "tipo_fat", "TIPO_FAT"))[:5],
                favor=favor,
                tipo=tipo[:20],
                parcela=parcela[:10],
                parcela_comissao=_codigo(_primeiro(c, "parcela_comissao", "PARCELA_2"))[:10],
                documento=documento[:20],
                valor=_decimal(_primeiro(c, "valor_comissao", "VALOR", "VALOR_COMISSAO")),
            )
        )
    if novos:
        VoucherEmitidoItem.objects.bulk_create(novos)

    if resultado and resultado.get("reutilizado") and not criado:
        logger.info("Voucher %s reutilizado pelo FedHub: %d parcela(s) acrescentada(s) ao registro", numero, len(novos))
    else:
        logger.info("Voucher %s registrado com %d parcela(s)", numero, len(novos))
    return voucher


def aplicar_espelho(numero: str, linhas: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool, Optional[VoucherEmitido]]:
    """Filtra as linhas do FedHub pelo registro do voucher.

    Devolve `(linhas, espelho, voucher)`. `espelho=True` quando existe registro:
    saem só as parcelas que estavam no documento, na ordem em que o FedHub as
    mandou. Sem registro, as linhas voltam intactas e `espelho=False`.
    """
    numero = _texto(numero)
    linhas = list(linhas)
    voucher = VoucherEmitido.objects.filter(numero=numero).first() if numero else None
    if voucher is None:
        return linhas, False, None

    chaves = {(i.fatura, i.favor, i.tipo, i.parcela, i.documento) for i in voucher.itens.all()}
    filtradas = [l for l in linhas if chave_da_linha(l) in chaves]
    if len(filtradas) != len(chaves):
        # A consulta deixou de trazer alguma parcela do documento (baixa estornada,
        # comissão cancelada no ERP). Não é erro do espelho, mas merece log.
        logger.warning(
            "Voucher %s: registro tem %d parcela(s), consulta devolveu %d delas",
            numero, len(chaves), len(filtradas),
        )
    return filtradas, True, voucher


def marcar_cancelamento(numeros: Iterable[str]) -> int:
    """O FedHub cancela o voucher inteiro; aqui fica a data, e o registro permanece para auditoria."""
    numeros = [_texto(n) for n in numeros if _texto(n)]
    if not numeros:
        return 0
    return VoucherEmitido.objects.filter(numero__in=numeros, cancelado_em__isnull=True).update(
        cancelado_em=timezone.now()
    )
