"""Não fechadas do mês (RF-IEX-006), calculadas no LAKE e montadas aqui (RF-IEX-011).

Universo: apólices que vencem no mês da referência. "Fechada" se existe (a) documento
com `nosnum_ren` apontando para ela ou (b) apólice `A` não cancelada do mesmo
CPF/CNPJ, em qualquer ramo ou seguradora, com início de vigência em `fimvig ±
janela_dias`. A regra é a mesma de antes; desde 23/09/2026 ela roda em
`fn_ind_nao_fechadas` do lake e chega pronta pelo FedHub — este módulo só
ordena, mascara CPF e monta a resposta.
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from indicadores.services import fedhub_lake
from indicadores.services.periodos import Filtros

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
    vencem: list = field(default_factory=list)  # linhas de fn_ind_nao_fechadas
    vencidas: list = field(default_factory=list)
    decididas: list = field(default_factory=list)
    sem_nova_apolice: list = field(default_factory=list)
    a_vencer: list = field(default_factory=list)

    def fechada(self, linha) -> bool:
        return bool(linha.get("fechada"))

    def sem_nova_por_seguradora(self) -> Counter:
        return Counter(l.get("seguradora_sigla") for l in self.sem_nova_apolice)

    def resposta(self) -> dict:
        corp_diz = Counter(l.get("renovacao_situacao") for l in self.vencidas)
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

    def _lista(self, linhas) -> dict:
        ordenadas = sorted(linhas, key=lambda l: (self.fechada(l), str(l.get("fimvig") or ""), int(l["nosnum"])))
        return {
            "total": len(ordenadas),
            "exibidas": min(len(ordenadas), LIMITE_LINHAS),
            "linhas": [self._linha(l) for l in ordenadas[:LIMITE_LINHAS]],
        }

    def _linha(self, l) -> dict:
        return {
            "nosnum": int(l["nosnum"]),
            "fimvig": str(l["fimvig"])[:10] if l.get("fimvig") else None,
            "datemi": str(l["datemi"])[:10] if l.get("datemi") else None,
            "cliente": l.get("cliente") or "",
            "cpf_cnpj": mascarar(l.get("cpf_cnpj"), l.get("pessoa") or ""),
            "pessoa": l.get("pessoa") or "",
            "seguradora": l.get("seguradora_sigla") or "",
            "seguradora_nome": l.get("seguradora") or "",
            "ramo": l.get("ramo_sigla") or "",
            "renovacao_situacao": l.get("renovacao_situacao"),
            "renovacao_situacao_rotulo": rotulo_situacao(l.get("renovacao_situacao")),
            "sin_situacao": l.get("sin_situacao"),
            "fechada": self.fechada(l),
            "novas_apolices": [
                {"nosnum": int(n["nosnum"]), "seguradora": n.get("seguradora") or "", "seguradora_nome": n.get("seguradora_nome") or ""}
                for n in (l.get("novas") or [])
            ],
        }


def calcular(filtros: Filtros) -> Resultado:
    ref = filtros.data_referencia
    resultado = Resultado(mes=ref.strftime("%Y-%m"), janela_dias=filtros.janela_dias)
    corpo = fedhub_lake.chamar("GET", "indicadores/nao-fechadas", params={
        "ref": ref.isoformat(), "janela_dias": filtros.janela_dias,
        "ramo": list(filtros.ramos), "seguradora": list(filtros.seguradoras),
        "incluir_cancelados": "true" if filtros.incluir_cancelados else "false",
        "todos_tipdoc": "true" if filtros.todos_tipdoc else "false",
    })
    linhas = corpo.get("linhas") or []
    resultado.vencem = linhas
    for l in linhas:
        if l.get("vencida"):
            resultado.vencidas.append(l)
            if l.get("decidida"):
                resultado.decididas.append(l)
                if not l.get("fechada"):
                    resultado.sem_nova_apolice.append(l)
        else:
            resultado.a_vencer.append(l)
    return resultado
