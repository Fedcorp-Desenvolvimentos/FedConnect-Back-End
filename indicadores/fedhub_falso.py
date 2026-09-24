"""FedHub de mentira para a suíte do app `indicadores` (RF-IEX-010).

Desde 23/09/2026 as metas moram no lake e chegam pelo FedHub (`/api/lake/metas`).
Nenhum teste pode depender do FedHub real: este módulo implementa as quatro
rotas em memória, com a mesma semântica (upsert pela chave, réplica de meses,
409 em chave ocupada, 404 em id inexistente, `fora` para simular lake caído).
`_ComCarga` (tests.py) o liga em todo `setUp`.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from indicadores.services import fedhub_lake
from indicadores.services import metas as servico_metas

NOMES_SEG = {"ALLI": "ALLIANZ", "PORT": "PORTO", "TOKI": "TOKIO"}
NOMES_RAMO = {"COND": "CONDOMINIO", "FIAN": "FIANCA", "AUTO": "AUTOMOVEL"}


class FedHubFalso:
    """`/api/lake/metas` em memória, com a semântica do FedHub real."""

    def __init__(self):
        self.metas = {}
        self.proximo = 1
        self.fora = False        # lake inteiro fora: toda rota falha
        self.metas_fora = False  # so as rotas de metas falham (indicadores respondem)

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
        if caminho.startswith("indicadores/"):
            return self._indicadores(caminho.split("/", 1)[1], params or {})
        if self.metas_fora:
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

    # ------------------------------------------------------------------ indicadores
    # As funcoes fn_ind_* do lake, com a MESMA regra (inicio de vigencia, premio
    # liquido, renovacao da casa), calculadas sobre o espelho carregado no banco
    # de teste. Assim a suite continua provando o contrato do FedConnect com o
    # front, e o numero esperado e o que o lake devolveria para a mesma amostra.

    _BLOCO = {
        "fechados": Count("nosnum"),
        "renovacoes": Count("nosnum", filter=Q(renovacao=True)),
        "captacoes": Count("nosnum", filter=Q(renovacao=False)),
        "com_negocio_origem": Count("documentonegocio"),
        "valor_fechado": Sum("documento__preliq"),
        "documentos_com_valor": Count("documento__preliq"),
        "premio_total": Sum("documento__pretot"),
        "comissao": Sum("documento__val_c"),
        "documentos_com_comissao": Count("documento__val_c"),
    }

    @staticmethod
    def _lista(p, chave):
        v = p.get(chave) or []
        return list(v) if isinstance(v, (list, tuple)) else [v]

    @staticmethod
    def _bool(p, chave):
        v = p.get(chave, False)
        return v is True or str(v).lower() == "true"

    @staticmethod
    def _data(v):
        return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])

    def _universo(self, p, ramos=None, seguradoras=None):
        from indicadores.models import Producao
        qs = Producao.objects.all()
        if not self._bool(p, "todos_tipdoc"):
            qs = qs.filter(tipdoc="A")
        if not self._bool(p, "incluir_cancelados"):
            qs = qs.filter(cancelado=False)
        ramos = self._lista(p, "ramo") if ramos is None else ramos
        seguradoras = self._lista(p, "seguradora") if seguradoras is None else seguradoras
        if ramos:
            qs = qs.filter(ramo_id__in=ramos)
        if seguradoras:
            qs = qs.filter(seguradora_id__in=seguradoras)
        return qs

    @staticmethod
    def _serializar(d):
        return {k: (str(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, date) else v) for k, v in d.items()}

    def _indicadores(self, rota, p):
        from indicadores.models import CargaCorp, Producao, Ramo, Seguradora
        if rota == "totais":
            carga = CargaCorp.objects.filter(sucesso=True).order_by("-concluida_em", "-id").first()
            return {"totais": {
                "total_documentos": Producao.objects.count(),
                "documentos_sem_datemi": Producao.objects.filter(datemi__isnull=True).count(),
                "documentos_sem_inivig": Producao.objects.filter(inivig__isnull=True).count(),
                "extraido_em": (carga.extraido_em.isoformat() + "T03:00:00+00:00") if carga and carga.extraido_em else None,
                "ausentes_na_origem": 0,
            }}
        if rota == "nao-fechadas":
            return {"linhas": self._nao_fechadas(p)}
        ini, fim = self._data(p["ini"]), self._data(p["fim"])
        if rota == "bloco":
            return {"bloco": self._serializar(self._universo(p).filter(inivig__range=(ini, fim)).aggregate(**self._BLOCO))}
        if rota == "por-seguradora":
            nomes = dict(Seguradora.objects.values_list("sigla", "nome"))
            linhas = self._universo(p).filter(inivig__range=(ini, fim)).values("seguradora").annotate(**self._BLOCO).order_by("-fechados", "seguradora")
            return {"linhas": [self._serializar({"seguradora_sigla": l["seguradora"], "seguradora": nomes.get(l["seguradora"], ""),
                                                 **{k: l[k] for k in self._BLOCO}}) for l in linhas]}
        if rota == "serie":
            qs = self._universo(p).filter(inivig__range=(ini, fim))
            if p.get("grao") == "mes":
                linhas = qs.annotate(mes=TruncMonth("inivig")).values("mes").annotate(**self._BLOCO).order_by("mes")
                return {"linhas": [self._serializar({"periodo": l["mes"], **{k: l[k] for k in self._BLOCO}}) for l in linhas]}
            linhas = qs.values("inivig").annotate(**self._BLOCO).order_by("inivig")
            return {"linhas": [self._serializar({"periodo": l["inivig"], **{k: l[k] for k in self._BLOCO}}) for l in linhas]}
        if rota == "dominios":
            linhas = []
            for r in Ramo.objects.all():
                linhas.append({"dominio": "ramo", "sigla": r.abreviatura, "nome": r.nome,
                               "total_base": Producao.objects.filter(ramo_id=r.abreviatura).count(),
                               "fechados_periodo": self._universo(p, ramos=[]).filter(inivig__range=(ini, fim), ramo_id=r.abreviatura).count()})
            for sg in Seguradora.objects.all():
                linhas.append({"dominio": "seguradora", "sigla": sg.sigla, "nome": sg.nome,
                               "total_base": Producao.objects.filter(seguradora_id=sg.sigla).count(),
                               "fechados_periodo": self._universo(p, seguradoras=[]).filter(inivig__range=(ini, fim), seguradora_id=sg.sigla).count()})
            return {"linhas": linhas}
        if rota == "composicao":
            nomes = dict(Seguradora.objects.values_list("sigla", "nome"))
            qs = self._universo(p).filter(inivig__range=(ini, fim)).order_by("-inivig", "cliente_nome", "nosnum")
            return {"linhas": [{"lista": "renovacoes" if d.renovacao else "captacoes", "nosnum": d.nosnum, "cliente": d.cliente_nome,
                                "seguradora_sigla": d.seguradora_id, "seguradora": nomes.get(d.seguradora_id, ""),
                                "ramo_sigla": d.ramo_id, "data": d.inivig.isoformat() if d.inivig else None} for d in qs]}
        raise AssertionError("rota de indicadores nao prevista: " + rota)

    def _nao_fechadas(self, p):
        from indicadores.models import Producao, Seguradora
        ref = self._data(p["ref"])
        janela = timedelta(days=int(p.get("janela_dias", 30)))
        nomes = dict(Seguradora.objects.values_list("sigla", "nome"))
        mes_ini = ref.replace(day=1)
        mes_fim = (mes_ini.replace(year=mes_ini.year + (mes_ini.month == 12), month=mes_ini.month % 12 + 1)) - timedelta(days=1)
        vencem = list(self._universo(p).filter(fimvig__range=(mes_ini, mes_fim)).select_related("cliente").order_by("fimvig", "nosnum"))
        linhas = []
        for v in vencem:
            novas = {}
            for n in Producao.objects.filter(nosnum_ren=v.nosnum).order_by("inivig", "nosnum"):
                novas[n.nosnum] = n
            cpf = v.cliente.cpf_cnpj if v.cliente_id else ""
            if cpf and v.fimvig:
                for n in Producao.objects.filter(tipdoc="A", cancelado=False, inivig__isnull=False, cliente__cpf_cnpj=cpf).exclude(nosnum=v.nosnum):
                    if v.fimvig - janela <= n.inivig <= v.fimvig + janela:
                        novas.setdefault(n.nosnum, n)
            ordenadas = sorted(novas.values(), key=lambda n: (n.inivig or v.fimvig, n.nosnum))
            linhas.append({
                "nosnum": v.nosnum, "fimvig": v.fimvig.isoformat() if v.fimvig else None,
                "datemi": v.datemi.isoformat() if v.datemi else None, "inivig": v.inivig.isoformat() if v.inivig else None,
                "cliente": v.cliente_nome or (v.cliente.nome if v.cliente_id else ""),
                "cpf_cnpj": cpf or None, "pessoa": v.cliente.pessoa if v.cliente_id else "",
                "seguradora_sigla": v.seguradora_id, "seguradora": nomes.get(v.seguradora_id, ""), "ramo_sigla": v.ramo_id,
                "renovacao_situacao": v.renovacao_situacao, "sin_situacao": v.sin_situacao,
                "vencida": bool(v.fimvig and v.fimvig <= ref), "decidida": v.renovacao_situacao in (2, 3),
                "fechada": bool(ordenadas),
                "novas": [{"nosnum": n.nosnum, "seguradora": n.seguradora_id, "seguradora_nome": nomes.get(n.seguradora_id, "")} for n in ordenadas],
            })
        return linhas
