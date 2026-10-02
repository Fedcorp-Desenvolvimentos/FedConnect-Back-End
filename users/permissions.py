from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permissão personalizada para permitir apenas usuários com nível de acesso 'admin'.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.nivel_acesso == 'admin'


class IsAdminOrTi(permissions.BasePermission):
    """
    Permissão personalizada para permitir apenas usuários com nível de acesso 'admin' ou 'ti'.
    Usada pela gravação de metas dos indicadores (PA-018, revisões de 2026-09-23 e 2026-10-02).
    """

    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.nivel_acesso in ('admin', 'ti'))


class LeituraAutenticadaEscritaAdminOuTi(permissions.BasePermission):
    """
    Leitura (GET/HEAD/OPTIONS) para qualquer autenticado; escrita só para 'admin' ou 'ti'.
    Usada pelas metas dos indicadores (PA-018, revisão de 2026-10-02): todos leem o painel
    e as metas, só admin e ti cadastram ou alteram.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.nivel_acesso in ('admin', 'ti')


class IsAdminOrModerador(permissions.BasePermission):
    """
    Permissão personalizada para permitir apenas usuários com nível de acesso 'admin' ou 'moderador'.
    """

    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.nivel_acesso in ('admin', 'moderador', 'vistoria'))


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permissão personalizada para permitir que usuários vejam apenas seus próprios recursos,
    enquanto administradores podem ver todos os recursos.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Administradores podem acessar qualquer objeto
        if request.user.nivel_acesso == 'admin':
            return True
        
        # Verifica se o objeto tem um atributo 'usuario' e se corresponde ao usuário atual
        if hasattr(obj, 'usuario'):
            return obj.usuario == request.user
        
        # Para outros casos, verifica se o próprio objeto é o usuário
        return obj == request.user


class IsCondomedOrAdmin(permissions.BasePermission):
    """
    Permissão para os endpoints da Condomed (cursos CIPA): os níveis
    'condomed', 'esocial' (Condomed + robô eSocial) e 'admin' (RF-CIP-004).
    """

    NIVEIS = ('condomed', 'esocial', 'admin')

    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.nivel_acesso in self.NIVEIS)


class IsFinanceiroOuFaturamentoOuAdmin(permissions.BasePermission):
    """
    Relatórios do Financeiro (faturas pendentes — spec relatorio-faturas-pendentes,
    RNF-FAT-001): níveis 'financeiro', 'faturamento' e 'admin'. Decisão do dono
    em 2026-09-09; o relatório expõe carteira e inadimplência, então não basta
    estar autenticado.
    """

    NIVEIS = ('financeiro', 'faturamento', 'faturamento-analista', 'admin')

    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.nivel_acesso in self.NIVEIS)
