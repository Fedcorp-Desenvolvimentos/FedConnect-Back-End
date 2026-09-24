"""Parâmetros comuns dos endpoints e janelas de período (RF-IEX-003, T-IEX-2.1).

Todo corte é por `datemi` e em datas civis (`datetime.date`), no fuso
`America/Sao_Paulo`: a referência padrão é `timezone.localdate()`, nunca
`date.today()` em UTC (RF-IEX-005). A semana começa na segunda-feira.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

PERIODOS = ("hoje", "semana", "mes", "ano", "faixa")
JANELA_PADRAO = 30
JANELA_MAXIMA = 180


class ParametroInvalido(ValueError):
    """Parâmetro fora do contrato: vira 400 `{"sucesso": false, "erro": ...}`."""


@dataclass
class Filtros:
    periodo: str = "mes"
    data_referencia: date = field(default_factory=timezone.localdate)
    data_ini: date | None = None
    data_fim: date | None = None
    ramos: list[str] = field(default_factory=list)
    seguradoras: list[str] = field(default_factory=list)
    incluir_cancelados: bool = False
    todos_tipdoc: bool = False
    janela_dias: int = JANELA_PADRAO

    def __post_init__(self):
        if self.periodo not in PERIODOS:
            raise ParametroInvalido(f"periodo deve ser um de {', '.join(PERIODOS)}.")
        if self.periodo == "faixa":
            if not (self.data_ini and self.data_fim):
                raise ParametroInvalido("periodo=faixa exige data_ini e data_fim.")
            # Invertidos são trocados, não recusados (contrato do design).
            if self.data_ini > self.data_fim:
                self.data_ini, self.data_fim = self.data_fim, self.data_ini
        if not 0 <= self.janela_dias <= JANELA_MAXIMA:
            raise ParametroInvalido(f"janela_dias deve estar entre 0 e {JANELA_MAXIMA}.")

    @property
    def janela(self) -> tuple[date, date]:
        """`[ini, fim]` do período pedido."""
        return janela(self.periodo, self.data_referencia, self.data_ini, self.data_fim)

    @property
    def janela_anterior(self) -> tuple[date, date]:
        return janela_anterior(self.periodo, self.data_referencia, self.data_ini, self.data_fim)

    def como_dict(self) -> dict:
        ini, fim = self.janela
        ant_ini, ant_fim = self.janela_anterior
        return {
            "periodo": self.periodo,
            "data_referencia": self.data_referencia.isoformat(),
            "periodo_ini": ini.isoformat(),
            "periodo_fim": fim.isoformat(),
            "anterior_ini": ant_ini.isoformat(),
            "anterior_fim": ant_fim.isoformat(),
            "ramos": list(self.ramos),
            "seguradoras": list(self.seguradoras),
            "incluir_cancelados": self.incluir_cancelados,
            "todos_tipdoc": self.todos_tipdoc,
            "janela_dias": self.janela_dias,
        }


# ------------------------------------------------------------------ janelas


def ultimo_dia_do_mes(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def _mesmo_dia_ou_ultimo(ano: int, mes: int, dia: int) -> date:
    """Dia limitado ao último do mês (31/mar → 30/abr; 29/fev → 28/fev)."""
    return date(ano, mes, min(dia, ultimo_dia_do_mes(ano, mes)))


def segunda_feira(ref: date) -> date:
    return ref - timedelta(days=ref.weekday())


def janela(periodo: str, ref: date, data_ini: date | None = None, data_fim: date | None = None) -> tuple[date, date]:
    if periodo == "hoje":
        return ref, ref
    if periodo == "semana":
        return segunda_feira(ref), ref
    if periodo == "mes":
        # Mês civil inteiro, do dia 1 ao último dia (PA-028, decisão do dono em
        # 2026-09-24): não corta na referência. Emissões depois da referência só
        # existem quando a referência é passado, e aí devem entrar.
        return mes_da_referencia(ref)
    if periodo == "ano":
        return date(ref.year, 1, 1), ref
    if periodo == "faixa":
        return data_ini, data_fim
    raise ParametroInvalido(f"periodo desconhecido: {periodo}")


def janela_anterior(
    periodo: str, ref: date, data_ini: date | None = None, data_fim: date | None = None
) -> tuple[date, date]:
    """O período equivalente imediatamente anterior, para a tela calcular o delta."""
    if periodo == "hoje":
        ontem = ref - timedelta(days=1)
        return ontem, ontem
    if periodo == "semana":
        return segunda_feira(ref) - timedelta(days=7), ref - timedelta(days=7)
    if periodo == "mes":
        # Mês anterior inteiro, para comparar mês fechado com mês fechado (PA-028).
        ano, mes = (ref.year - 1, 12) if ref.month == 1 else (ref.year, ref.month - 1)
        return date(ano, mes, 1), date(ano, mes, ultimo_dia_do_mes(ano, mes))
    if periodo == "ano":
        return date(ref.year - 1, 1, 1), _mesmo_dia_ou_ultimo(ref.year - 1, ref.month, ref.day)
    if periodo == "faixa":
        duracao = (data_fim - data_ini).days + 1
        return data_ini - timedelta(days=duracao), data_ini - timedelta(days=1)
    raise ParametroInvalido(f"periodo desconhecido: {periodo}")


def janelas_padrao(ref: date) -> dict[str, tuple[date, date]]:
    """Hoje, semana, mês e ano da mesma referência (bloco `periodos` do resumo)."""
    return {nome: janela(nome, ref) for nome in ("hoje", "semana", "mes", "ano")}


def mes_da_referencia(ref: date) -> tuple[date, date]:
    """`[dia 1, último dia]` do mês da referência (não fechadas, RF-IEX-006)."""
    return ref.replace(day=1), date(ref.year, ref.month, ultimo_dia_do_mes(ref.year, ref.month))
