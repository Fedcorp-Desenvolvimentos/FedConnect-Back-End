"""Agregações dos indicadores no banco (RF-IEX-002..005, RF-IEX-007, T-IEX-2.2, T-IEX-2.4).

Primeira agregação com o ORM no repositório (ADR-0009): `Count`, `Sum`,
`Q`-filter em `Count` e `TruncMonth`, tudo numa consulta por Bloco. Nada é
somado em Python linha a linha (RNF-IEX-003). Toda soma monetária sai como
string decimal ao lado da contagem de documentos que a compõem; sem nenhum,
sai `null`, nunca `"0.00"` (INV-IEX-003, PA-019).
"""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from indicadores.models import CargaCorp, Producao, Ramo, Seguradora
from indicadores.services.periodos import Filtros, janelas_padrao

LIMITE_LINHAS = 400
ROTULOS_MES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

# As mesmas expressões servem para `aggregate()` (um Bloco) e para `annotate()`
# agrupado (por seguradora, por dia, por mês). `documento` e `documentonegocio`
# são OneToOne: o LEFT JOIN não multiplica linhas.
EXPRESSOES_BLOCO = {
    "fechados": Count("nosnum"),
    "renovacoes": Count("nosnum", filter=Q(renovacao=True)),
    "captacoes": Count("nosnum", filter=Q(renovacao=False)),
    "com_negocio_origem": Count("documentonegocio"),
    "valor_fechado": Sum("documento__pretot"),
    "documentos_com_valor": Count("documento__pretot"),
    "comissao": Sum("documento__val_c"),
    "documentos_com_comissao": Count("documento__val_c"),
}
CAMPOS_BLOCO = tuple(EXPRESSOES_BLOCO)


def queryset_base(filtros: Filtros):
    """Universo do painel: `tipdoc = 'A'` e não cancelado, salvo toggles; ramos e seguradoras escolhidos."""
    qs = Producao.objects.all()
    if not filtros.todos_tipdoc:
        qs = qs.filter(tipdoc="A")
    if not filtros.incluir_cancelados:
        qs = qs.filter(cancelado=False)
    if filtros.ramos:
        qs = qs.filter(ramo__in=filtros.ramos)
    if filtros.seguradoras:
        qs = qs.filter(seguradora__in=filtros.seguradoras)
    return qs


def no_periodo(qs, ini: date, fim: date):
    return qs.filter(datemi__range=(ini, fim))


def _decimal_texto(valor) -> str | None:
    if valor is None:
        return None
    return str(Decimal(valor).quantize(Decimal("0.01")))


def formatar_bloco(bruto: dict) -> dict:
    """Dicionário do `aggregate`/`annotate` → Bloco do contrato (Decimal → string; sem cobertura → `null`)."""
    com_valor = bruto.get("documentos_com_valor") or 0
    com_comissao = bruto.get("documentos_com_comissao") or 0
    return {
        "fechados": bruto.get("fechados") or 0,
        "renovacoes": bruto.get("renovacoes") or 0,
        "captacoes": bruto.get("captacoes") or 0,
        "com_negocio_origem": bruto.get("com_negocio_origem") or 0,
        "valor_fechado": _decimal_texto(bruto.get("valor_fechado")) if com_valor else None,
        "documentos_com_valor": com_valor,
        "comissao": _decimal_texto(bruto.get("comissao")) if com_comissao else None,
        "documentos_com_comissao": com_comissao,
    }


def bloco_vazio() -> dict:
    return formatar_bloco({})


def bloco(qs, ini: date, fim: date) -> dict:
    return formatar_bloco(no_periodo(qs, ini, fim).aggregate(**EXPRESSOES_BLOCO))


# ------------------------------------------------------------------ carga vigente


def ultima_carga():
    return CargaCorp.objects.filter(sucesso=True).order_by("-concluida_em", "-id").first()


def dados_parciais(filtros: Filtros, carga=None) -> bool:
    """Referência depois da extração: a resposta sai normal, avisada (RF-IEX-003)."""
    carga = carga or ultima_carga()
    return bool(carga and carga.extraido_em and filtros.data_referencia > carga.extraido_em)


# ------------------------------------------------------------------ seções


def resumo(filtros: Filtros) -> dict:
    qs = queryset_base(filtros)
    ini, fim = filtros.janela
    ant_ini, ant_fim = filtros.janela_anterior
    return {
        "filtros": filtros.como_dict(),
        "dados_parciais": dados_parciais(filtros),
        "atual": bloco(qs, ini, fim),
        "anterior": bloco(qs, ant_ini, ant_fim),
        "periodos": {nome: bloco(qs, *janela) for nome, janela in janelas_padrao(filtros.data_referencia).items()},
    }


def por_seguradora(filtros: Filtros) -> dict:
    from indicadores.services import nao_fechadas  # evita import circular: nao_fechadas usa queryset_base

    qs = queryset_base(filtros)
    ini, fim = filtros.janela
    linhas_db = list(no_periodo(qs, ini, fim).values("seguradora").annotate(**EXPRESSOES_BLOCO))
    nao_fechadas_por_seg = nao_fechadas.calcular(filtros).sem_nova_por_seguradora()

    por_sigla = {linha["seguradora"]: formatar_bloco(linha) for linha in linhas_db}
    for sigla in nao_fechadas_por_seg:
        por_sigla.setdefault(sigla, bloco_vazio())
    nomes = dict(Seguradora.objects.filter(sigla__in=[s for s in por_sigla if s]).values_list("sigla", "nome"))

    linhas = []
    for sigla, dados in por_sigla.items():
        nao_fechadas_seg = nao_fechadas_por_seg.get(sigla, 0)
        if dados["fechados"] <= 0 and nao_fechadas_seg <= 0:
            continue
        linhas.append({
            "seguradora": sigla or "",
            "nome": nomes.get(sigla, "" if sigla else "(sem seguradora)"),
            **dados,
            "nao_fechadas": nao_fechadas_seg,
        })
    linhas.sort(key=lambda linha: (-linha["fechados"], -linha["nao_fechadas"], linha["seguradora"]))

    total = bloco(qs, ini, fim)
    total["nao_fechadas"] = sum(nao_fechadas_por_seg.values())
    return {"linhas": linhas, "total": total}


def serie(filtros: Filtros, tipo: str) -> dict:
    ref = filtros.data_referencia
    qs = queryset_base(filtros)
    if tipo == "dia":
        ini = ref - timedelta(days=29)
        por_dia = {
            linha["datemi"]: formatar_bloco(linha)
            for linha in no_periodo(qs, ini, ref).values("datemi").annotate(**EXPRESSOES_BLOCO)
        }
        pontos = []
        for deslocamento in range(30):
            dia = ini + timedelta(days=deslocamento)
            pontos.append({
                "periodo": dia.isoformat(),
                "rotulo": dia.strftime("%d/%m"),
                "futuro": False,
                **por_dia.get(dia, bloco_vazio()),
            })
        return {"tipo": "dia", "ano": ref.year, "pontos": pontos}

    # `mes`: agrupado no banco por TruncMonth; `datemi` é DateField, o corte já é a data civil local.
    por_mes = {}
    consulta = (
        no_periodo(qs, date(ref.year, 1, 1), ref)
        .annotate(mes=TruncMonth("datemi"))
        .values("mes")
        .annotate(**EXPRESSOES_BLOCO)
    )
    for linha in consulta:
        mes = linha["mes"]
        por_mes[(mes.year, mes.month)] = formatar_bloco(linha)
    pontos = []
    for mes in range(1, 13):
        futuro = mes > ref.month
        pontos.append({
            "periodo": f"{ref.year}-{mes:02d}",
            "rotulo": ROTULOS_MES[mes - 1],
            "futuro": futuro,
            **(bloco_vazio() if futuro else por_mes.get((ref.year, mes), bloco_vazio())),
        })
    return {"tipo": "mes", "ano": ref.year, "pontos": pontos}


def dominios(filtros: Filtros) -> dict:
    """Ramos e seguradoras com total na base e fechados no período; metadados da última carga.

    `total_base` é a base inteira, sem filtro: é o que mantém a ordem dos chips
    fixa. `fechados_periodo` respeita o universo e o filtro cruzado (o contador
    de ramo respeita as seguradoras escolhidas e vice-versa, RF-IEX-002).
    """
    ini, fim = filtros.janela
    carga = ultima_carga()

    totais_ramo = _contagem_por(Producao.objects.all(), "ramo")
    totais_seg = _contagem_por(Producao.objects.all(), "seguradora")
    # Filtro cruzado: o contador de ramo ignora o filtro de ramo e respeita o de seguradora; e vice-versa.
    fechados_ramo = _contagem_por(no_periodo(queryset_base(replace(filtros, ramos=[])), ini, fim), "ramo")
    fechados_seg = _contagem_por(no_periodo(queryset_base(replace(filtros, seguradoras=[])), ini, fim), "seguradora")

    ramos = [
        {"sigla": r.abreviatura, "nome": r.nome, "total_base": totais_ramo.get(r.abreviatura, 0),
         "fechados_periodo": fechados_ramo.get(r.abreviatura, 0)}
        for r in Ramo.objects.all()
    ]
    seguradoras = [
        {"sigla": s.sigla, "nome": s.nome, "total_base": totais_seg.get(s.sigla, 0),
         "fechados_periodo": fechados_seg.get(s.sigla, 0)}
        for s in Seguradora.objects.all()
    ]
    ramos.sort(key=lambda item: (-item["total_base"], item["sigla"]))
    seguradoras.sort(key=lambda item: (-item["total_base"], item["sigla"]))

    return {
        "extraido_em": carga.extraido_em.isoformat() if carga and carga.extraido_em else None,
        "gerado_em": carga.gerado_em if carga else None,
        "total_documentos": Producao.objects.count(),
        "documentos_sem_datemi": Producao.objects.filter(datemi__isnull=True).count(),
        "carga": {
            "origem": carga.origem,
            "concluida_em": carga.concluida_em.isoformat() if carga.concluida_em else None,
            "rejeitos": carga.rejeitos,
        } if carga else None,
        "dados_parciais": dados_parciais(filtros, carga),
        "ramos": ramos,
        "seguradoras": seguradoras,
    }


def _contagem_por(qs, campo: str) -> dict:
    """`{valor do campo: quantidade}` agrupado no banco."""
    return {linha[campo]: linha["n"] for linha in qs.values(campo).annotate(n=Count("nosnum"))}


def composicao(filtros: Filtros) -> dict:
    """As três listas saem das mesmas querysets dos cartões (INV-IEX-005)."""
    from indicadores.services import nao_fechadas

    qs = queryset_base(filtros)
    ini, fim = filtros.janela
    emitidas = no_periodo(qs, ini, fim).select_related("seguradora").order_by("-datemi", "cliente_nome", "nosnum")
    captacoes = emitidas.filter(renovacao=False)
    renovacoes = emitidas.filter(renovacao=True)
    vencidas = sorted(
        nao_fechadas.calcular(filtros).sem_nova_apolice, key=lambda p: (p.fimvig, p.nosnum), reverse=True
    )
    return {
        "captacoes": _lista(captacoes.count(), list(captacoes[:LIMITE_LINHAS]), "datemi"),
        "renovacoes": _lista(renovacoes.count(), list(renovacoes[:LIMITE_LINHAS]), "datemi"),
        "vencidas_sem_nova_apolice": _lista(len(vencidas), vencidas[:LIMITE_LINHAS], "fimvig"),
    }


def _lista(total: int, exibidas: list, campo_data: str) -> dict:
    return {
        "total": total,
        "exibidas": len(exibidas),
        "linhas": [
            {
                "nosnum": p.nosnum,
                "cliente": p.cliente_nome,
                "seguradora": p.seguradora_id,
                "seguradora_nome": p.seguradora.nome if p.seguradora else "",
                "ramo": p.ramo_id,
                "data": getattr(p, campo_data).isoformat() if getattr(p, campo_data) else None,
            }
            for p in exibidas
        ],
    }
