"""Não fechadas do mês (RF-IEX-006, T-IEX-2.3).

Universo: apólices da queryset base com `fimvig` no mês da referência. Uma
apólice está "fechada" se existe (a) documento com `nosnum_ren` apontando para
ela ou (b) apólice `A` não cancelada do mesmo CPF/CNPJ, em qualquer ramo ou
seguradora, com `inivig` em `fimvig ± janela_dias`. As "vencidas decididas" são
as com `fimvig ≤ referência` e `renovacao_situacao ∈ {2, 3}`; as sem nova
apólice entre elas são o número do cartão e a terceira lista da composição.

Todos os candidatos são lidos em duas consultas e cruzados em dicionários:
a regra olha a carteira do cliente, e o volume (dezenas de milhares) cabe.
"""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from indicadores.models import Producao
from indicadores.services import agregacao
from indicadores.services.periodos import Filtros, mes_da_referencia

LIMITE_LINHAS = 400
SITUACOES_DECIDIDAS = (2, 3)
ROTULOS_SITUACAO = {1: "vigente", 2: "renovada", 3: "não renovada", 5: "5 (sem legenda)", 6: "cancelada", -1: "—"}


def rotulo_situacao(situacao) -> str:
    if situacao is None:
        return "—"
    return ROTULOS_SITUACAO.get(situacao, f"{situacao} (sem legenda)")


def mascarar(cpf_cnpj, pessoa="") -> str:
    """CPF sai `***.456.789-**`; CNPJ sai formatado completo; outro tamanho sai como veio (PA-022)."""
    if not cpf_cnpj:
        return ""
    digitos = re.sub(r"\D", "", str(cpf_cnpj))
    if len(digitos) == 11:
        return f"***.{digitos[3:6]}.{digitos[6:9]}-**"
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return str(cpf_cnpj)


@dataclass
class Resultado:
    """Saída do cálculo, antes de virar resposta: as outras seções também leem daqui."""

    mes: str
    janela_dias: int
    vencem: list = field(default_factory=list)  # Producao
    novas: dict = field(default_factory=dict)  # nosnum → [Producao]
    vencidas: list = field(default_factory=list)
    decididas: list = field(default_factory=list)
    sem_nova_apolice: list = field(default_factory=list)
    a_vencer: list = field(default_factory=list)

    def fechada(self, producao) -> bool:
        return bool(self.novas.get(producao.nosnum))

    def sem_nova_por_seguradora(self) -> Counter:
        return Counter(p.seguradora_id for p in self.sem_nova_apolice)

    def resposta(self) -> dict:
        corp_diz = Counter(p.renovacao_situacao for p in self.vencidas)
        return {
            "mes": self.mes,
            "janela_dias": self.janela_dias,
            "resumo": {
                "vencem_no_mes": len(self.vencem),
                "vencidas": len(self.vencidas),
                "vencidas_decididas": len(self.decididas),
                "vencidas_ainda_vigentes": len(self.vencidas) - len(self.decididas),
                "vencidas_sem_nova_apolice": len(self.sem_nova_apolice),
                "a_vencer": len(self.a_vencer),
                "corp_diz": [
                    {"situacao": situacao, "rotulo": rotulo_situacao(situacao), "quantidade": quantidade}
                    for situacao, quantidade in sorted(corp_diz.items(), key=lambda item: (-item[1], str(item[0])))
                ],
            },
            "vencidas": self._lista(self.decididas),
            "a_vencer": self._lista(self.a_vencer),
        }

    def _lista(self, producoes) -> dict:
        ordenadas = sorted(producoes, key=lambda p: (self.fechada(p), p.fimvig, p.nosnum))
        return {
            "total": len(ordenadas),
            "exibidas": min(len(ordenadas), LIMITE_LINHAS),
            "linhas": [self._linha(p) for p in ordenadas[:LIMITE_LINHAS]],
        }

    def _linha(self, p) -> dict:
        cliente = p.cliente
        return {
            "nosnum": p.nosnum,
            "fimvig": p.fimvig.isoformat() if p.fimvig else None,
            "datemi": p.datemi.isoformat() if p.datemi else None,
            "cliente": p.cliente_nome or (cliente.nome if cliente else ""),
            "cpf_cnpj": mascarar(cliente.cpf_cnpj, cliente.pessoa) if cliente else "",
            "pessoa": cliente.pessoa if cliente else "",
            "seguradora": p.seguradora_id,
            "seguradora_nome": p.seguradora.nome if p.seguradora else "",
            "ramo": p.ramo_id,
            "renovacao_situacao": p.renovacao_situacao,
            "renovacao_situacao_rotulo": rotulo_situacao(p.renovacao_situacao),
            "sin_situacao": p.sin_situacao,
            "fechada": self.fechada(p),
            "novas_apolices": [
                {"nosnum": n.nosnum, "seguradora": n.seguradora_id, "seguradora_nome": n.seguradora.nome if n.seguradora else ""}
                for n in self.novas.get(p.nosnum, [])
            ],
        }


def calcular(filtros: Filtros) -> Resultado:
    ref = filtros.data_referencia
    mes_ini, mes_fim = mes_da_referencia(ref)
    janela = timedelta(days=filtros.janela_dias)
    resultado = Resultado(mes=ref.strftime("%Y-%m"), janela_dias=filtros.janela_dias)

    vencem = list(
        agregacao.queryset_base(filtros)
        .filter(fimvig__range=(mes_ini, mes_fim))
        .select_related("cliente", "seguradora")
        .order_by("fimvig", "nosnum")
    )
    resultado.vencem = vencem
    if not vencem:
        return resultado

    nosnums = {p.nosnum for p in vencem}
    cpfs = {p.cliente.cpf_cnpj for p in vencem if p.cliente_id and p.cliente.cpf_cnpj}

    # (a) cadeia da CORP: qualquer documento que renova uma das vencidas.
    por_cadeia = defaultdict(list)
    for nova in Producao.objects.filter(nosnum_ren__in=nosnums).select_related("seguradora").order_by("inivig", "nosnum"):
        por_cadeia[nova.nosnum_ren].append(nova)

    # (b) mesma pessoa, apólice A não cancelada, em qualquer ramo: filtrada pela janela abaixo.
    por_cpf = defaultdict(list)
    candidatas = (
        Producao.objects.filter(tipdoc="A", cancelado=False, inivig__isnull=False, cliente__cpf_cnpj__in=cpfs)
        .select_related("seguradora", "cliente")
        .order_by("inivig", "nosnum")
    )
    for nova in candidatas:
        por_cpf[nova.cliente.cpf_cnpj].append(nova)

    for p in vencem:
        novas = {n.nosnum: n for n in por_cadeia.get(p.nosnum, [])}
        cpf = p.cliente.cpf_cnpj if p.cliente_id else ""
        if cpf and p.fimvig:
            ini, fim = p.fimvig - janela, p.fimvig + janela
            for n in por_cpf.get(cpf, []):
                if n.nosnum != p.nosnum and ini <= n.inivig <= fim:
                    novas.setdefault(n.nosnum, n)
        if novas:
            resultado.novas[p.nosnum] = sorted(novas.values(), key=lambda n: (n.inivig or p.fimvig, n.nosnum))

        if p.fimvig <= ref:
            resultado.vencidas.append(p)
            if p.renovacao_situacao in SITUACOES_DECIDIDAS:
                resultado.decididas.append(p)
                if not resultado.fechada(p):
                    resultado.sem_nova_apolice.append(p)
        else:
            resultado.a_vencer.append(p)
    return resultado
