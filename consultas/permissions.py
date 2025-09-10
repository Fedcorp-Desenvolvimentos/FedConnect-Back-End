from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permissão personalizada para permitir apenas usuários com nível de acesso 'admin'.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.nivel_acesso == 'admin'


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
