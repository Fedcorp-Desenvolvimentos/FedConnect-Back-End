from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
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
    AnalyticsDashboardCompletoView,
    AnalyticsFaturamentoPeriodoView,
    AnalyticsFaturamentoPorAdministradoraView,
    AnalyticsInadimplenciaView,
    AnalyticsStatusFaturasView,
    AnalyticsTopAdministradorasView,
    AutomacaoProcessarPDFsBBZView,
    AutomacaoSepararPDFView,
    AutomacaoUploadPDFsBBZView,
    BuscarAdministradoras,
    BuscarAdministradorasPorCodigo, 
    BuscarAdministradorasPorNome,
    BuscarCidadesAutocomplete, 
    BuscarCorretores, 
    BuscarFaturaPorNumero, 
    BuscarFaturamento,
    BuscarLocalidade, 
    BuscarNFSEPorBoleto, 
    BuscarTodasEmpresas,
    CancelarBoletoFedBnkView,
    ConverterBoletoCSVView, 
    ExportarFaturasComBoletosExcel, 
    ExportarFaturasComBoletosPDF, 
    RealizarConsultaView, 
    HistoricoConsultaListView, 
    HistoricoConsultaDetailView, 
    HistoricoConsultaUserListView,
    TratamentoDeErroView
)
from planilha.views.cnpj_views import (baixar_planilha_modelo_drf_cnpj, ProcessarPlanilhaCnpjsView)
from planilha.views.cep_views import (baixar_planilha_modelo_drf_cep,ProcessarPlanilhaCepsView)
from planilha.views.cpf_views import (baixar_planilha_modelo_drf_cpf, ProcessarPlanilhaCpfsView)
from empresas.views import EmpresaViewSet
from consultas.comercial import ConsultaComercialAPIView, ConsultaContatoComercialAPIView, BulkConsultaComercialAPIView, ComercialRegiaoAPIView
from consultas.segurados import RealizarConsultaSeguradosView, buscarAdms
from consultas.faturas import RealizarConsultaFaturasView
from agenda.views import ReservaViewSet
from agenda_comercial.views import AgendamentoListCreateAPIView, AgendamentoRetrieveUpdateDestroyAPIView
from django.urls import path
from cotacao.views import calcular_cotacao_incendio
from consultas.boletofedbnk import cancelar_boleto, consultar_boletos_proxy, consultar_boleto
from bank.views import SantanderWebhookView

# Importe para a documentação
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


router = DefaultRouter()
router.register(r"users", UsuarioViewSet, basename="users")
router.register(r'empresas', EmpresaViewSet)
router.register(r'agenda', ReservaViewSet)

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
    
    # Rotas de Autenticação
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    #path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
    
    path("logout/", LogoutView.as_view(), name="logout"),
    # Rota para o endpoint "me" do usuário
    
    path("users/me/", UsuarioViewSet.as_view({"get": "me"}), name="usuario-me"),
    path("users/password/", PasswordView.as_view(), name="usuario-password"),
    
    path("empresas/", BuscarTodasEmpresas.as_view(), name="consultar-todas-empresas"),
    
    # Rotas de Consultas#
    path('consultas/realizar/', RealizarConsultaView.as_view(), name='realizar-consulta'),
    path('consultas/historico/', HistoricoConsultaListView.as_view(), name='historico-consultas'),
    path('consultas/historico/<int:pk>/', HistoricoConsultaDetailView.as_view(), name='historico-consulta-detail'),
    path('consultas/historico/usuario/<int:user_id>/', HistoricoConsultaUserListView.as_view(), name='historico-consultas-por-usuario'),
 
    # Rotas das planilhas #
    #CNPJ
    path('planilha-modelo-cnpj/', baixar_planilha_modelo_drf_cnpj, name='baixar-modelo-cnpj'),
    path('processar-cnpj-planilha/', ProcessarPlanilhaCnpjsView.as_view(), name='processar-cnpj-planilha'),

    # CEP
    path('planilha-modelo-cep/', baixar_planilha_modelo_drf_cep, name='baixar-modelo-cep'),
    path('processar-cep-planilha/', ProcessarPlanilhaCepsView.as_view(), name='processar-cep-planilha'),

    # CPF 
    path('planilha-modelo-cpf/', baixar_planilha_modelo_drf_cpf, name='baixar-modelo-cpf'),
    path('processar-cpf-planilha/', ProcessarPlanilhaCpfsView.as_view(), name='processar-cpf-planilha'),

    # Comercial
    path('consultas/comercial/', ConsultaComercialAPIView.as_view(), name='consulta-comercial'), 
    path('consultas/cont-comercial/', ConsultaContatoComercialAPIView.as_view(), name='consulta-contato-comercial'), 
    path('consulta-massa-comercial/', BulkConsultaComercialAPIView.as_view(), name='consulta-massa-comercial'),
    path('consulta/comercial-regiao/', ComercialRegiaoAPIView.as_view(), name='consulta-comercial-regiao'),
   
   
    path('consultas/segurados/', RealizarConsultaSeguradosView.as_view(), name='realizar_consulta_segurados'),
    path('administradoras/', buscarAdms.as_view(), name='buscar_adms'),
    
    path('consultas/faturas/', RealizarConsultaFaturasView.as_view(), name='realizar-consulta-faturas'),
    
    path('consultas/faturamento/', BuscarFaturamento.as_view(), name='buscar-faturamento'),
    
    path('consultas/faturas/com-boletos/exportar-excel/', ExportarFaturasComBoletosExcel.as_view(), name='exportar-faturas-excel'),
    path("consultas/faturas/com-boletos/exportar-pdf/", ExportarFaturasComBoletosPDF.as_view(), name='exportar-faturas-pdf'),
    path('consultas/faturas/<str:numero_fatura>/', BuscarFaturaPorNumero.as_view(), name='consulta-fatura-por-numero'),
    
    path('consultas/administradoras/', BuscarAdministradoras.as_view(), name='consulta-administradoras'),
    path('consultas/administradora/por-nome/<str:nome>/', BuscarAdministradorasPorNome.as_view(), name='consulta-administradora-por-nome'),
    path('consultas/administradora/por-codigo/<str:codigo>/', BuscarAdministradorasPorCodigo.as_view(), name='consulta-administradora-por-codigo'),
    
    path('consultas/corretores/<str:codigo>/', BuscarCorretores.as_view(), name='consulta-corretor-por-codigo'),
    
    path('consultas/nfse/<str:documento>/', BuscarNFSEPorBoleto.as_view(), name='consulta-nfse-por-documento'),
    
    path('consultas/localidade/', BuscarLocalidade.as_view(), name='buscar-localidade'),
    path('cidades/autocomplete/', BuscarCidadesAutocomplete.as_view(), name='cidades-autocomplete'),
    
    path('comercial/agenda/', AgendamentoListCreateAPIView.as_view(), name='agendamento_list'),
    path('comercial/agenda/<int:pk>/', AgendamentoRetrieveUpdateDestroyAPIView.as_view(), name='agendamento_detail'),
    
    path('cotacao/incendio-conteudo/', calcular_cotacao_incendio, name='calcular_cotacao_incendio'),
    
    path('consultar-boletosfedbnk/', consultar_boletos_proxy, name='consultar_boletos_proxy'),
    path('consultar-boletofedbnk/', consultar_boleto, name='consultar_boleto_proxy'),
    path('cancelar-boletofedbnk/', cancelar_boleto, name='cancelar_boleto_proxy'), 
    
    path('automacao/separar-pdf/', AutomacaoSepararPDFView.as_view(), name='automacao-separar-pdf'),
    path('automacao/upload-pdfs-bbz/', AutomacaoUploadPDFsBBZView.as_view(), name='automacao-upload-pdfs-bbz'),
    path('automacao/processar-pdfs-bbz/', AutomacaoProcessarPDFsBBZView.as_view(), name='automacao-processar-pdfs-bbz'),
        
    # Recuperação de senha
    path("solicitar-reset-senha/", SolicitarResetSenhaView.as_view(), name="solicitar-reset-senha"),
    path("validar-token-reset/<str:token>/", ValidarTokenResetView.as_view(), name="validar-token-reset"),
    path("resetar-senha/", ResetarSenhaView.as_view(), name="resetar-senha"),
    
    # Boleto FedBNK
    path('boletofedbnk/cancelar/', CancelarBoletoFedBnkView.as_view(), name='cancelar-boleto-fedbnk'),
    
    
    path('analytics/faturamento/', AnalyticsFaturamentoPeriodoView.as_view(), name='analytics-faturamento-periodo'),
    path('analytics/administradoras/top/', AnalyticsTopAdministradorasView.as_view(), name='analytics-top-administradoras'),
    path('analytics/inadimplencia/', AnalyticsInadimplenciaView.as_view(), name='analytics-inadimplencia'),
    path('analytics/administradoras/faturamento/', AnalyticsFaturamentoPorAdministradoraView.as_view(), name='analytics-faturamento-administradora'),
    path('analytics/faturas/status/', AnalyticsStatusFaturasView.as_view(), name='analytics-status-faturas'),
    path('analytics/dashboard/', AnalyticsDashboardCompletoView.as_view(), name='analytics-dashboard-completo'),
    
    path('faturamento/tratamento-de-erros/rodar-procedure/', TratamentoDeErroView.as_view(), name='faturamento-tratamento-de-erro'),
    path('faturamento/formato-arquivos/converter-boleto-csv/', ConverterBoletoCSVView.as_view(), name='faturamento-converter-boleto-csv'),
    
    # Webhook do Santander
    path('api/santander/webhook/', SantanderWebhookView.as_view(), name="santander_webhook"),

    path("", include(router.urls)),
]
