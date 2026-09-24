"""Extração do Data Lake CORP no formato que `carga.py` já sabe carregar.

Esta é a fase 2 prevista na ADR-0009: a segunda origem do espelho. O que ela
NÃO faz é tão importante quanto o que faz.

**Não escreve no espelho.** Monta o mesmo dicionário do snapshot e entrega a
`carregar_snapshot`, que já valida contrato, faz o upsert, conta rejeito e
classifica renovação. Um segundo escritor duplicaria essas quatro coisas e as
faria divergir na primeira mudança — foi exatamente o que aconteceu com a
regra de renovação entre o lake e este repositório, corrigido em 23/09/2026.

**Não reclassifica renovação.** O lake tem a coluna pronta em
`vw_documento_renovacao`, e a decisão de 23/09/2026 (ADR-0018 do pacote do
lake) é que a regra mora lá. `carregar_snapshot` recalcula porque precisa
funcionar para o snapshot; quando o lake for a única origem, aquele passo sai.

**Não traduz nome de campo.** O lake publica os nomes da CORP e este módulo os
repassa, como manda a RNF-IEX-002.

O acesso é somente-leitura, pelo papel `lake_financeiro`, que enxerga views e
nenhuma tabela.
"""
from __future__ import annotations

import datetime
import re

from django.conf import settings

# As colunas de `docs`, na ordem do contrato do snapshot (§7 do pacote do dono).
COLUNAS = [
    "nosnum", "tipdoc", "seg", "ramo", "cli", "inivig", "fimvig", "datemi",
    "nosnum_ren", "cancelado", "renov_sit", "sin", "cliente",
]

# Tudo vem de `vw_documento_financeiro`: é a view que o papel `lake_financeiro`
# enxerga, e o contrato publicado pelo lake. Ler a tabela `documento` por baixo
# dela funcionaria com um papel mais largo e quebraria no dia em que o lake
# renomeasse uma coluna sem avisar — a view existe para absorver isso.
# `tipdoc` NÃO é filtrado: o espelho quer endosso também, e quem decide o que
# entra em cada indicador é o endpoint, não a carga. Documento que a origem
# deixou de devolver (`ausente_na_origem_em`, decisão do pacote do lake em
# 23/09/2026) fica de fora: a CORP não o tem mais, e o espelho não pode tê-lo.
# `nosnum_ren` é `renovacao_de_nosnum` (chave interna da apólice renovada);
# `renovacao_de` na view é o número EXTERNO da apólice e não cabe num inteiro.
SQL_DOCUMENTOS = """
    SELECT nosnum, tipdoc, seguradora_sigla, ramo_sigla, cliente_codigo,
           inicio_vigencia, fim_vigencia, data_emissao,
           renovacao_de_nosnum,
           cancelado::int, sit_renovacao, sit_sinistro, cliente
      FROM vw_documento_financeiro
     WHERE ausente_na_origem_em IS NULL
"""

# Cadastros: só o que algum documento referencia — é tudo de que o espelho precisa.
SQL_CLIENTES = """
    SELECT DISTINCT cliente_codigo, coalesce(cliente_cpf_cnpj, ''), coalesce(cliente_pessoa, '')
      FROM vw_documento_financeiro
     WHERE cliente_codigo IS NOT NULL
"""

SQL_SEGURADORAS = """
    SELECT DISTINCT seguradora_sigla, coalesce(seguradora, '')
      FROM vw_documento_financeiro
     WHERE seguradora_sigla IS NOT NULL
"""

SQL_RAMOS = """
    SELECT DISTINCT ramo_sigla, coalesce(ramo, '')
      FROM vw_documento_financeiro
     WHERE ramo_sigla IS NOT NULL
"""

# Prêmio e comissão vêm SEMPRE do detalhe do documento no lake, nunca do feed
# de renovações — por isso a fonte é 'D' fixa. É a fonte autoritativa, e o
# snapshot marcava 'R' só onde não tinha o detalhe.
SQL_VALORES = """
    SELECT nosnum, premio_total, comissao_valor, premio_liquido
      FROM vw_documento_financeiro
     WHERE ausente_na_origem_em IS NULL
       AND (premio_total IS NOT NULL OR comissao_valor IS NOT NULL OR premio_liquido IS NOT NULL)
"""

# A última corrida do lake, para registrar de quando é a extração. Sem isto, a
# `CargaCorp` diria a hora em que ESTE processo rodou, e não a idade do dado —
# que é a pergunta que alguém faz quando o número parece velho.
SQL_EXTRACAO = """
    SELECT max(terminada_em)
      FROM _lake_execucao
     WHERE status = 'concluida'
"""


def dsn_do_lake() -> str:
    dsn = getattr(settings, "LAKE_DSN", "") or ""
    if not dsn:
        raise RuntimeError(
            "LAKE_DSN não configurada — a carga pelo lake não tem de onde ler. "
            "Use o papel `lake_financeiro`, que é somente-leitura."
        )
    return dsn


def mascarar(dsn: str) -> str:
    """O DSN sem a senha, para gravar em `CargaCorp.arquivo` sem vazá-la."""
    return re.sub(r"(://[^:@/]+:)[^@]+(@)", r"\1***\2", dsn or "")


def _data(valor) -> str:
    """O contrato do snapshot é texto ISO; o psycopg devolve `date`."""
    if valor is None:
        return ""
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def extrair(dsn: str | None = None) -> dict:
    """Lê o lake e devolve o dicionário no contrato do snapshot.

    Uma conexão, cinco consultas, nada de paginação: o volume é de dezenas de
    milhares de linhas e cabe na memória — o mesmo que o snapshot já fazia.
    """
    # psycopg2, e nao psycopg v3: e o que o projeto ja tem em requirements.
    # Acrescentar driver por preferencia de versao seria pagar dependencia nova
    # para ler seis consultas.
    import psycopg2

    dsn = dsn or dsn_do_lake()
    agora = datetime.datetime.now()
    conexao = psycopg2.connect(dsn, connect_timeout=20)
    try:
        # Somente leitura, declarado na sessao: se algum dia este modulo tentar
        # escrever no lake, falha aqui em vez de escrever.
        conexao.set_session(readonly=True, autocommit=True)
        with conexao.cursor() as cursor:
                cursor.execute(SQL_EXTRACAO)
                linha = cursor.fetchone()
                extraido = linha[0] if linha else None

                cursor.execute(SQL_DOCUMENTOS)
                docs = [
                    [
                        n, t or "", seg or "", ramo or "", cli,
                        _data(ini), _data(fim), _data(emi),
                        ren, bool(canc), sit_ren, sit_sin, nome or "",
                    ]
                    for (n, t, seg, ramo, cli, ini, fim, emi, ren, canc, sit_ren, sit_sin, nome) in cursor
                ]

                cursor.execute(SQL_CLIENTES)
                clientes = {str(codigo): [cpf, pessoa] for codigo, cpf, pessoa in cursor}

                cursor.execute(SQL_SEGURADORAS)
                seguradoras = {sigla: nome for sigla, nome in cursor}

                cursor.execute(SQL_RAMOS)
                ramos = {abrev: nome for abrev, nome in cursor}

                cursor.execute(SQL_VALORES)
                valores = {
                    str(nosnum): [
                        str(pretot) if pretot is not None else None,
                        str(val_c) if val_c is not None else None,
                        str(preliq) if preliq is not None else None,
                        "D",
                    ]
                    for nosnum, pretot, val_c, preliq in cursor
                }

                # `documento_negocio` não está no contrato do financeiro, e nenhum
                # endpoint dos indicadores lê `DocumentoNegocio` (medido em 23/09/2026).
                # Fica vazio até a captação ser decidida — ela virá da lista de
                # negócios em andamento da CORP, não desta tabela.
                negocios = {}
    finally:
        conexao.close()

    return {
        "gerado_em": agora.strftime("%Y-%m-%d %H:%M"),
        # A data da extração é a da última corrida CONCLUÍDA do lake, e não a
        # de hoje: é ela que diz a idade do dado.
        "extracao": _data(extraido) or agora.strftime("%Y-%m-%d"),
        "colunas": list(COLUNAS),
        "docs": docs,
        "clientes": clientes,
        "seguradoras": seguradoras,
        "ramos": ramos,
        "valores": valores,
        "negocios": negocios,
        "fontes": {"lake": mascarar(dsn)},
    }
