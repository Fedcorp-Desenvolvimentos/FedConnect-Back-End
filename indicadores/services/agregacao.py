"""Indicadores da tela "Produção CORP", montados a partir do LAKE via FedHub (RF-IEX-011).

Até 23/09/2026 este módulo agregava um espelho local por data de emissão e prêmio
total; o painel de TV lia o lake por início de vigência e prêmio líquido, e a
mesma meta tinha dois atingimentos. A gestão decidiu: "vamos manter o que está
no lake". Desde então NENHUM número é calculado aqui. Cada seção pede ao FedHub
(`/api/lake/indicadores/*`), que repassa as funções `fn_ind_*` do contrato do
lake, e este módulo só MONTA a resposta no contrato que o front já consome:
mesmas chaves, mesmos envelopes (RF-IEX-002..007). A regra — corte por início
de vigência, valor fechado = prêmio líquido, renovação da casa, documento que a
CORP apagou fora — mora no lake, e é a mesma do painel de TV.

Toda soma monetária continua saindo como string decimal ao lado da contagem de
documentos que a compõem; sem nenhum, `null` (INV-IEX-003).
"""
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from indicadores.services import fedhub_lake
from indicadores.services import metas as servico_metas
from indicadores.services.periodos import Filtros, janelas_padrao, mes_da_referencia, ultimo_dia_do_mes

LIMITE_LINHAS = 400
ROTULOS_MES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
CAMPOS_BLOCO = ("fechados", "renovacoes", "captacoes", "com_negocio_origem", "valor_fechado",
                "documentos_com_valor", "comissao", "documentos_com_comissao")


# ------------------------------------------------------------------ FedHub

def _parametros(filtros: Filtros, ramos=None, seguradoras=None, **extra) -> dict:
    """Query string das rotas do FedHub. `None` em ramos/seguradoras = os do filtro; lista = sobrepõe."""
    p = {
        "ramo": list(filtros.ramos if ramos is None else ramos),
        "seguradora": list(filtros.seguradoras if seguradoras is None else seguradoras),
        "incluir_cancelados": "true" if filtros.incluir_cancelados else "false",
        "todos_tipdoc": "true" if filtros.todos_tipdoc else "false",
    }
    p.update(extra)
    return p


def _lake(rota: str, params: dict):
    return fedhub_lake.chamar("GET", "indicadores/" + rota, params=params)


def _bloco_lake(filtros: Filtros, ini: date, fim: date, ramos=None, seguradoras=None) -> dict:
    corpo = _lake("bloco", _parametros(filtros, ramos, seguradoras, ini=ini.isoformat(), fim=fim.isoformat()))
    return formatar_bloco(corpo.get("bloco") or {})


def totais() -> dict:
    return _lake("totais", {}).get("totais") or {}


# ------------------------------------------------------------------ bloco

def _decimal_texto(valor) -> str | None:
    if valor is None:
        return None
    return str(Decimal(str(valor)).quantize(Decimal("0.01")))


def formatar_bloco(bruto: dict) -> dict:
    """Linha de `fn_ind_bloco` → Bloco do contrato (decimal → string; sem cobertura → `null`)."""
    com_valor = int(bruto.get("documentos_com_valor") or 0)
    com_comissao = int(bruto.get("documentos_com_comissao") or 0)
    return {
        "fechados": int(bruto.get("fechados") or 0),
        "renovacoes": int(bruto.get("renovacoes") or 0),
        "captacoes": int(bruto.get("captacoes") or 0),
        "com_negocio_origem": int(bruto.get("com_negocio_origem") or 0),
        "valor_fechado": _decimal_texto(bruto.get("valor_fechado")) if com_valor else None,
        "documentos_com_valor": com_valor,
        "comissao": _decimal_texto(bruto.get("comissao")) if com_comissao else None,
        "documentos_com_comissao": com_comissao,
    }


def bloco_vazio() -> dict:
    return formatar_bloco({})


# ------------------------------------------------------------------ carga vigente

def _data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date()


def extraido_em(tot: dict | None = None) -> date | None:
    """Data da última carga concluída do lake (`fn_ind_totais.extraido_em`)."""
    return _data((tot if tot is not None else totais()).get("extraido_em"))


def dados_parciais(filtros: Filtros, tot: dict | None = None) -> bool:
    """Referência depois da última carga do lake: a resposta sai normal, avisada (RF-IEX-003)."""
    quando = extraido_em(tot)
    return bool(quando and filtros.data_referencia > quando)


# ------------------------------------------------------------------ seções

def resumo(filtros: Filtros) -> dict:
    ini, fim = filtros.janela
    ant_ini, ant_fim = filtros.janela_anterior
    tot = totais()
    return {
        "filtros": filtros.como_dict(),
        "dados_parciais": dados_parciais(filtros, tot),
        "atual": _bloco_lake(filtros, ini, fim),
        "anterior": _bloco_lake(filtros, ant_ini, ant_fim),
        "periodos": {nome: _bloco_lake(filtros, *janela) for nome, janela in janelas_padrao(filtros.data_referencia).items()},
        "meta_mes": meta_mes(filtros),
    }


# ------------------------------------------------------------------ metas (RF-IEX-008/010)

class _MetasIndisponiveis(list):
    """Lista vazia que sabe por quê: o lake não respondeu à leitura das metas."""

    indisponiveis = True


def _metas_do_mes(filtros: Filtros) -> list[dict]:
    try:
        return servico_metas.metas_da_competencia(
            filtros.data_referencia.replace(day=1), filtros.ramos, filtros.seguradoras
        )
    except fedhub_lake.LakeIndisponivel:
        return _MetasIndisponiveis()


def _realizado_dos_pares(filtros: Filtros, metas: list[dict], ini: date, fim: date) -> dict:
    """Valor fechado (líquido) do mês, restrito aos pares seguradora × ramo com meta (PA-023).

    Sem meta, o universo inteiro do filtro. Um bloco por par: são poucas metas, e
    é o mesmo número que o painel de TV mostra para aquele par.
    """
    pares = sorted({(m["seguradora"], m["ramo"]) for m in metas})
    if not pares:
        b = _bloco_lake(filtros, ini, fim)
        return {"valor": Decimal(b["valor_fechado"]) if b["valor_fechado"] else None, "n": b["documentos_com_valor"],
                "por_seguradora": {}}
    valor, n, por_seg = Decimal(0), 0, {}
    for seguradora, ramo in pares:
        b = _bloco_lake(filtros, ini, fim, ramos=[ramo], seguradoras=[seguradora])
        if b["documentos_com_valor"]:
            v = Decimal(b["valor_fechado"])
            valor += v
            n += b["documentos_com_valor"]
            por_seg[seguradora] = por_seg.get(seguradora, Decimal(0)) + v
    return {"valor": valor if n else None, "n": n, "por_seguradora": por_seg}


def _percentual(realizado, meta) -> float | None:
    if meta is None or meta == 0:
        return None
    return float((Decimal(realizado or 0) / Decimal(meta) * 100).quantize(Decimal("0.1")))


def meta_mes(filtros: Filtros, metas_mes: list | None = None) -> dict:
    """Meta × realizado do **mês civil inteiro** da referência, seja qual for o `periodo`.

    Até 2026-09-24 o realizado ia do dia 1 até a referência, enquanto o cartão
    "Valor fechado" (em "este mês") mostrava o mês inteiro: a diferença entre os
    dois números fazia "faltam" sair maior do que meta − valor fechado (relato do
    dono, PA-028). Agora as duas contas usam a mesma janela, e a projeção pelo
    ritmo dos dias deixa de fazer sentido: sai `null`.
    """
    ref = filtros.data_referencia
    dias_no_mes = ultimo_dia_do_mes(ref.year, ref.month)
    dias_decorridos = ref.day
    metas_mes = _metas_do_mes(filtros) if metas_mes is None else metas_mes
    meta = sum(Decimal(m["valor_meta"]) for m in metas_mes) if metas_mes else None
    fechado = _realizado_dos_pares(filtros, metas_mes, *mes_da_referencia(ref))
    realizado = fechado["valor"]

    falta = projecao = None
    if meta is not None:
        falta = max(meta - (realizado or 0), Decimal(0))

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
        "metas_consideradas": len(metas_mes),
        "metas_indisponiveis": bool(getattr(metas_mes, "indisponiveis", False)),
    }


def _metas_por_seguradora(metas: list[dict]) -> dict:
    por_sigla: dict = {}
    for m in metas:
        por_sigla[m["seguradora"]] = por_sigla.get(m["seguradora"], Decimal(0)) + Decimal(m["valor_meta"])
    return por_sigla


def por_seguradora(filtros: Filtros) -> dict:
    from indicadores.services import nao_fechadas

    ini, fim = filtros.janela
    linhas_lake = _lake("por-seguradora", _parametros(filtros, ini=ini.isoformat(), fim=fim.isoformat())).get("linhas") or []
    nao_fechadas_por_seg = nao_fechadas.calcular(filtros).sem_nova_por_seguradora()

    metas_mes = _metas_do_mes(filtros)
    metas_por_seg = _metas_por_seguradora(metas_mes)
    ref = filtros.data_referencia
    # Mesma janela de `meta_mes`: o mês civil inteiro (PA-028).
    realizado = _realizado_dos_pares(filtros, metas_mes, *mes_da_referencia(ref))
    realizado_por_seg = realizado["por_seguradora"]

    por_sigla = {l["seguradora_sigla"]: formatar_bloco(l) for l in linhas_lake}
    nomes = {l["seguradora_sigla"]: l.get("seguradora") or "" for l in linhas_lake}
    for sigla in list(nao_fechadas_por_seg) + list(metas_por_seg):
        por_sigla.setdefault(sigla, bloco_vazio())

    linhas = []
    for sigla, dados in por_sigla.items():
        nf = nao_fechadas_por_seg.get(sigla, 0)
        meta_seg = metas_por_seg.get(sigla)
        if dados["fechados"] <= 0 and nf <= 0 and meta_seg is None:
            continue
        realizado_seg = realizado_por_seg.get(sigla) if meta_seg is not None else None
        linhas.append({
            "seguradora": sigla or "",
            "nome": nomes.get(sigla, "" if sigla else "(sem seguradora)"),
            **dados,
            "nao_fechadas": nf,
            "meta_mes": _decimal_texto(meta_seg),
            "realizado_mes": _decimal_texto(realizado_seg),
            "percentual_meta": _percentual(realizado_seg, meta_seg),
        })
    linhas.sort(key=lambda linha: (-linha["fechados"], -linha["nao_fechadas"], linha["seguradora"]))

    total = _bloco_lake(filtros, ini, fim)
    total["nao_fechadas"] = sum(nao_fechadas_por_seg.values())
    geral = meta_mes(filtros, metas_mes)
    total["meta_mes"] = geral["meta"]
    total["realizado_mes"] = geral["realizado"]
    total["percentual_meta"] = geral["percentual"]
    return {"linhas": linhas, "total": total}


def serie(filtros: Filtros, tipo: str) -> dict:
    ref = filtros.data_referencia
    if tipo == "dia":
        ini = ref - timedelta(days=29)
        linhas = _lake("serie", _parametros(filtros, ini=ini.isoformat(), fim=ref.isoformat(), grao="dia")).get("linhas") or []
        por_dia = {str(l["periodo"])[:10]: formatar_bloco(l) for l in linhas}
        pontos = []
        for deslocamento in range(30):
            dia = ini + timedelta(days=deslocamento)
            pontos.append({"periodo": dia.isoformat(), "rotulo": dia.strftime("%d/%m"), "futuro": False,
                           **por_dia.get(dia.isoformat(), bloco_vazio())})
        return {"tipo": "dia", "ano": ref.year, "pontos": pontos}

    linhas = _lake("serie", _parametros(filtros, ini=date(ref.year, 1, 1).isoformat(), fim=ref.isoformat(), grao="mes")).get("linhas") or []
    por_mes = {str(l["periodo"])[:7]: formatar_bloco(l) for l in linhas}
    pontos = []
    for mes in range(1, 13):
        futuro = mes > ref.month
        chave = f"{ref.year}-{mes:02d}"
        pontos.append({"periodo": chave, "rotulo": ROTULOS_MES[mes - 1], "futuro": futuro,
                       **(bloco_vazio() if futuro else por_mes.get(chave, bloco_vazio()))})
    return {"tipo": "mes", "ano": ref.year, "pontos": pontos}


def dominios(filtros: Filtros) -> dict:
    """Ramos e seguradoras com total na base e fechados no período (filtro cruzado no lake); metadados da carga."""
    ini, fim = filtros.janela
    linhas = _lake("dominios", _parametros(filtros, ini=ini.isoformat(), fim=fim.isoformat())).get("linhas") or []
    tot = totais()

    def lista(dominio):
        itens = [{"sigla": l["sigla"], "nome": l.get("nome") or "", "total_base": int(l.get("total_base") or 0),
                  "fechados_periodo": int(l.get("fechados_periodo") or 0)} for l in linhas if l["dominio"] == dominio]
        itens.sort(key=lambda item: (-item["total_base"], item["sigla"]))
        return itens

    quando = extraido_em(tot)
    return {
        "extraido_em": quando.isoformat() if quando else None,
        "gerado_em": str(tot.get("extraido_em"))[:16].replace("T", " ") if tot.get("extraido_em") else None,
        "total_documentos": int(tot.get("total_documentos") or 0),
        "documentos_sem_datemi": int(tot.get("documentos_sem_datemi") or 0),
        "carga": {
            "origem": "lake",
            "concluida_em": str(tot["extraido_em"]) if tot.get("extraido_em") else None,
            "rejeitos": {"ausentes_na_origem": int(tot.get("ausentes_na_origem") or 0)},
        },
        "dados_parciais": dados_parciais(filtros, tot),
        "ramos": lista("ramo"),
        "seguradoras": lista("seguradora"),
    }


def composicao(filtros: Filtros) -> dict:
    """As três listas saem do mesmo universo dos cartões (INV-IEX-005), agora no lake."""
    from indicadores.services import nao_fechadas

    ini, fim = filtros.janela
    linhas = _lake("composicao", _parametros(filtros, ini=ini.isoformat(), fim=fim.isoformat())).get("linhas") or []
    captacoes = [l for l in linhas if l["lista"] == "captacoes"]
    renovacoes = [l for l in linhas if l["lista"] == "renovacoes"]
    vencidas = sorted(nao_fechadas.calcular(filtros).sem_nova_apolice, key=lambda p: (p["fimvig"], p["nosnum"]), reverse=True)
    return {
        "captacoes": _lista(captacoes, "data"),
        "renovacoes": _lista(renovacoes, "data"),
        "vencidas_sem_nova_apolice": _lista(vencidas, "fimvig"),
    }


def _lista(linhas: list, campo_data: str) -> dict:
    exibidas = linhas[:LIMITE_LINHAS]
    return {
        "total": len(linhas),
        "exibidas": len(exibidas),
        "linhas": [
            {
                "nosnum": int(l["nosnum"]),
                "cliente": l.get("cliente") or "",
                "seguradora": l.get("seguradora_sigla") or "",
                "seguradora_nome": l.get("seguradora") or "",
                "ramo": l.get("ramo_sigla") or "",
                "data": str(l[campo_data])[:10] if l.get(campo_data) else None,
            }
            for l in exibidas
        ],
    }
