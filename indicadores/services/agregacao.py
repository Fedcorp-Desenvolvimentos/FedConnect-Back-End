"""Agregações dos indicadores no banco (RF-IEX-002..005, RF-IEX-007, RF-IEX-008, T-IEX-2.2, T-IEX-2.4, T-IEX-4.3).

Primeira agregação com o ORM no repositório (ADR-0009): `Count`, `Sum`,
`Q`-filter em `Count` e `TruncMonth`, tudo numa consulta por Bloco. Nada é
somado em Python linha a linha (RNF-IEX-003). Toda soma monetária sai como
string decimal ao lado da contagem de documentos que a compõem; sem nenhum,
sai `null`, nunca `"0.00"` (INV-IEX-003, PA-019).

`meta_mes` (RF-IEX-008, PA-023) compara a soma das metas cadastradas para o
mês da referência com o valor fechado do dia 1 até a referência — sempre o
mês, independente do `periodo` pedido, porque a meta é mensal. Desde RF-IEX-010
(23/09/2026) as metas vêm do LAKE, via FedHub, e o realizado comparado com a
meta é o PRÊMIO LÍQUIDO (`preliq`), como a gestão decidiu para o lake — o
cartão `valor_fechado` do período continua em `pretot` até a tela inteira
passar a ler o lake.
"""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from indicadores.models import CargaCorp, Producao, Ramo, Seguradora
from indicadores.services import fedhub_lake
from indicadores.services import metas as servico_metas
from indicadores.services.periodos import Filtros, janelas_padrao, ultimo_dia_do_mes

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
        "meta_mes": meta_mes(filtros, qs),
    }


# ------------------------------------------------------------------ metas (RF-IEX-008)


class _MetasIndisponiveis(list):
    """Lista vazia que sabe por quê: o lake não respondeu. A tela mostra o realizado
    e avisa que a meta não veio, em vez de cair inteira por causa de um número."""

    indisponiveis = True


def _metas_do_mes(filtros: Filtros) -> list[dict]:
    """Metas da competência da referência (lidas do lake via FedHub), restritas aos ramos e seguradoras do filtro."""
    try:
        return servico_metas.metas_da_competencia(
            filtros.data_referencia.replace(day=1), filtros.ramos, filtros.seguradoras
        )
    except fedhub_lake.LakeIndisponivel:
        return _MetasIndisponiveis()


def _so_pares_com_meta(qs, metas: list[dict]):
    """Restringe o universo aos pares seguradora × ramo que têm meta no mês.

    A meta "vai contra o total do mês" daquele par (PA-023). Sem esta restrição,
    a tela sem filtro compararia a soma das metas cadastradas com o realizado
    da carteira inteira — uma única meta apareceria "158 % atingida".
    """
    pares = {(m["seguradora"], m["ramo"]) for m in metas}
    if not pares:
        return qs
    condicao = Q()
    for seguradora, ramo in pares:
        condicao |= Q(seguradora_id=seguradora, ramo_id=ramo)
    return qs.filter(condicao)


def _percentual(realizado, meta) -> float | None:
    """`realizado / meta × 100` com uma decimal (INV-IEX-008); `null` sem meta. Pode passar de 100."""
    if meta is None or meta == 0:
        return None
    return float((Decimal(realizado or 0) / Decimal(meta) * 100).quantize(Decimal("0.1")))


def meta_mes(filtros: Filtros, qs=None) -> dict:
    """Meta × realizado do mês da referência, sempre do dia 1 até a referência, seja qual for o `periodo`.

    `meta` é a soma das metas do mês (filtro vazio = todas); `null` quando
    nenhuma. `realizado` é o valor fechado no mês **dos pares seguradora × ramo
    que têm meta** (com meta cadastrada) ou do universo inteiro (sem meta)
    (INV-IEX-003: `null` sem documento com valor). `falta = max(meta − realizado, 0)`;
    `projecao` extrapola o ritmo do mês (`realizado / dias_decorridos × dias_no_mes`).
    """
    ref = filtros.data_referencia
    qs = queryset_base(filtros) if qs is None else qs
    dias_no_mes = ultimo_dia_do_mes(ref.year, ref.month)
    dias_decorridos = ref.day

    metas_mes = _metas_do_mes(filtros)
    metas = {"meta": sum(Decimal(m["valor_meta"]) for m in metas_mes), "n": len(metas_mes)}
    # Realizado da meta em PRÊMIO LÍQUIDO (decisão da gestão para o lake, 23/09/2026).
    fechado = no_periodo(_so_pares_com_meta(qs, metas_mes), ref.replace(day=1), ref).aggregate(
        valor=Sum("documento__preliq"), n=Count("documento__preliq")
    )
    meta = metas["meta"] if metas["n"] else None
    realizado = fechado["valor"] if fechado["n"] else None

    falta = projecao = None
    if meta is not None:
        falta = max(meta - (realizado or 0), Decimal(0))
    if realizado is not None:
        projecao = Decimal(realizado) / dias_decorridos * dias_no_mes

    return {
        "competencia": f"{ref.year:04d}-{ref.month:02d}",
        "dias_no_mes": dias_no_mes,
        "dias_decorridos": dias_decorridos,
        "meta": _decimal_texto(meta),
        "realizado": _decimal_texto(realizado),
        "documentos_com_valor": fechado["n"] or 0,
        "falta": _decimal_texto(falta),
        "percentual": _percentual(realizado, meta),
        "projecao": _decimal_texto(projecao),
        "metas_consideradas": metas["n"] or 0,
        "metas_indisponiveis": bool(getattr(metas_mes, "indisponiveis", False)),
    }


def _metas_por_seguradora(metas: list[dict]) -> dict:
    """`{sigla: soma das metas do mês}` a partir das metas já filtradas."""
    por_sigla: dict = {}
    for m in metas:
        por_sigla[m["seguradora"]] = por_sigla.get(m["seguradora"], Decimal(0)) + Decimal(m["valor_meta"])
    return por_sigla


def _realizado_mes_por_seguradora(qs, ref: date) -> dict:
    """`{sigla: prêmio líquido fechado no mês até a referência}`; `null` para quem não tem documento com valor."""
    consulta = (
        no_periodo(qs, ref.replace(day=1), ref)
        .values("seguradora")
        .annotate(valor=Sum("documento__preliq"), n=Count("documento__preliq"))
    )
    return {linha["seguradora"]: (linha["valor"] if linha["n"] else None) for linha in consulta}


def por_seguradora(filtros: Filtros) -> dict:
    from indicadores.services import nao_fechadas  # evita import circular: nao_fechadas usa queryset_base

    qs = queryset_base(filtros)
    ini, fim = filtros.janela
    linhas_db = list(no_periodo(qs, ini, fim).values("seguradora").annotate(**EXPRESSOES_BLOCO))
    nao_fechadas_por_seg = nao_fechadas.calcular(filtros).sem_nova_por_seguradora()

    # Metas do mês (RF-IEX-008/010): uma leitura do lake; seguradora com meta aparece mesmo sem fechado no período.
    metas_mes = _metas_do_mes(filtros)
    metas_por_seg = _metas_por_seguradora(metas_mes)
    # Realizado da meta só nos ramos com meta de cada seguradora (mesma regra de `meta_mes`).
    realizado_por_seg = _realizado_mes_por_seguradora(_so_pares_com_meta(qs, metas_mes), filtros.data_referencia)

    por_sigla = {linha["seguradora"]: formatar_bloco(linha) for linha in linhas_db}
    for sigla in list(nao_fechadas_por_seg) + list(metas_por_seg):
        por_sigla.setdefault(sigla, bloco_vazio())
    nomes = dict(Seguradora.objects.filter(sigla__in=[s for s in por_sigla if s]).values_list("sigla", "nome"))

    linhas = []
    for sigla, dados in por_sigla.items():
        nao_fechadas_seg = nao_fechadas_por_seg.get(sigla, 0)
        meta_seg = metas_por_seg.get(sigla)
        if dados["fechados"] <= 0 and nao_fechadas_seg <= 0 and meta_seg is None:
            continue
        realizado_seg = realizado_por_seg.get(sigla)
        linhas.append({
            "seguradora": sigla or "",
            "nome": nomes.get(sigla, "" if sigla else "(sem seguradora)"),
            **dados,
            "nao_fechadas": nao_fechadas_seg,
            "meta_mes": _decimal_texto(meta_seg),
            "realizado_mes": _decimal_texto(realizado_seg),
            "percentual_meta": _percentual(realizado_seg, meta_seg),
        })
    linhas.sort(key=lambda linha: (-linha["fechados"], -linha["nao_fechadas"], linha["seguradora"]))

    total = bloco(qs, ini, fim)
    total["nao_fechadas"] = sum(nao_fechadas_por_seg.values())
    geral = meta_mes(filtros, qs)
    total["meta_mes"] = geral["meta"]
    total["realizado_mes"] = geral["realizado"]
    total["percentual_meta"] = geral["percentual"]
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
