"""FedHub de mentira para a suíte do app `indicadores` (RF-IEX-010).

Desde 23/09/2026 as metas moram no lake e chegam pelo FedHub (`/api/lake/metas`).
Nenhum teste pode depender do FedHub real: este módulo implementa as quatro
rotas em memória, com a mesma semântica (upsert pela chave, réplica de meses,
409 em chave ocupada, 404 em id inexistente, `fora` para simular lake caído).
`_ComCarga` (tests.py) o liga em todo `setUp`.
"""
from decimal import Decimal

from indicadores.services import fedhub_lake
from indicadores.services import metas as servico_metas

NOMES_SEG = {"ALLI": "ALLIANZ", "PORT": "PORTO", "TOKI": "TOKIO"}
NOMES_RAMO = {"COND": "CONDOMINIO", "FIAN": "FIANCA", "AUTO": "AUTOMOVEL"}


class FedHubFalso:
    """`/api/lake/metas` em memória, com a semântica do FedHub real."""

    def __init__(self):
        self.metas = {}
        self.proximo = 1
        self.fora = False

    def _linha(self, m):
        return {
            "id": m["id"], "seguradora": m["seguradora"], "seguradora_nome": NOMES_SEG.get(m["seguradora"], ""),
            "ramo": m["ramo"], "ramo_nome": NOMES_RAMO.get(m["ramo"], ""), "codram": 0,
            "competencia": m["competencia"], "valor_meta": str(Decimal(m["valor_meta"]).quantize(Decimal("0.01"))),
            "atualizado_em": None, "atualizado_por": m.get("usuario"),
        }

    def criar(self, seguradora, ramo, valor, competencia="2026-09", usuario=None):
        """Atalho dos testes (o antigo `meta()`): grava direto no servidor falso."""
        chave = (seguradora, ramo, competencia)
        for m in self.metas.values():
            if (m["seguradora"], m["ramo"], m["competencia"]) == chave:
                m["valor_meta"] = str(valor)
                return self._linha(m)
        m = {"id": self.proximo, "seguradora": seguradora, "ramo": ramo, "competencia": competencia,
             "valor_meta": str(valor), "usuario": usuario}
        self.metas[m["id"]] = m
        self.proximo += 1
        return self._linha(m)

    def chamar(self, metodo, caminho, *, params=None, json=None):
        if self.fora:
            raise fedhub_lake.LakeIndisponivel("lake_indisponivel", "o Postgres do lake não respondeu")
        if metodo == "GET":
            comp = params["competencia"]
            linhas = sorted((m for m in self.metas.values() if m["competencia"] == comp),
                            key=lambda m: (m["seguradora"], m["ramo"]))
            total = sum(Decimal(m["valor_meta"]) for m in linhas)
            return {"competencia": comp, "metas": [self._linha(m) for m in linhas],
                    "total_meta": str(total.quantize(Decimal("0.01"))) if linhas else None}
        if metodo == "POST":
            gravadas = []
            for k in range(json.get("replicar_meses", 0) + 1):
                comp = servico_metas.rotulo(servico_metas.somar_meses(servico_metas.competencia_de(json["competencia"]), k))
                gravadas.append(self.criar(json["seguradora"], json["ramo"], json["valor_meta"], comp, json.get("usuario")))
            return {"metas": gravadas}
        meta_id = int(caminho.rsplit("/", 1)[1])
        if metodo == "PUT":
            if meta_id not in self.metas:
                raise fedhub_lake.RecusaDoFedHub(404, {"erro": "meta_inexistente", "detalhe": "meta não encontrada."})
            chave = (json["seguradora"], json["ramo"], json["competencia"])
            for m in self.metas.values():
                if m["id"] != meta_id and (m["seguradora"], m["ramo"], m["competencia"]) == chave:
                    raise fedhub_lake.RecusaDoFedHub(409, {"erro": "meta_duplicada", "detalhe": "já existe meta para essa chave."})
            m = self.metas[meta_id]
            m.update(seguradora=json["seguradora"], ramo=json["ramo"], competencia=json["competencia"],
                     valor_meta=json["valor_meta"], usuario=json.get("usuario"))
            return {"metas": [self._linha(m)]}
        if metodo == "DELETE":
            if meta_id not in self.metas:
                raise fedhub_lake.RecusaDoFedHub(404, {"erro": "meta_inexistente", "detalhe": "meta não encontrada."})
            del self.metas[meta_id]
            return None
        raise AssertionError(metodo)
