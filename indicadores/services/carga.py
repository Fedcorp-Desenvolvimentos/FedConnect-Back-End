"""Carga do snapshot da CORP no espelho (RF-IEX-001, T-IEX-1.2, T-IEX-1.3).

Contrato do snapshot (`DEFINICAO-TECNICA.md` §7 do pacote do dono):

    {"gerado_em": "AAAA-MM-DD HH:MM", "extracao": "AAAA-MM-DD",
     "colunas": ["nosnum", "tipdoc", "seg", "ramo", "cli", "inivig", "fimvig", "datemi",
                 "nosnum_ren", "cancelado", "renov_sit", "sin", "cliente"],
     "docs": [[...posicional conforme `colunas`...], ...],
     "clientes": {"<codigo>": ["<cpf_cnpj>", "<F|J>"]},
     "seguradoras": {"<sigla>": "<nome>"}, "ramos": {"<abrev>": "<nome>"},
     "valores": {"<nosnum>": [pretot, val_c, preliq, "<D|R>"]},
     "negocios": {"<nosnum>": ["<codigo>", "<AAAA-MM-DD>"]},
     "fontes": {...}}

As chaves dos mapas são strings; `nosnum` nos docs é inteiro. Nada é corrigido
por suposição: referência desconhecida vira FK nula e rejeito nomeado; data
inválida vira nulo (e, para `datemi`, o texto fica em `datemi_bruta`).

A classificação de renovação (ADR-0009) roda no fim, sobre a base inteira, e
grava `Producao.renovacao` em lote.
"""
import json
import time
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from indicadores.models import CargaCorp, Cliente, Documento, DocumentoNegocio, Producao, Ramo, Seguradora

CHAVES_OBRIGATORIAS = ("gerado_em", "extracao", "colunas", "docs", "clientes", "seguradoras", "ramos", "valores", "negocios")
COLUNAS_OBRIGATORIAS = (
    "nosnum", "tipdoc", "seg", "ramo", "cli", "inivig", "fimvig", "datemi",
    "nosnum_ren", "cancelado", "renov_sit", "sin", "cliente",
)
TIPOS_REJEITO = (
    "cliente_desconhecido", "ramo_desconhecido", "seguradora_desconhecida",
    "datemi_invalida", "inivig_invalida", "fimvig_invalida",
)
LOTE = 2000


class SnapshotInvalido(ValueError):
    """Arquivo fora do contrato: a mensagem diz a chave que faltou."""


# ------------------------------------------------------------------ leitura


def ler_arquivo(caminho) -> dict:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise SnapshotInvalido(f"arquivo não encontrado: {caminho}")
    try:
        with caminho.open(encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError) as erro:
        raise SnapshotInvalido(f"não foi possível ler o JSON de {caminho}: {erro}") from erro
    return dados


def validar_contrato(dados) -> list[str]:
    """Devolve a lista de colunas dos docs; levanta `SnapshotInvalido` com a chave que faltou."""
    if not isinstance(dados, dict):
        raise SnapshotInvalido("o snapshot precisa ser um objeto JSON")
    faltando = [chave for chave in CHAVES_OBRIGATORIAS if chave not in dados]
    if faltando:
        raise SnapshotInvalido(f"chave(s) ausente(s) no snapshot: {', '.join(faltando)}")
    colunas = dados["colunas"]
    if not isinstance(colunas, list):
        raise SnapshotInvalido("`colunas` precisa ser uma lista")
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in colunas]
    if faltando:
        raise SnapshotInvalido(f"coluna(s) ausente(s) em `colunas`: {', '.join(faltando)}")
    for chave in ("clientes", "seguradoras", "ramos", "valores", "negocios"):
        if not isinstance(dados[chave], dict):
            raise SnapshotInvalido(f"`{chave}` precisa ser um objeto")
    if not isinstance(dados["docs"], list):
        raise SnapshotInvalido("`docs` precisa ser uma lista")
    return colunas


# ------------------------------------------------------------------ conversões


def converter_data(valor) -> date | None:
    """`AAAA-MM-DD` → date; vazio, None ou qualquer outra coisa → None."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip())
    except ValueError:
        return None


def converter_decimal(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _inteiro(valor) -> int | None:
    if valor is None or valor == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _texto(valor, limite) -> str:
    return "" if valor is None else str(valor)[:limite]


# ------------------------------------------------------------------ carga


def _upsert(modelo, objetos, unico, campos):
    for inicio in range(0, len(objetos), LOTE):
        modelo.objects.bulk_create(
            objetos[inicio:inicio + LOTE],
            update_conflicts=True,
            unique_fields=[unico],
            update_fields=campos,
        )


def carregar_snapshot(dados: dict, arquivo: str = "", origem: str = CargaCorp.ORIGEM_SNAPSHOT) -> CargaCorp:
    """Grava o snapshot inteiro por upsert numa transação e devolve a `CargaCorp` fechada.

    Contrato quebrado → `SnapshotInvalido`, com a carga registrada como falha.
    """
    inicio = time.monotonic()
    carga = CargaCorp.objects.create(origem=origem, arquivo=_texto(arquivo, 255))
    try:
        colunas = validar_contrato(dados)
    except SnapshotInvalido as erro:
        carga.erro = str(erro)
        carga.concluida_em = timezone.now()
        carga.duracao_ms = int((time.monotonic() - inicio) * 1000)
        carga.save(update_fields=["erro", "concluida_em", "duracao_ms"])
        raise

    carga.gerado_em = _texto(dados.get("gerado_em"), 30)
    carga.extraido_em = converter_data(dados.get("extracao"))

    rejeitos = Counter({tipo: 0 for tipo in TIPOS_REJEITO})
    contagens = {}

    with transaction.atomic():
        clientes = [
            Cliente(codigo=int(codigo), cpf_cnpj=_texto(_item(dado, 0), 20), pessoa=_texto(_item(dado, 1), 1))
            for codigo, dado in dados["clientes"].items()
        ]
        _upsert(Cliente, clientes, "codigo", ["cpf_cnpj", "pessoa"])
        ramos = [Ramo(abreviatura=_texto(abrev, 10), nome=_texto(nome, 100)) for abrev, nome in dados["ramos"].items()]
        _upsert(Ramo, ramos, "abreviatura", ["nome"])
        seguradoras = [
            Seguradora(sigla=_texto(sigla, 10), nome=_texto(nome, 100)) for sigla, nome in dados["seguradoras"].items()
        ]
        _upsert(Seguradora, seguradoras, "sigla", ["nome"])

        codigos_cliente = {c.codigo for c in clientes}
        abrevs_ramo = {r.abreviatura for r in ramos}
        siglas_seg = {s.sigla for s in seguradoras}
        nomes_cliente = {}

        posicao = {nome: colunas.index(nome) for nome in COLUNAS_OBRIGATORIAS}
        producoes = []
        for linha in dados["docs"]:
            producao = _montar_producao(linha, posicao, codigos_cliente, abrevs_ramo, siglas_seg, rejeitos, carga)
            producoes.append(producao)
            if producao.cliente_id is not None and producao.cliente_nome:
                nomes_cliente.setdefault(producao.cliente_id, producao.cliente_nome)
        _upsert(
            Producao, producoes, "nosnum",
            [
                "codfil", "tipdoc", "seguradora", "ramo", "cliente", "cliente_nome", "inivig", "fimvig", "datemi",
                "datemi_bruta", "nosnum_ren", "cancelado", "renovacao_situacao", "sin_situacao", "carga",
            ],
        )
        # O nome do cliente vem só na produção; o mapa `clientes` traz CPF/CNPJ e pessoa.
        if nomes_cliente:
            _upsert(
                Cliente,
                [Cliente(codigo=codigo, nome=nome[:200]) for codigo, nome in nomes_cliente.items()],
                "codigo", ["nome"],
            )

        nosnums = {p.nosnum for p in producoes}
        documentos, negocios = [], []
        for chave, dado in dados["valores"].items():
            nosnum = _inteiro(chave)
            if nosnum in nosnums:
                documentos.append(
                    Documento(
                        producao_id=nosnum,
                        pretot=converter_decimal(_item(dado, 0)),
                        val_c=converter_decimal(_item(dado, 1)),
                        preliq=converter_decimal(_item(dado, 2)),
                        fonte=_texto(_item(dado, 3), 1),
                    )
                )
            else:
                rejeitos["valor_sem_producao"] += 1
        _upsert(Documento, documentos, "producao", ["pretot", "val_c", "preliq", "fonte"])
        for chave, dado in dados["negocios"].items():
            nosnum = _inteiro(chave)
            if nosnum in nosnums:
                negocios.append(
                    DocumentoNegocio(
                        producao_id=nosnum,
                        codigo_negocio=_texto(_item(dado, 0), 30),
                        datinc_negocio=converter_data(_item(dado, 1)),
                    )
                )
            else:
                rejeitos["negocio_sem_producao"] += 1
        _upsert(DocumentoNegocio, negocios, "producao", ["codigo_negocio", "datinc_negocio"])

        contagens = {
            "clientes": len(clientes),
            "ramos": len(ramos),
            "seguradoras": len(seguradoras),
            "producao": len(producoes),
            "documentos": len(documentos),
            "negocios": len(negocios),
            "producao_sem_datemi": sum(1 for p in producoes if p.datemi is None),
        }
        contagens["renovacoes"] = classificar_renovacao()

        carga.contagens = contagens
        carga.rejeitos = dict(rejeitos)
        carga.sucesso = True
        carga.concluida_em = timezone.now()
        carga.duracao_ms = int((time.monotonic() - inicio) * 1000)
        carga.save()
    return carga


def carregar_arquivo(caminho) -> CargaCorp:
    """Atalho do comando: lê o arquivo e carrega. Arquivo inexistente também registra a falha."""
    try:
        dados = ler_arquivo(caminho)
    except SnapshotInvalido as erro:
        CargaCorp.objects.create(
            arquivo=_texto(caminho, 255), erro=str(erro), concluida_em=timezone.now(), duracao_ms=0
        )
        raise
    return carregar_snapshot(dados, arquivo=str(caminho))


def _item(sequencia, indice):
    try:
        return sequencia[indice]
    except (IndexError, KeyError, TypeError):
        return None


def _montar_producao(linha, posicao, codigos_cliente, abrevs_ramo, siglas_seg, rejeitos, carga) -> Producao:
    valor = {nome: _item(linha, indice) for nome, indice in posicao.items()}

    codigo_cliente = _inteiro(valor["cli"])
    if codigo_cliente not in codigos_cliente:
        if codigo_cliente is not None:
            rejeitos["cliente_desconhecido"] += 1
        codigo_cliente = None
    ramo = _texto(valor["ramo"], 10) or None
    if ramo is not None and ramo not in abrevs_ramo:
        rejeitos["ramo_desconhecido"] += 1
        ramo = None
    seguradora = _texto(valor["seg"], 10) or None
    if seguradora is not None and seguradora not in siglas_seg:
        rejeitos["seguradora_desconhecida"] += 1
        seguradora = None

    datas = {}
    for campo in ("inivig", "fimvig", "datemi"):
        bruto = valor[campo]
        datas[campo] = converter_data(bruto)
        if datas[campo] is None and bruto not in (None, ""):
            rejeitos[f"{campo}_invalida"] += 1
    datemi_bruta = "" if datas["datemi"] is not None or valor["datemi"] in (None, "") else _texto(valor["datemi"], 20)

    return Producao(
        nosnum=int(valor["nosnum"]),
        codfil=None,  # ausente no snapshot (PA-020)
        tipdoc=_texto(valor["tipdoc"], 2),
        seguradora_id=seguradora,
        ramo_id=ramo,
        cliente_id=codigo_cliente,
        cliente_nome=_texto(valor["cliente"], 200),
        inivig=datas["inivig"],
        fimvig=datas["fimvig"],
        datemi=datas["datemi"],
        datemi_bruta=datemi_bruta,
        nosnum_ren=_inteiro(valor["nosnum_ren"]),
        cancelado=bool(_inteiro(valor["cancelado"]) or 0),
        renovacao_situacao=_inteiro(valor["renov_sit"]),
        sin_situacao=_inteiro(valor["sin"]),
        carga=carga,
    )


# ------------------------------------------------------------------ renovação


def classificar_renovacao() -> int:
    """Grava `Producao.renovacao` para a base inteira e devolve quantas ficaram verdadeiras.

    Regra do gestor (RF-IEX-001, ADR-0009): a "primeira apólice" de um CPF/CNPJ é
    o menor `(inivig, nosnum)` entre as produções `tipdoc = 'A'` com `inivig`,
    canceladas ou não, de qualquer ramo ou seguradora. Uma produção é renovação
    se `nosnum_ren > 0` ou se a primeira do seu CPF/CNPJ não é ela mesma e vem
    antes dela. Cliente sem CPF/CNPJ só entra pela cadeia `nosnum_ren`.
    """
    linhas = list(
        Producao.objects.values_list("nosnum", "tipdoc", "inivig", "nosnum_ren", "cliente__cpf_cnpj", "renovacao")
    )
    primeira = {}
    for nosnum, tipdoc, inivig, _ren, cpf, _atual in linhas:
        if tipdoc == "A" and inivig is not None and cpf:
            chave = (inivig, nosnum)
            if cpf not in primeira or chave < primeira[cpf]:
                primeira[cpf] = chave

    ligar, desligar, total = [], [], 0
    for nosnum, _tipdoc, inivig, ren, cpf, atual in linhas:
        renovacao = bool(ren and ren > 0)
        if not renovacao and cpf and inivig is not None:
            inicial = primeira.get(cpf)
            # A própria primeira apólice não é menor que ela mesma: fica captação.
            renovacao = inicial is not None and inicial < (inivig, nosnum)
        total += renovacao
        if renovacao != atual:
            (ligar if renovacao else desligar).append(nosnum)

    # Só as linhas que mudaram, em lotes: recarga do mesmo snapshot não escreve nada aqui.
    for nosnums, valor in ((ligar, True), (desligar, False)):
        for inicio in range(0, len(nosnums), LOTE):
            Producao.objects.filter(nosnum__in=nosnums[inicio:inicio + LOTE]).update(renovacao=valor)
    return total
