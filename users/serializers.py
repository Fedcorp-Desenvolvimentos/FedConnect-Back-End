from rest_framework import serializers

from empresas.models import Empresa
from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para o modelo de usuário."""
    
    password = serializers.CharField(write_only=True, required=True)
    
    empresa_nome = serializers.CharField(write_only=True)
    empresa_cnpj = serializers.CharField(write_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'password', 'nome_completo',
            'nivel_acesso', 'is_active',
            'data_criacao', 'data_atualizacao',
            'empresa',
            'empresa_nome',
            'empresa_cnpj',
            'is_fed', 'cpf'
        ]
        read_only_fields = ['id', 'data_criacao', 'data_atualizacao']
    
    def create(self, validated_data):
        password = validated_data.pop('password')

        nome = validated_data.pop('empresa_nome')
        cnpj = validated_data.pop('empresa_cnpj')

        empresa, created = Empresa.objects.get_or_create(
            cnpj=cnpj,
            defaults={
                "nome": nome,
                "ativa": True
            }
        )

        if not created and empresa.nome != nome:
            empresa.nome = nome
            empresa.save()

        validated_data['empresa'] = empresa

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
    
    
