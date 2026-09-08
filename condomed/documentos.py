# condomed/documentos.py
"""Documentos em PDF do curso CIPA, gerados a partir do registro (RF-HIS-003).

O PDF não é armazenado: é montado na hora, a partir da turma e dos inscritos.
Mudança de layout vale para o próximo download; o conteúdo é sempre o que está
no banco. Assets (logo, assinaturas) vivem em `condomed/assets/`.

A lista de presença é o documento que vai impresso para o dia do curso: quem
assina é o participante, em bloco por condomínio — por isso a ordem é
condomínio → nome, e por isso há linhas em branco no fim (chega gente de
última hora; ADR-0006). O que entrar à mão vira inscrição depois.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import INSTRUTORES_CIPA, LOCAIS_CIPA

ASSETS = Path(__file__).resolve().parent / "assets"

# Quantas linhas em branco a lista traz para inscrições feitas no dia.
# Hipótese de trabalho (PA-007); muda com uma resposta do solicitante.
LINHAS_EXTRAS_PADRAO = 5

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

AZUL = colors.HexColor("#0F3D5D")
CINZA_TEXTO = colors.HexColor("#475569")
CINZA_LINHA = colors.HexColor("#CBD5E1")
CINZA_FUNDO = colors.HexColor("#F1F5F9")


def formatar_cpf(cpf):
    """000.000.000-00 a partir de 11 dígitos; devolve o que veio se não tiver 11."""
    digitos = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(digitos) != 11:
        return cpf or ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def data_por_extenso(data):
    return f"{data.day} de {MESES[data.month - 1]} de {data.year}"


def linhas_lista_presenca(turma, linhas_extras=LINHAS_EXTRAS_PADRAO):
    """Linhas da tabela, na ordem em que as pessoas assinam: por condomínio, depois nome.

    Função pura (sem PDF) para ser testável: é aqui que a regra de ordem e de
    linhas extras vive.
    """
    inscritos = sorted(
        turma.inscricoes.all(),
        key=lambda i: ((i.condominio_nome or "").casefold(), (i.nome or "").casefold()),
    )
    linhas = [
        {
            "numero": indice,
            "nome": inscrito.nome,
            "cpf": formatar_cpf(inscrito.cpf),
            "condominio": inscrito.condominio_nome,
            "administradora": inscrito.administradora_nome or "",
            "funcao": inscrito.funcao or "",
            "extra": False,
        }
        for indice, inscrito in enumerate(inscritos, 1)
    ]
    for indice in range(len(linhas) + 1, len(linhas) + 1 + linhas_extras):
        linhas.append({
            "numero": indice, "nome": "", "cpf": "", "condominio": "",
            "administradora": "", "funcao": "", "extra": True,
        })
    return linhas


def cabecalho_lista_presenca(turma):
    """Dados do cabeçalho, resolvidos a partir do local e do instrutor da turma."""
    local = LOCAIS_CIPA.get(turma.local, {})
    unidade = local.get("unidade", {})
    instrutor = INSTRUTORES_CIPA.get(turma.instrutor)
    return {
        "titulo": "Lista de presença — Curso CIPA (NR-5)",
        "codigo": turma.codigo,
        "unidade_nome": unidade.get("nome", "CondoMed"),
        "unidade_endereco": unidade.get("endereco", ""),
        "unidade_contato": " · ".join(
            filter(None, [unidade.get("telefone"), unidade.get("email")])
        ),
        "data": data_por_extenso(turma.data),
        "local": local.get("nome", turma.local),
        "horario": f"{turma.hora_inicio:%H:%M} às {turma.hora_fim:%H:%M}",
        "instrutor": (
            f"{instrutor['nome']} — {instrutor['titulo']} · MTE/{instrutor['registro_uf']} {instrutor['registro_mte']}"
            if instrutor
            else "a definir"
        ),
        "situacao": turma.get_status_display(),
        "total": turma.inscricoes.count(),
        "capacidade": local.get("capacidade"),
    }


def nome_arquivo_lista_presenca(turma):
    return f"lista-presenca-cipa-{turma.data:%Y-%m-%d}-{turma.local.lower()}.pdf"


def gerar_lista_presenca(turma, usuario=None, linhas_extras=LINHAS_EXTRAS_PADRAO):
    """PDF da lista de presença em bytes. A4 paisagem, tabela com coluna de assinatura."""
    cabecalho = cabecalho_lista_presenca(turma)
    linhas = linhas_lista_presenca(turma, linhas_extras)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.2 * cm, bottomMargin=1.5 * cm,
        title=cabecalho["titulo"],
        author=cabecalho["unidade_nome"],
    )

    titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=15, textColor=AZUL, leading=18)
    meta = ParagraphStyle("meta", fontName="Helvetica", fontSize=9, textColor=CINZA_TEXTO, leading=12, alignment=TA_LEFT)
    meta_forte = ParagraphStyle("meta_forte", parent=meta, fontName="Helvetica-Bold", textColor=AZUL)
    celula = ParagraphStyle("celula", fontName="Helvetica", fontSize=8.5, leading=10.5)
    celula_topo = ParagraphStyle("celula_topo", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, leading=10)

    elementos = []

    # --- cabeçalho: logo à esquerda, dados à direita ---
    logo_path = ASSETS / "logo-condomed.jpeg"
    bloco_texto = [
        Paragraph(cabecalho["titulo"], titulo),
        Spacer(0, 3),
        Paragraph(
            f"<b>{cabecalho['codigo']}</b> · <b>{cabecalho['data']}</b> · {cabecalho['local']}"
            f" · {cabecalho['horario']} · situação: {cabecalho['situacao']}",
            meta_forte,
        ),
        Paragraph(f"Instrutor: {cabecalho['instrutor']}", meta),
        Paragraph(
            f"{cabecalho['unidade_nome']} · {cabecalho['unidade_endereco']}"
            + (f" · {cabecalho['unidade_contato']}" if cabecalho["unidade_contato"] else ""),
            meta,
        ),
        Paragraph(
            f"Inscritos: <b>{cabecalho['total']}</b>"
            + (f" (capacidade do local: {cabecalho['capacidade']})" if cabecalho["capacidade"] else ""),
            meta,
        ),
    ]
    if logo_path.exists():
        logo = Image(str(logo_path), width=3.6 * cm, height=2.7 * cm, kind="proportional")
        topo = Table([[logo, bloco_texto]], colWidths=[4.2 * cm, None])
        topo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        elementos.append(topo)
    else:
        elementos.extend(bloco_texto)
    elementos.append(Spacer(0, 10))

    # --- tabela ---
    colunas = ["Nº", "Nome", "CPF", "Condomínio", "Administradora", "Função", "Assinatura"]
    larguras = [1.0 * cm, 6.2 * cm, 3.0 * cm, 4.6 * cm, 4.2 * cm, 3.0 * cm, 4.7 * cm]
    dados = [[Paragraph(c, celula_topo) for c in colunas]]
    for linha in linhas:
        dados.append([
            Paragraph(str(linha["numero"]), celula),
            Paragraph(linha["nome"], celula),
            Paragraph(linha["cpf"], celula),
            Paragraph(linha["condominio"], celula),
            Paragraph(linha["administradora"], celula),
            Paragraph(linha["funcao"], celula),
            "",  # assinatura: em branco, de propósito
        ])

    tabela = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("BOX", (0, 0), (-1, -1), 0.6, CINZA_LINHA),
        ("LINEBEFORE", (6, 0), (6, -1), 0.6, CINZA_LINHA),
        # ~1 cm de altura por linha: é para assinar à mão, não só para ler.
        ("TOPPADDING", (0, 1), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 11),
    ]
    primeira_extra = next((i for i, l in enumerate(linhas, 1) if l["extra"]), None)
    if primeira_extra:
        estilo.append(("BACKGROUND", (0, primeira_extra), (-1, -1), CINZA_FUNDO))
    tabela.setStyle(TableStyle(estilo))
    elementos.append(tabela)

    elementos.append(Spacer(0, 6))
    elementos.append(Paragraph(
        "Linhas em cinza: inscrições feitas no dia — registrar no sistema depois do curso.",
        meta,
    ))
    elementos.append(Spacer(0, 22))
    elementos.append(Paragraph(
        "_______________________________________________<br/>"
        f"Instrutor: {cabecalho['instrutor']}",
        meta,
    ))

    gerado_em = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else datetime.now()
    quem = getattr(usuario, "nome_completo", "") or getattr(usuario, "email", "") or ""

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(CINZA_TEXTO)
        canvas.drawString(
            documento.leftMargin, 0.8 * cm,
            f"Gerado em {gerado_em:%d/%m/%Y %H:%M}" + (f" por {quem}" if quem else "") + " · FedConnect / Condomed",
        )
        canvas.drawRightString(
            documento.pagesize[0] - documento.rightMargin, 0.8 * cm, f"Página {documento.page}"
        )
        canvas.restoreState()

    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()
