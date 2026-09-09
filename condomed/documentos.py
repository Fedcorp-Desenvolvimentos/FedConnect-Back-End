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
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
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
    local = turma.local
    unidade = local.unidade_dados
    instrutor = turma.instrutor
    return {
        "titulo": "Lista de presença — Curso CIPA (NR-5)",
        "codigo": turma.codigo,
        "unidade_nome": unidade.get("nome", "CondoMed"),
        "unidade_endereco": unidade.get("endereco", ""),
        "unidade_contato": " · ".join(
            filter(None, [unidade.get("telefone"), unidade.get("email")])
        ),
        "data": data_por_extenso(turma.data),
        "local": local.nome,
        "horario": f"{turma.hora_inicio:%H:%M} às {turma.hora_fim:%H:%M}",
        "instrutor": (
            f"{instrutor.nome} — {instrutor.titulo} · {instrutor.registro}"
            if instrutor
            else "a definir"
        ),
        "situacao": turma.get_status_display(),
        "total": turma.inscricoes.count(),
        "capacidade": local.capacidade,
    }


def nome_arquivo_lista_presenca(turma):
    return f"lista-presenca-cipa-{turma.data:%Y-%m-%d}-{turma.local.codigo.lower()}.pdf"


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


# ---------------------------------------------------------------------------
# Certificado (RF-HIS-006). Reproduz os modelos em Word da Condomed
# (docs/curso-cipa/ANALISE_CERTIFICADO_CIPA.md §1): paisagem 16:9, frente com
# texto e assinatura, verso com o conteúdo programático. Frente e verso com a
# mesma unidade emissora — a do local da turma (PA-008).
# ---------------------------------------------------------------------------

CERTIFICADO_PAGINA = (33.9 * cm, 19.1 * cm)

TEXTO_CERTIFICADO = (
    "Certificamos que <b>{nome}</b>, portador(a) do CPF <b>{cpf}</b>, funcionário(a) "
    "de <b>{condominio}</b>, CNPJ <b>{cnpj}</b>, concluiu os treinamentos para Representante "
    "Nomeado da NR-5 – CIPA, NR-6 Equipamento de Proteção Individual – EPI e Noções Básicas "
    "de Primeiros Socorros, conforme as exigências estabelecidas pela Portaria MTP nº 4.219, "
    "de 20 de dezembro de 2022."
)

CONTEUDO_PROGRAMATICO = [
    "estudo do ambiente, das condições de trabalho, bem como dos riscos originados do processo produtivo;",
    "noções sobre acidentes e doenças relacionadas ao trabalho decorrentes das condições de trabalho e da "
    "exposição aos riscos existentes no estabelecimento e suas medidas de prevenção (noções básicas de primeiros socorros);",
    "metodologia de investigação e análise de acidentes e doenças relacionadas ao trabalho;",
    "princípios gerais de higiene do trabalho e de medidas de prevenção dos riscos (APR/EPI/EPC);",
    "noções sobre as legislações trabalhista e previdenciária relativas à segurança e saúde no trabalho;",
    "noções sobre a inclusão de pessoas com deficiência e reabilitados nos processos de trabalho;",
    "organização da CIPA e outros assuntos necessários ao exercício das atribuições da Comissão; e",
    "prevenção e combate ao assédio sexual e a outras formas de violência no trabalho.",
]

DOURADO = colors.HexColor("#B8860B")


def formatar_cnpj(cnpj):
    d = "".join(c for c in (cnpj or "") if c.isdigit())
    if len(d) != 14:
        return cnpj or ""
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def dados_certificado(certificado):
    """Tudo que o PDF imprime, resolvido do registro — função pura, testável."""
    inscricao = certificado.inscricao
    turma = inscricao.turma
    unidade = turma.local.unidade_dados
    instrutor = turma.instrutor
    return {
        "numero": certificado.numero,
        "codigo_verificacao": str(certificado.codigo_verificacao),
        "nome": inscricao.nome,
        "cpf": formatar_cpf(inscricao.cpf),
        "condominio": inscricao.condominio_nome,
        "cnpj": formatar_cnpj(inscricao.condominio_cnpj),
        "cidade": unidade.get("cidade", ""),
        "data": data_por_extenso(turma.data),
        "turma_codigo": turma.codigo,
        "unidade_nome": unidade.get("nome", "CondoMed"),
        "unidade_linha": " — ".join(
            filter(None, [unidade.get("endereco"), unidade.get("telefone"), unidade.get("email")])
        ),
        "instrutor_nome": instrutor.nome if instrutor else "",
        "instrutor_titulo": instrutor.titulo if instrutor else "",
        "instrutor_registro": instrutor.registro if instrutor else "",
        "emitido_em": certificado.emitido_em,
    }


def _imagem(caminho):
    try:
        return ImageReader(str(caminho)) if Path(caminho).exists() else None
    except Exception:  # asset corrompido não derruba a emissão
        return None


def _imagem_assinatura(instrutor):
    if instrutor is None or not instrutor.assinatura:
        return None
    try:
        with instrutor.assinatura.open("rb") as arquivo:
            return ImageReader(BytesIO(arquivo.read()))
    except Exception:
        return None


def _desenhar_imagem_proporcional(c, imagem, x, y, largura_max, altura_max, ancora="esquerda"):
    if imagem is None:
        return
    iw, ih = imagem.getSize()
    escala = min(largura_max / iw, altura_max / ih)
    w, h = iw * escala, ih * escala
    if ancora == "direita":
        x = x - w
    elif ancora == "centro":
        x = x - w / 2
    c.drawImage(imagem, x, y, width=w, height=h, mask="auto")


def _faixa(c, largura, altura, dados):
    """Faixa colorida do topo com a unidade emissora — igual na frente e no verso."""
    c.setFillColor(AZUL)
    c.rect(0, altura - 1.9 * cm, largura, 1.9 * cm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1.5 * cm, altura - 0.85 * cm, dados["unidade_nome"].upper())
    c.setFont("Helvetica", 8.5)
    c.drawString(1.5 * cm, altura - 1.45 * cm, dados["unidade_linha"])


def _rodape_certificado(c, largura, dados):
    c.setFillColor(CINZA_TEXTO)
    c.setFont("Helvetica", 7.5)
    c.drawString(1.5 * cm, 0.7 * cm, f"Certificado nº {dados['numero']} · verificação {dados['codigo_verificacao']}")
    c.drawRightString(largura - 1.5 * cm, 0.7 * cm, f"Turma {dados['turma_codigo']} · FedConnect / Condomed")


def _frente(c, dados, logos, assinatura):
    largura, altura = CERTIFICADO_PAGINA
    _faixa(c, largura, altura, dados)

    _desenhar_imagem_proporcional(c, logos["condomed"], 1.5 * cm, altura - 5.3 * cm, 6.0 * cm, 2.9 * cm)
    _desenhar_imagem_proporcional(c, logos["condocorp"], largura - 1.5 * cm, altura - 5.1 * cm, 5.0 * cm, 2.6 * cm, ancora="direita")
    # Selo no canto inferior direito, fora da área do texto e do bloco do instrutor.
    _desenhar_imagem_proporcional(c, logos["selo"], largura - 3.8 * cm, 1.4 * cm, 4.2 * cm, 4.2 * cm, ancora="centro")

    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(largura / 2, altura - 8.0 * cm, "Certificado")

    corpo = ParagraphStyle(
        "corpo", fontName="Helvetica", fontSize=12.5, leading=19, textColor=colors.black, alignment=4
    )
    texto = Paragraph(TEXTO_CERTIFICADO.format(**dados), corpo)
    largura_texto = largura - 2 * 2.6 * cm
    _, h = texto.wrap(largura_texto, 8 * cm)
    texto.drawOn(c, 2.6 * cm, altura - 9.0 * cm - h)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11.5)
    c.drawString(2.6 * cm, 6.9 * cm, f"{dados['cidade']}, {dados['data']}.")

    # Bloco do instrutor: assinatura sobre a linha, nome, título e registro.
    x = 2.6 * cm
    _desenhar_imagem_proporcional(c, assinatura, x, 4.35 * cm, 6.2 * cm, 2.0 * cm)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.6)
    c.line(x, 4.2 * cm, x + 8.5 * cm, 4.2 * cm)
    c.setFont("Helvetica", 8)
    c.setFillColor(CINZA_TEXTO)
    c.drawString(x, 3.7 * cm, "INSTRUTOR DO CURSO")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(x, 3.1 * cm, dados["instrutor_nome"].upper())
    c.setFont("Helvetica", 9)
    c.drawString(x, 2.55 * cm, dados["instrutor_titulo"])
    c.drawString(x, 2.05 * cm, dados["instrutor_registro"])

    _rodape_certificado(c, largura, dados)


def _verso(c, dados, logos):
    largura, altura = CERTIFICADO_PAGINA
    _faixa(c, largura, altura, dados)
    _desenhar_imagem_proporcional(c, logos["condomed"], 1.5 * cm, altura - 5.0 * cm, 5.2 * cm, 2.5 * cm)

    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2.6 * cm, altura - 6.6 * cm, "CONTEÚDO PROGRAMÁTICO:")

    item = ParagraphStyle("item", fontName="Helvetica", fontSize=10.5, leading=15, textColor=colors.black)
    y = altura - 7.6 * cm
    largura_texto = largura - 2 * 2.6 * cm - 1.0 * cm
    for indice, linha in enumerate(CONTEUDO_PROGRAMATICO, 1):
        par = Paragraph(f"{indice}. {linha}", item)
        _, h = par.wrap(largura_texto, 4 * cm)
        y -= h
        par.drawOn(c, 3.2 * cm, y)
        y -= 0.25 * cm

    c.setFillColor(CINZA_TEXTO)
    c.setFont("Helvetica", 8.5)
    c.drawString(2.6 * cm, 2.2 * cm, f"Participante: {dados['nome']} · CPF {dados['cpf']}")
    _rodape_certificado(c, largura, dados)


def gerar_certificados(certificados, usuario=None):
    """PDF em bytes com frente e verso de cada certificado, na ordem recebida (ADR-0007)."""
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=CERTIFICADO_PAGINA)
    # Sem compressão: o conteúdo (nome, CPF, número) fica legível no arquivo e testável.
    c.setPageCompression(0)
    c.setTitle("Certificados — Curso CIPA (Condomed)")
    c.setAuthor(getattr(usuario, "nome_completo", "") or getattr(usuario, "email", "") or "FedConnect")
    logos = {
        "condomed": _imagem(ASSETS / "logo-condomed.jpeg"),
        "condocorp": _imagem(ASSETS / "logo-condocorp.jpeg"),
        "selo": _imagem(ASSETS / "selo-condomed.png"),
    }
    assinaturas = {}
    for certificado in certificados:
        dados = dados_certificado(certificado)
        instrutor = certificado.inscricao.turma.instrutor
        if instrutor is not None and instrutor.pk not in assinaturas:
            assinaturas[instrutor.pk] = _imagem_assinatura(instrutor)
        _frente(c, dados, logos, assinaturas.get(instrutor.pk) if instrutor else None)
        c.showPage()
        _verso(c, dados, logos)
        c.showPage()
    c.save()
    return buffer.getvalue()
