from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UsuarioViewSet, LogoutView, CustomTokenObtainPairView, PasswordView
from consultas.views import BuscarFaturaDinamicamente, BuscarFaturaPorNumero, RealizarConsultaView, HistoricoConsultaListView, HistoricoConsultaDetailView, HistoricoConsultaUserListView
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
from consultas.boletofedbnk import consultar_boletos_proxy, consultar_boleto


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
    path("logout/", LogoutView.as_view(), name="logout"),
    # Rota para o endpoint "me" do usuário
    path("users/me/", UsuarioViewSet.as_view({"get": "me"}), name="usuario-me"),
    path("users/password/", PasswordView.as_view(), name="usuario-password"),
    
    # Rotas de Consultas#
    path('consultas/realizar/', RealizarConsultaView.as_view(), name='realizar-consulta'),
    path('consultas/historico/', HistoricoConsultaListView.as_view(), name='historico-consultas'),
    path('consultas/historico/<int:pk>/', HistoricoConsultaDetailView.as_view(), name='historico-consulta-detail'),
    path('consultas/historico/usuario/<int:user_id>/', HistoricoConsultaUserListView.as_view(), name='historico-consultas-por-usuario'),
    path('consultas/fatura/fatura-dinamica/', BuscarFaturaDinamicamente.as_view(), name='buscar-fatura-dinamicamente'),
    path('consultas/fatura/<str:numero_fatura>/', BuscarFaturaPorNumero.as_view(), name='consulta-fatura-por-numero'),
    
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
    
    path('comercial/agenda/', AgendamentoListCreateAPIView.as_view(), name='agendamento_list'),
    path('comercial/agenda/<int:pk>/', AgendamentoRetrieveUpdateDestroyAPIView.as_view(), name='agendamento_detail'),
    
    path('cotacao/incendio-conteudo/', calcular_cotacao_incendio, name='calcular_cotacao_incendio'),
    
    path('consultar-boletosfedbnk/', consultar_boletos_proxy, name='consultar_boletos_proxy'),
    path('consultar-boletofedbnk/', consultar_boleto, name='consultar_boletos_proxy'),    # Inclua as rotas geradas pelo Router (ViewSets) por último
    path("", include(router.urls)),
]
