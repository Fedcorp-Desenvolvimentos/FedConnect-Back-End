"""Planilha e PDF do relatório de faturas pendentes (RF-FAT-002, RF-FAT-003).

Funções puras sobre a resposta do FedHub: recebem `dados` (`data`, `totais`,
`filtros`, `referencia`) e devolvem bytes. O PDF reproduz o relatório do
legado (PA-014): A4 retrato, cabeçalho com data, título e "Página N de M",
linha "DATA: de A até", tabela com dois renglões por documento e rodapé com
"N Fatura(s)" e TOTAL GERAL.
"""
from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TITULO = "RELATÓRIO DE FATURAS PENDENTES"

ROTULO_SITUACAO = {"vencidas": "Vencidas", "a_vencer": "A vencer", "todas": "Todas"}
ROTULO_CLASSIFICACAO = {
    "todas": "Todas as faturas",
    "com_obs": "Somente com OBS preenchida",
    "sem_obs_sem_deposito": "OBS não preenchida e sem depósito em C/C",
    "deposito_cc": "Depósito em conta corrente",
}

COLUNAS_PLANILHA = [
    ("fatura", "Fatura"),
    ("documento", "Documento"),
    ("sacado", "Sacado"),
    ("produto", "Produto"),
    ("obs", "OBS"),
    ("vigencia", "Vigência"),
    ("vencimento", "Vencimento"),
    ("dias_atraso", "Dias em atraso"),
    ("valor", "Valor do documento (R$)"),
    ("parcela", "Parcela"),
    ("administradora_nome", "Administradora"),
    ("seguradora_nome", "Seguradora"),
    ("cedente", "Cedente"),
    ("apolice", "Apólice"),
    ("nosso_numero", "Nosso número"),
    ("deposito_cc", "Depósito em C/C"),
]


def _data_br(valor) -> str:
    if not valor:
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(valor)


def _data_iso_para_date(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor)[:10]).date()
    except ValueError:
        return None


def moeda_br(valor) -> str:
    numero = float(valor or 0)
    inteiro, decimal = f"{numero:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{decimal}"


def nome_arquivo(extensao: str, referencia: str = "") -> str:
    dia = referencia or date.today().isoformat()
    return f"faturas-pendentes-{dia}.{extensao}"


def descrever_filtros(filtros: Dict[str, Any]) -> List[str]:
    """Filtros aplicados em texto, para o cabeçalho do PDF e a aba da planilha."""
    partes = []
    if filtros.get("situacao"):
        partes.append(f"Situação: {ROTULO_SITUACAO.get(filtros['situacao'], filtros['situacao'])}")
    if filtros.get("classificacao"):
        partes.append(ROTULO_CLASSIFICACAO.get(filtros["classificacao"], filtros["classificacao"]))
    for chave, rotulo in (("fatura", "Fatura"), ("administradora", "Administradora"), ("seguradora", "Seguradora"),
                          ("cedente", "Cedente"), ("apolice", "Apólice")):
        if filtros.get(chave):
            partes.append(f"{rotulo}: {filtros[chave]}")
    if filtros.get("vigencia_ini"):
        partes.append(f"Vigência a partir de {_data_br(filtros['vigencia_ini'])}")
    if filtros.get("ordenar_por"):
        partes.append(f"Ordenado por {filtros['ordenar_por']}")
    return partes


# ---------------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------------

def gerar_planilha(dados: Dict[str, Any]) -> bytes:
    """Uma linha por documento, valores como número, datas como data, linha de totais."""
    linhas = dados.get("data", [])
    totais = dados.get("totais", {})
    wb = Workbook()
    ws = wb.active
    ws.title = "Faturas pendentes"

    cabecalho_fill = PatternFill("solid", fgColor="0F3D5D")
    for indice, (_, rotulo) in enumerate(COLUNAS_PLANILHA, start=1):
        celula = ws.cell(row=1, column=indice, value=rotulo)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = cabecalho_fill
        celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30

    for r, linha in enumerate(linhas, start=2):
        for c, (chave, _) in enumerate(COLUNAS_PLANILHA, start=1):
            valor = linha.get(chave)
            if chave == "vencimento":
                valor = _data_iso_para_date(valor)
                celula = ws.cell(row=r, column=c, value=valor)
                celula.number_format = "DD/MM/YYYY"
                continue
            if chave == "valor":
                celula = ws.cell(row=r, column=c, value=float(valor or 0))
                celula.number_format = '"R$" #,##0.00'
                continue
            ws.cell(row=r, column=c, value=valor)

    linha_total = len(linhas) + 2
    ws.cell(row=linha_total, column=1, value=f"{totais.get('documentos', len(linhas))} documento(s)").font = Font(bold=True)
    ws.cell(row=linha_total, column=2, value=f"{totais.get('faturas', 0)} fatura(s)").font = Font(bold=True)
    ws.cell(row=linha_total, column=8, value="TOTAL GERAL").font = Font(bold=True)
    celula_total = ws.cell(row=linha_total, column=9, value=float(totais.get("valor_total", 0)))
    celula_total.font = Font(bold=True)
    celula_total.number_format = '"R$" #,##0.00'

    larguras = [10, 14, 38, 36, 24, 10, 12, 10, 18, 10, 36, 24, 10, 12, 16, 18]
    for indice, largura in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(indice)].width = largura
    ws.freeze_panes = "A2"

    aba = wb.create_sheet("Filtros")
    aba.append(["Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")])
    aba.append(["Referência", _data_br(dados.get("referencia"))])
    for texto in descrever_filtros(dados.get("filtros", {})):
        aba.append([texto])
    aba.column_dimensions["A"].width = 60

    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

AZUL = colors.HexColor("#0F3D5D")
CINZA = colors.HexColor("#64748B")
PONTILHADO = colors.HexColor("#94A3B8")

_estilo_base = ParagraphStyle("base", fontName="Helvetica", fontSize=7.2, leading=8.6)
_estilo_negrito = ParagraphStyle("negrito", parent=_estilo_base, fontName="Helvetica-Bold")
_estilo_direita = ParagraphStyle("direita", parent=_estilo_base, alignment=TA_RIGHT)
_estilo_cabecalho = ParagraphStyle("cab", parent=_estilo_negrito, fontSize=6.8, leading=8, alignment=TA_CENTER)
_estilo_cinza = ParagraphStyle("cinza", parent=_estilo_base, textColor=CINZA)


class _CanvasNumerado(rl_canvas.Canvas):
    """Canvas que escreve "Página N de M" no fim, quando M já é conhecido."""

    def __init__(self, *args, cabecalho=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []
        self._cabecalho = cabecalho or {}

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._desenhar_cabecalho(total)
            super().showPage()
        super().save()

    def _desenhar_cabecalho(self, total):
        largura, altura = A4
        topo = altura - 1.2 * cm
        self.setFont("Helvetica-Bold", 8)
        self.drawString(1.5 * cm, topo, self._cabecalho.get("data_geracao", ""))
        self.setFont("Helvetica-Bold", 14)
        self.drawCentredString(largura / 2, topo - 0.1 * cm, TITULO)
        self.setFont("Helvetica-Bold", 8)
        self.drawRightString(largura - 1.5 * cm, topo, f"Página {self._pageNumber} de {total}")
        self.setFont("Helvetica-Bold", 8)
        self.drawCentredString(largura / 2, topo - 0.75 * cm, self._cabecalho.get("linha_periodo", ""))
        self.setFont("Helvetica", 7)
        self.drawCentredString(largura / 2, topo - 1.2 * cm, self._cabecalho.get("linha_filtros", ""))


def _paragrafo(texto, estilo=_estilo_base):
    return Paragraph((texto or "").replace("&", "&amp;").replace("<", "&lt;"), estilo)


def linhas_da_tabela(linhas: List[Dict[str, Any]]):
    """Cabeçalho (2 linhas) + 2 renglões por documento, e os comandos de estilo por par."""
    dados = [
        [_paragrafo("", _estilo_cabecalho), _paragrafo("", _estilo_cabecalho), _paragrafo("", _estilo_cabecalho),
         _paragrafo("", _estilo_cabecalho), _paragrafo("DATA", _estilo_cabecalho),
         _paragrafo("VALOR", _estilo_cabecalho), _paragrafo("DATA", _estilo_cabecalho), _paragrafo("VALOR", _estilo_cabecalho)],
        [_paragrafo("FATURA", _estilo_cabecalho), _paragrafo("DOCUMENTO", _estilo_cabecalho),
         _paragrafo("PRODUTO/OBS", _estilo_cabecalho), _paragrafo("VIGÊNCIA", _estilo_cabecalho),
         _paragrafo("VENCIMENTO", _estilo_cabecalho), _paragrafo("DOCUMENTO", _estilo_cabecalho),
         _paragrafo("PAGAMENTO", _estilo_cabecalho), _paragrafo("PAGO", _estilo_cabecalho)],
    ]
    estilos = [
        ("SPAN", (2, 0), (3, 0)),
        ("LINEBELOW", (0, 1), (-1, 1), 0.8, AZUL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]
    for indice, linha in enumerate(linhas):
        r1 = 2 + indice * 2
        r2 = r1 + 1
        produto_obs = linha.get("produto") or ""
        if linha.get("obs"):
            produto_obs = f"{produto_obs} — {linha['obs']}" if produto_obs else linha["obs"]
        dados.append([
            _paragrafo(str(linha.get("fatura") or ""), _estilo_negrito),
            _paragrafo(linha.get("documento"), _estilo_negrito),
            _paragrafo(linha.get("sacado")),
            _paragrafo(linha.get("vigencia")),
            _paragrafo(_data_br(linha.get("vencimento"))),
            _paragrafo(moeda_br(linha.get("valor")), _estilo_direita),
            _paragrafo(""),
            _paragrafo(""),
        ])
        dados.append([
            _paragrafo(""),
            _paragrafo(produto_obs, _estilo_cinza),
            _paragrafo(""),
            _paragrafo(""),
            _paragrafo(linha.get("parcela"), _estilo_negrito),
            _paragrafo(linha.get("administradora_nome"), _estilo_negrito),
            _paragrafo(""),
            _paragrafo(""),
        ])
        estilos += [
            ("SPAN", (1, r2), (3, r2)),          # produto/OBS ocupa documento..vigência
            ("SPAN", (5, r2), (7, r2)),          # administradora ocupa valor..pago
            ("LINEBELOW", (0, r2), (-1, r2), 0.4, PONTILHADO, None, (1, 2)),
        ]
    return dados, estilos


def gerar_pdf(dados: Dict[str, Any]) -> bytes:
    linhas = dados.get("data", [])
    totais = dados.get("totais", {})
    filtros = dados.get("filtros", {})

    periodo_ini = _data_br(filtros.get("vencimento_ini")) or "__/__/____"
    periodo_fim = _data_br(filtros.get("vencimento_fim")) or "__/__/____"
    cabecalho = {
        "data_geracao": datetime.now().strftime("%d/%m/%Y"),
        "linha_periodo": f"DATA: {periodo_ini}   A   {periodo_fim}",
        "linha_filtros": " · ".join(descrever_filtros(filtros)),
    }

    saida = BytesIO()
    doc = SimpleDocTemplate(
        saida, pagesize=A4,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm, topMargin=2.9 * cm, bottomMargin=1.3 * cm,
        title=TITULO, author="FedConnect",
    )
    largura_util = A4[0] - doc.leftMargin - doc.rightMargin
    proporcoes = [0.09, 0.12, 0.30, 0.08, 0.11, 0.11, 0.10, 0.09]
    larguras = [largura_util * p for p in proporcoes]

    dados_tabela, estilos = linhas_da_tabela(linhas)
    tabela = Table(dados_tabela, colWidths=larguras, repeatRows=2)
    tabela.setStyle(TableStyle(estilos))

    rodape = Table(
        [[
            _paragrafo(f"{totais.get('faturas', 0)} Fatura(s) · {totais.get('documentos', len(linhas))} documento(s)", _estilo_negrito),
            _paragrafo("TOTAL GERAL", ParagraphStyle("tg", parent=_estilo_negrito, fontSize=8.5, alignment=TA_RIGHT)),
            _paragrafo(moeda_br(totais.get("valor_total", 0)), ParagraphStyle("tv", parent=_estilo_negrito, fontSize=8.5, alignment=TA_RIGHT)),
            _paragrafo(moeda_br(totais.get("valor_pago", 0)), ParagraphStyle("tp", parent=_estilo_negrito, fontSize=8.5, alignment=TA_RIGHT)),
        ]],
        colWidths=[largura_util * 0.5, largura_util * 0.2, largura_util * 0.15, largura_util * 0.15],
    )
    rodape.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.8, AZUL), ("TOPPADDING", (0, 0), (-1, 0), 6)]))

    elementos = [tabela, Spacer(1, 0.3 * cm), rodape]
    if not linhas:
        elementos.insert(1, _paragrafo("Nenhuma fatura pendente para os filtros informados.", _estilo_cinza))

    doc.build(elementos, canvasmaker=lambda *a, **k: _CanvasNumerado(*a, cabecalho=cabecalho, **k))
    return saida.getvalue()
