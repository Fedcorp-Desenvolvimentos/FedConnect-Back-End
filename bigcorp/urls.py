from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from fedhub.views.administradoras_view import (
    buscarAdms,
    BuscarAdministradoras,
    BuscarAdministradorasPorNome,
    BuscarAdministradorasPorCodigo
)
from fedhub.views.analytics_view import (
    AnalyticsFaturamentoPeriodoView,
    AnalyticsTopAdministradorasView,
    AnalyticsInadimplenciaView,
    AnalyticsFaturamentoPorAdministradoraView,
    AnalyticsStatusFaturasView,
    AnalyticsDashboardCompletoView
)
from fedhub.views.automacao_view import (
    AutomacaoSepararPDFView,
    AutomacaoUploadPDFsBBZView,
    AutomacaoProcessarPDFsBBZView
)
from fedhub.views.bancos_view import BuscarBancoPorCodigoView, BuscarBancoPorNomeView, BuscarBancosView
from fedhub.views.cedente_view import BuscarCedentePorNomeView, BuscarCedentesView
from fedhub.views.comissao_view import (
    BuscarComissoesPorFaturaView, 
    BuscarFaturasComissoesView, 
    BuscarComissaoPorDataCorteView, 
    BuscarComissaoPorDataCorteV2View,
    BuscarProdutosPorFavorecidoView, 
    EmitirReciboComissaoView, 
    EmitirVoucherComissaoView, 
    ConsultarComissaoView, 
    CancelarComissaoView
)
from fedhub.views.corretores_view import BuscarCorretores
from fedhub.views.faturamento_view import (
    BuscarFaturamento,
    TratamentoDeErroView,
    EmissaoSegundaViaBoletoView,
    DadosSegundaViaBoletoView,
    ConverterBoletoCSVView
)
   
from fedhub.views.empresas_view import BuscarTodasEmpresas

from fedhub.views.faturas_view import BuscarFaturaPorNumero, ExportarFaturasComBoletosExcel, ExportarFaturasComBoletosPDF
from fedhub.views.fedbnk_view import CancelarBoletoFedBnkView, SincronizarBoletosView
from fedhub.views.fedpay_view import ConsultarFedPayView, TratamentoFedPayView
from fedhub.views.envio_porto_view import (
    GerarAssistenciaView, ListarJobsView, JobView, DownloadJobView, EnviarSftpView,
    VidaSubgruposView, VidaGerarView, VidaInconsistenciasView, DentalView,
)
from fedhub.views.pessoas_view import (
    BuscarPessoasView,
    CriarPessoaView,
    BuscarGerentesComerciaisView,
    PessoaDetailView
)

from fedhub.views.produtos_view import BuscarProdutosView, BuscarNFSEPorBoleto

from rest_framework_simplejwt.views import TokenRefreshView
from users.views import (
    GoogleLoginView,
    ResetarSenhaView, 
    SolicitarResetSenhaView, 
    UsuarioViewSet, 
    LogoutView, 
    CustomTokenObtainPairView, 
    PasswordView, 
    ValidarTokenResetView
)
from consultas.views import (
    BuscarCidadesAutocomplete,
    BuscarLocalidade, 
    RealizarConsultaView, 
    HistoricoConsultaListView, 
    HistoricoConsultaDetailView, 
    HistoricoConsultaUserListView,
)
from planilha.views.cnpj_views import (baixar_planilha_modelo_drf_cnpj, ProcessarPlanilhaCnpjsView)
from planilha.views.cep_views import (baixar_planilha_modelo_drf_cep,ProcessarPlanilhaCepsView)
from planilha.views.cpf_views import (baixar_planilha_modelo_drf_cpf, ProcessarPlanilhaCpfsView)

from empresas.views import EmpresaViewSet

# Vistorias
from fedhub.views.vistorias_view import (
    ListarEstadosVistoria,
    ListarVistoriadores,
    ListarAdministradorasVistoria,
    ConsultarVistorias,
    ExportarVistoriasExcel,
    ExportarVistoriasPDF
)
from agenda.views import ReservaViewSet
from condomed.views import TurmaCipaViewSet

from cotacao.views import calcular_cotacao_incendio
from questionarios.views import QuestionarioProcessoViewSet

# Importe para a documentação
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from consultas.comercial import ConsultaComercialAPIView, ConsultaContatoComercialAPIView, BulkConsultaComercialAPIView, ComercialRegiaoAPIView
from consultas.segurados import RealizarConsultaSeguradosView
from consultas.faturas import RealizarConsultaFaturasView
from agenda_comercial.views import AgendamentoListCreateAPIView, AgendamentoRetrieveUpdateDestroyAPIView
from django.urls import path
from consultas.boletofedbnk import cancelar_boleto, consultar_boletos_proxy, consultar_boleto

router = DefaultRouter()
router.register(r"users", UsuarioViewSet, basename="users")
router.register(r'empresas', EmpresaViewSet)
router.register(r'agenda', ReservaViewSet)
router.register(r'questionarios', QuestionarioProcessoViewSet)
router.register(r'cursos-cipa', TurmaCipaViewSet, basename='cursos-cipa')

urlpatterns = [
    path("admin/", admin.site.urls),
    # URLs da Documentação (Swagger/OpenAPI)
    
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI: Swagger UI (interativa)
    
    path("schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    
    # Optional UI: ReDoc UI (mais focada em leitura)
    path(
        "schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
    ),
    
    # ROTA DE AUTENTICAÇÃO / LOGIN / LOGOUT
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    
    path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("users/me/", UsuarioViewSet.as_view({"get": "me"}), name="usuario-me"),
    path("users/password/", PasswordView.as_view(), name="usuario-password"),
    
    # ROTAS DAS PLANILHAS 
    
    ## CNPJ
    path('planilha-modelo-cnpj/', baixar_planilha_modelo_drf_cnpj, name='baixar-modelo-cnpj'),
    path('processar-cnpj-planilha/', ProcessarPlanilhaCnpjsView.as_view(), name='processar-cnpj-planilha'),

    ## CEP
    path('planilha-modelo-cep/', baixar_planilha_modelo_drf_cep, name='baixar-modelo-cep'),
    path('processar-cep-planilha/', ProcessarPlanilhaCepsView.as_view(), name='processar-cep-planilha'),

    ## CPF
    path('planilha-modelo-cpf/', baixar_planilha_modelo_drf_cpf, name='baixar-modelo-cpf'),
    path('processar-cpf-planilha/', ProcessarPlanilhaCpfsView.as_view(), name='processar-cpf-planilha'),

    # ROTAS DE ADMINISTRADORAS *******
    path('administradoras/', buscarAdms.as_view(), name='buscar_adms'),
    
    # ROTAS DE EMPRESAS *******
    path("empresas/", BuscarTodasEmpresas.as_view(), name="consultar-todas-empresas"),

    # ROTA DE CONSULTAS *******
    path('consultas/realizar/', RealizarConsultaView.as_view(), name='realizar-consulta'),
    
    # HISTÓRICO DE CONSULTAS *******
    path('consultas/historico/', HistoricoConsultaListView.as_view(), name='historico-consultas'),
    path('consultas/historico/<int:pk>/', HistoricoConsultaDetailView.as_view(), name='historico-consulta-detail'),
    path('consultas/historico/usuario/<int:user_id>/', HistoricoConsultaUserListView.as_view(), name='historico-consultas-por-usuario'),
    
    # ROTAS DE COMERCIAL
    path('consultas/comercial/', ConsultaComercialAPIView.as_view(), name='consulta-comercial'), 
    path('consultas/cont-comercial/', ConsultaContatoComercialAPIView.as_view(), name='consulta-contato-comercial'), 

    # ROTAS DE SEGURADOS
    path('consultas/segurados/', RealizarConsultaSeguradosView.as_view(), name='realizar_consulta_segurados'),
    
    # ROTAS DE FATURAS *******
    path('consultas/faturas/', RealizarConsultaFaturasView.as_view(), name='realizar-consulta-faturas'),
    path('consultas/faturas/com-boletos/exportar-excel/', ExportarFaturasComBoletosExcel.as_view(), name='exportar-faturas-excel'),
    path("consultas/faturas/com-boletos/exportar-pdf/", ExportarFaturasComBoletosPDF.as_view(), name='exportar-faturas-pdf'),
    path('consultas/faturas/<str:numero_fatura>/', BuscarFaturaPorNumero.as_view(), name='consulta-fatura-por-numero'),

    # ROTAS DE FATURAMENTO *******
    path('consultas/faturamento/', BuscarFaturamento.as_view(), name='buscar-faturamento'),

    # ROTAS DE ADMINISTRADORAS / CORRETORES / NFSE / LOCALIDADE *******
    path('consultas/administradoras/', BuscarAdministradoras.as_view(), name='consulta-administradoras'),
    path('consultas/administradora/por-nome/<str:nome>/', BuscarAdministradorasPorNome.as_view(), name='consulta-administradora-por-nome'),
    path('consultas/administradora/por-codigo/<str:codigo>/', BuscarAdministradorasPorCodigo.as_view(), name='consulta-administradora-por-codigo'),
    
    # ROTAS DE CORRETORES *******
    path('consultas/corretores/<str:codigo>/', BuscarCorretores.as_view(), name='consulta-corretor-por-codigo'),
    
    # ROTAS DE NFSE *******
    path('consultas/nfse/<str:documento>/', BuscarNFSEPorBoleto.as_view(), name='consulta-nfse-por-documento'),
    
    # ROTAS DE LOCALIDADE *******
    path('consultas/localidade/', BuscarLocalidade.as_view(), name='buscar-localidade'),
    
    # ROTAS DE PESSOAS POR FAVORECIDO *******
    path('consulta-massa-comercial/', BulkConsultaComercialAPIView.as_view(), name='consulta-massa-comercial'),
    path('consulta/comercial-regiao/', ComercialRegiaoAPIView.as_view(), name='consulta-comercial-regiao'),
    
    # ROTAS DE BOLETOS FEDBNK ******* ?????
    path('consultar-boletosfedbnk/', consultar_boletos_proxy, name='consultar_boletos_proxy'),
    path('consultar-boletofedbnk/', consultar_boleto, name='consultar_boleto_proxy'),
    
    # CIDADES / ROTAS DE AUTOCOMPLETE *******
    path('cidades/autocomplete/', BuscarCidadesAutocomplete.as_view(), name='cidades-autocomplete'),
    
    # AGENDA COMERCIAL *******
    path('comercial/agenda/', AgendamentoListCreateAPIView.as_view(), name='agendamento_list'),
    path('comercial/agenda/<int:pk>/', AgendamentoRetrieveUpdateDestroyAPIView.as_view(), name='agendamento_detail'),
    
    # COTAÇÃO DE INCÊNDIO E CONTEÚDO *******
    path('cotacao/incendio-conteudo/', calcular_cotacao_incendio, name='calcular_cotacao_incendio'),
    
    # BOLETO FEDBNK - CANCELAMENTO ******* ?????
    path('cancelar-boletofedbnk/', cancelar_boleto, name='cancelar_boleto_proxy'), 
    
    # AUTOMAÇÃO DE PDFS *******
    path('automacao/separar-pdf/', AutomacaoSepararPDFView.as_view(), name='automacao-separar-pdf'),
    path('automacao/upload-pdfs-bbz/', AutomacaoUploadPDFsBBZView.as_view(), name='automacao-upload-pdfs-bbz'),
    path('automacao/processar-pdfs-bbz/', AutomacaoProcessarPDFsBBZView.as_view(), name='automacao-processar-pdfs-bbz'),
        
    # RECUPERAÇÃO DE SENHA *******
    path("solicitar-reset-senha/", SolicitarResetSenhaView.as_view(), name="solicitar-reset-senha"),
    path("validar-token-reset/<str:token>/", ValidarTokenResetView.as_view(), name="validar-token-reset"),
    path("resetar-senha/", ResetarSenhaView.as_view(), name="resetar-senha"),
    
    # BOLETO FEDBNK *******
    path('boletofedbnk/cancelar/', CancelarBoletoFedBnkView.as_view(), name='cancelar-boleto-fedbnk'),
    path('boletofedbnk/sincronizar/', SincronizarBoletosView.as_view(), name='sincronizar-boletos'),
    
    # ESTATÍSTICAS / ANALYTICS *******
    path('analytics/faturamento/', AnalyticsFaturamentoPeriodoView.as_view(), name='analytics-faturamento-periodo'),
    path('analytics/administradoras/top/', AnalyticsTopAdministradorasView.as_view(), name='analytics-top-administradoras'),
    path('analytics/inadimplencia/', AnalyticsInadimplenciaView.as_view(), name='analytics-inadimplencia'),
    path('analytics/administradoras/faturamento/', AnalyticsFaturamentoPorAdministradoraView.as_view(), name='analytics-faturamento-administradora'),
    path('analytics/faturas/status/', AnalyticsStatusFaturasView.as_view(), name='analytics-status-faturas'),
    path('analytics/dashboard/', AnalyticsDashboardCompletoView.as_view(), name='analytics-dashboard-completo'),
    
    # FATURAMENTO / BOLETOS *******
    path('faturamento/tratamento-de-erros/rodar-procedure/', TratamentoDeErroView.as_view(), name='faturamento-tratamento-de-erro'),
    path('faturamento/formato-arquivos/converter-boleto-csv/', ConverterBoletoCSVView.as_view(), name='faturamento-converter-boleto-csv'),
    path('faturamento/dados-segunda-via-boleto/<str:fatura>/', DadosSegundaViaBoletoView.as_view(), name='faturamento-dados-segunda-via-boleto'),
    path('faturamento/emissao-segunda-via-boleto/<str:fatura>/', EmissaoSegundaViaBoletoView.as_view(), name='faturamento-emissao-segunda-via-boleto'),
    path('fedpay/consulta/<str:fatura>/', ConsultarFedPayView.as_view(), name='fedpay-consulta'),
    path('fedpay/tratamento/', TratamentoFedPayView.as_view(), name='fedpay-tratamento'),

    # ENVIO PORTO (proxy da API /api/envio-porto/* do FedHub) *******
    path('envio-porto/assistencia/gerar/', GerarAssistenciaView.as_view(), name='envio-porto-assistencia-gerar'),
    path('envio-porto/jobs/', ListarJobsView.as_view(), name='envio-porto-jobs'),
    path('envio-porto/jobs/<str:job_id>/', JobView.as_view(), name='envio-porto-job'),
    path('envio-porto/jobs/<str:job_id>/download/', DownloadJobView.as_view(), name='envio-porto-job-download'),
    path('envio-porto/jobs/<str:job_id>/enviar-sftp/', EnviarSftpView.as_view(), name='envio-porto-job-enviar-sftp'),
    path('envio-porto/vida/subgrupos/', VidaSubgruposView.as_view(), name='envio-porto-vida-subgrupos'),
    path('envio-porto/vida/gerar/', VidaGerarView.as_view(), name='envio-porto-vida-gerar'),
    path('envio-porto/vida/inconsistencias/', VidaInconsistenciasView.as_view(), name='envio-porto-vida-inconsistencias'),
    path('envio-porto/dental/<path:rota>/', DentalView.as_view(), name='envio-porto-dental'),
    
    # COMISSÕES / RECIBOS / VOUCHERS *******
    path('comissoes/faturas/', BuscarFaturasComissoesView.as_view(), name='buscar-faturas-comissoes'),
    path('comissoes/faturas/<str:numero_fatura>/comissoes/', BuscarComissoesPorFaturaView.as_view(), name='buscar-comissoes-por-fatura'),    
    path('comissoes/por-data/<str:data_corte>/', BuscarComissaoPorDataCorteView.as_view(), name='buscar-comissao-por-data'),
    path('comissoes/por-data-v2/<str:data_corte>/', BuscarComissaoPorDataCorteV2View.as_view(), name='buscar-comissao-por-data-v2'),
    path('comissoes/emitir-recibo/', EmitirReciboComissaoView.as_view(), name='emitir-recibo-comissao'),
    path('comissoes/emitir-voucher/', EmitirVoucherComissaoView.as_view(), name='emitir-voucher-comissao'),
    path('comissoes/consultar/', ConsultarComissaoView.as_view(), name='consultar-comissoes'),
    path('comissoes/produtos-por-favorecido/', BuscarProdutosPorFavorecidoView.as_view(), name='produtos-por-favorecido'),
    path('comissoes/cancelar/', CancelarComissaoView.as_view(), name='cancelar-comissoes'),
    
    # PESSOAS (FAVORECIDOS) *******
    path('pessoas/', BuscarPessoasView.as_view(), name='buscar-pessoas'),
    path('pessoas/criar/', CriarPessoaView.as_view(), name='criar-pessoa'),
    path('pessoas/gerentes-comerciais/', BuscarGerentesComerciaisView.as_view(), name='buscar-gerentes-comerciais'),    
    path('pessoas/<str:codigo>/', PessoaDetailView.as_view(), name='pessoa-detail'),
    
    # BANCOS *******
    path('bancos/', BuscarBancosView.as_view(), name='buscar-bancos'),
    path('bancos/<str:codigo>/', BuscarBancoPorCodigoView.as_view(), name='buscar-banco-por-codigo'),
    path('bancos/nome/<str:nome>/', BuscarBancoPorNomeView.as_view(), name='buscar-banco-por-nome'),
    
    # PRODUTOS *******
    path('produtos/', BuscarProdutosView.as_view(), name='buscar-produtos'),
    
    # CEDENTES *******
    path('cedentes/', BuscarCedentesView.as_view(), name='buscar-cedentes'),
    path('cedentes/buscar/', BuscarCedentePorNomeView.as_view(), name='buscar-cedente-por-nome'),
    
    # VISTORIAS *******
    path('vistorias/estados/', ListarEstadosVistoria.as_view(), name='listar-estados-vistoria'),
    path('vistorias/vistoriadores/', ListarVistoriadores.as_view(), name='listar-vistoriadores'),
    path('vistorias/administradoras/', ListarAdministradorasVistoria.as_view(), name='listar-administradoras-vistoria'),
    path('vistorias/', ConsultarVistorias.as_view(), name='consultar-vistorias'),
    path('vistorias/exportar/excel/', ExportarVistoriasExcel.as_view(), name='exportar-vistorias-excel'),
    path('vistorias/exportar/pdf/', ExportarVistoriasPDF.as_view(), name='exportar-vistorias-pdf'),
    
    path("", include(router.urls)),
]
