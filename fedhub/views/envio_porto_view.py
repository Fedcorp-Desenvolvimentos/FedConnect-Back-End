# fedhub/views/envio_porto_view.py
#
# Tela Envio Porto (spec FedConnect-FrontEnd/specs/envio-porto; contrato:
# FedHub-Backend/specs/envio-porto v2). Proxy fino: autenticação JWT +
# gate por nível aqui; toda a lógica (geração, jobs, SFTP) é do FedHub.
#
# O `operador` enviado ao FedHub é SEMPRE request.user.email — nunca vem do
# payload. Enviar à Porto exige a confirmação digitada na tela ("ENVIAR")
# chegar aqui como {"confirmacao": "ENVIAR"}; só então o FedHub recebe
# {"confirmar": true}.

import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.envio_porto_service import EnvioPortoService

logger = logging.getLogger(__name__)

# PA-023 (FedHub, fechada 2026-08-27): operadores são "faturista" (nivel_acesso
# "faturamento"), o Alberto é admin; "ti" = equipe técnica. Sem distinção entre
# gerar e enviar — a confirmação digitada continua obrigatória para todos.
NIVEIS_TELA = ("admin", "faturamento", "ti")   # gerar, acompanhar, baixar
NIVEIS_ENVIO = ("admin", "faturamento", "ti")  # enviar à Porto (ato irreversível)

TEXTO_CONFIRMACAO = "ENVIAR"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _sem_acesso(acao="usar o Envio Porto"):
    return Response({"sucesso": False, "erro": f"Seu nível de acesso não permite {acao}."}, status=status.HTTP_403_FORBIDDEN)


def _repassar(resultado: dict, ok=(200, 201, 202)) -> Response:
    """Resposta do FedHub → {sucesso, resultado|erro} com o mesmo HTTP status."""
    body = resultado.get("body") or {}
    if resultado["http_status"] in ok:
        return Response({"sucesso": True, "resultado": body}, status=resultado["http_status"])
    erro = body.get("message") or body.get("resumo") or "Erro na comunicação com o FedHub"
    return Response({"sucesso": False, "erro": erro, "resultado": body}, status=resultado["http_status"])


class _EnvioPortoBase(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _autorizado(self, request, niveis=NIVEIS_TELA) -> bool:
        return getattr(request.user, "nivel_acesso", None) in niveis

    @property
    def service(self) -> EnvioPortoService:
        return EnvioPortoService()


class GerarAssistenciaView(_EnvioPortoBase):
    """POST envio-porto/assistencia/gerar/  {inivig, produtos} → 202 {job_id}."""

    def post(self, request, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        inivig = request.data.get("inivig")
        produtos = request.data.get("produtos")
        if not inivig or not isinstance(produtos, dict) or not produtos:
            return Response({"sucesso": False, "erro": "Informe a data de início de vigência e ao menos um produto."}, status=status.HTTP_400_BAD_REQUEST)
        logger.info(f"EnvioPorto: geração Assistência inivig={inivig} produtos={produtos} operador={request.user.email}")
        return _repassar(self.service.gerar_assistencia(str(inivig), produtos, request.user.email))


class ListarJobsView(_EnvioPortoBase):
    """GET envio-porto/jobs/?tipo=&limite= → histórico recente."""

    def get(self, request, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        try:
            limite = max(1, min(int(request.query_params.get("limite", 20)), 100))
        except ValueError:
            limite = 20
        return _repassar(self.service.listar_jobs(request.query_params.get("tipo") or None, limite))


class JobView(_EnvioPortoBase):
    """GET envio-porto/jobs/<job_id>/ → status + log."""

    def get(self, request, job_id, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        return _repassar(self.service.job(job_id))


class DownloadJobView(_EnvioPortoBase):
    """GET envio-porto/jobs/<job_id>/download/ → .xlsx (attachment)."""

    def get(self, request, job_id, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        resultado = self.service.download(job_id)
        if resultado["http_status"] != 200:
            return _repassar(resultado)
        response = HttpResponse(resultado["conteudo"], content_type=XLSX)
        response["Content-Disposition"] = f'attachment; filename="{resultado["nome"]}"'
        response["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response


class EnviarSftpView(_EnvioPortoBase):
    """POST envio-porto/jobs/<job_id>/enviar-sftp/  {confirmacao: "ENVIAR", reenviar?: bool}.

    Tudo que cai em /Porto/Remessa pode ser processado pela seguradora: a
    confirmação digitada é verificada AQUI e só então o FedHub recebe
    confirmar=true. Sem o texto exato, nada sai desta view.
    """

    def post(self, request, job_id, *args, **kwargs):
        if not self._autorizado(request, NIVEIS_ENVIO):
            return _sem_acesso("enviar arquivos à Porto Seguro")
        confirmacao = str(request.data.get("confirmacao") or "").strip().upper()
        if confirmacao != TEXTO_CONFIRMACAO:
            return Response(
                {"sucesso": False, "erro": f'Confirmação inválida — digite {TEXTO_CONFIRMACAO} para enviar à Porto.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reenviar = bool(request.data.get("reenviar"))
        logger.warning(f"EnvioPorto: ENVIO SFTP do job {job_id} solicitado por {request.user.email} (reenviar={reenviar})")
        return _repassar(self.service.enviar_sftp(job_id, request.user.email, reenviar=reenviar))


class VidaSubgruposView(_EnvioPortoBase):
    def get(self, request, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        return _repassar(self.service.vida_subgrupos())


class VidaGerarView(_EnvioPortoBase):
    """POST envio-porto/vida/gerar/  {vigencia, subgrupos: [nomes]} → 202 {job_id}."""

    def post(self, request, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        vigencia = request.data.get("vigencia")
        subgrupos = request.data.get("subgrupos")
        if not vigencia or not isinstance(subgrupos, list) or not subgrupos:
            return Response({"sucesso": False, "erro": "Informe a vigência e ao menos um subgrupo."}, status=status.HTTP_400_BAD_REQUEST)
        logger.info(f"EnvioPorto: geração Vida vigencia={vigencia} subgrupos={len(subgrupos)} operador={request.user.email}")
        return _repassar(self.service.vida_gerar(str(vigencia), [str(s) for s in subgrupos], request.user.email))


class VidaInconsistenciasView(_EnvioPortoBase):
    def get(self, request, *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        vigencia = request.query_params.get("vigencia")
        if not vigencia:
            return Response({"sucesso": False, "erro": "Informe a vigência."}, status=status.HTTP_400_BAD_REQUEST)
        return _repassar(self.service.vida_inconsistencias(str(vigencia)))


class DentalView(_EnvioPortoBase):
    """Placeholders: o FedHub responde 501 'em desenvolvimento'."""

    def get(self, request, rota="", *args, **kwargs):
        if not self._autorizado(request):
            return _sem_acesso()
        return _repassar(self.service.dental(rota))
