from rest_framework import serializers
from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para o modelo de usuário."""
    
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    class Meta:
        model = Usuario
        fields = ['id', 'email','password' ,'nome_completo', 'nivel_acesso', 'is_active', 'data_criacao', 'data_atualizacao', 'empresa', 'is_fed', 'cpf']
        read_only_fields = ['id', 'data_criacao', 'data_atualizacao']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def create(self, validated_data):
        """Cria um novo usuário com senha criptografada."""
        password = validated_data.pop('password')
        user = Usuario(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """Atualiza um usuário existente, tratando a senha corretamente."""
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance