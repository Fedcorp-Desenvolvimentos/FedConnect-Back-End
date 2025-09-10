from rest_framework import serializers
import json
from .models import HistoricoConsulta


class ConsultaRequestSerializer(serializers.Serializer):
    """
    Serializer para validar os dados de entrada ao realizar uma nova consulta.
    """
    tipo_consulta = serializers.ChoiceField(
        choices=HistoricoConsulta.TIPO_CONSULTA_CHOICES,
        help_text="Tipo de consulta a ser realizada (ex: 'cpf', 'cnpj', 'endereco', 'cpf_alternativa', 'cnpj_razao_social', 'cep_rua_cidade', 'comercial')."
    )
    parametro_consulta = serializers.CharField(
        style={'base_template': 'textarea.html'},
        help_text="O parâmetro da consulta (ex: um CPF, CNPJ, CEP, ou JSON para chaves alternativas)."
    )
    
    origem = serializers.CharField(
        max_length=50,
        default='manual',
        required=False,
        help_text="Origem da consulta (ex: 'manual' ou 'planilha')."
    )
    lote_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="ID único para agrupar consultas de um mesmo upload de planilha."
    )

    def validate(self, data):
        tipo_consulta = data.get("tipo_consulta")
        parametro_consulta = data.get("parametro_consulta")

        if tipo_consulta == "cpf":
            cleaned_param = parametro_consulta.replace(".", "").replace("-", "")
            if len(cleaned_param) != 11 or not cleaned_param.isdigit():
                raise serializers.ValidationError({"parametro_consulta": "CPF deve conter 11 dígitos numéricos."})
            data["parametro_consulta"] = cleaned_param

        elif tipo_consulta == "cnpj":
            cleaned_param = parametro_consulta.replace(".", "").replace("/", "").replace("-", "")
            if len(cleaned_param) != 14 or not cleaned_param.isdigit():
                raise serializers.ValidationError({"parametro_consulta": "CNPJ deve conter 14 dígitos numéricos."})
            data["parametro_consulta"] = cleaned_param

        elif tipo_consulta == "endereco":
            cleaned_param = parametro_consulta.replace("-", "")
            if len(cleaned_param) != 8 or not cleaned_param.isdigit():
                raise serializers.ValidationError({"parametro_consulta": "CEP deve conter 8 dígitos numéricos."})
            data["parametro_consulta"] = cleaned_param
        
        elif tipo_consulta == "cpf_alternativa":
            try:
                parsed_params = json.loads(parametro_consulta)
                if not all(k in parsed_params for k in ["Datasets", "q", "Limit"]):
                    raise serializers.ValidationError("JSON de parametro_consulta para 'cpf_alternativa' deve conter 'Datasets', 'q' e 'Limit'.")
                
                q_string = parsed_params.get("q", "")
                if not isinstance(q_string, str) or "name{" not in q_string.replace(' ', ''):
                     raise serializers.ValidationError({"q": "O campo 'q' deve ser uma string e conter o nome na chave 'name{}'."})
                
                data["parametro_consulta"] = parsed_params

            except json.JSONDecodeError:
                raise serializers.ValidationError({"parametro_consulta": "Para 'cpf_alternativa', o parâmetro deve ser um JSON string válido."})
            except serializers.ValidationError as e:
                raise serializers.ValidationError({"parametro_consulta": e.detail})
            except Exception as e:
                raise serializers.ValidationError({"parametro_consulta": f"Erro inesperado na validação do JSON: {str(e)}"})

        elif tipo_consulta == "cnpj_razao_social":
            try:
                parsed_params = json.loads(parametro_consulta)
                if not all(k in parsed_params for k in ["Datasets", "q", "Limit"]):
                    raise serializers.ValidationError("JSON de parametro_consulta para 'cnpj_razao_social' deve conter 'Datasets', 'q' e 'Limit'.")
                
                q_string = parsed_params.get("q", "")
                if not isinstance(q_string, str) or "name{" not in q_string.replace(' ', ''):
                     raise serializers.ValidationError({"q": "O campo 'q' (BigDataCorp CNPJ) deve ser uma string e conter o nome da empresa na chave 'name{}'."})
                
                data["parametro_consulta"] = parsed_params

            except json.JSONDecodeError:
                raise serializers.ValidationError({"parametro_consulta": "Para 'cnpj_razao_social', o parâmetro deve ser um JSON string válido."})
            except serializers.ValidationError as e:
                raise serializers.ValidationError({"parametro_consulta": e.detail})
            except Exception as e:
                raise serializers.ValidationError({"parametro_consulta": f"Erro inesperado na validação do JSON de CNPJ: {str(e)}"})

        # --- NOVA LÓGICA PARA CEP POR RUA E CIDADE (VIACEP) ---
        elif tipo_consulta == "cep_rua_cidade":
            try:
                parsed_params = json.loads(parametro_consulta)
                # O ViaCEP espera estado, cidade e logradouro
                if not all(k in parsed_params for k in ["estado", "cidade", "logradouro"]):
                    raise serializers.ValidationError("JSON de parametro_consulta para 'cep_rua_cidade' deve conter as chaves 'estado', 'cidade' e 'logradouro'.")
                
                # Validação de tipos (opcional, mas boa prática)
                if not all(isinstance(parsed_params[k], str) and parsed_params[k] for k in ["estado", "cidade", "logradouro"]):
                    raise serializers.ValidationError("Os campos 'estado', 'cidade' e 'logradouro' devem ser strings não vazias.")

                # O estado deve ser uma UF válida (2 caracteres)
                if len(parsed_params["estado"]) != 2 or not parsed_params["estado"].isalpha():
                    raise serializers.ValidationError({"estado": "O estado deve ser uma UF válida (2 letras)."})
                
                data["parametro_consulta"] = parsed_params

            except json.JSONDecodeError:
                raise serializers.ValidationError({"parametro_consulta": "Para 'cep_rua_cidade', o parâmetro deve ser um JSON string válido."})
            except serializers.ValidationError as e:
                raise serializers.ValidationError({"parameatro_consulta": e.detail})
            except Exception as e:
                raise serializers.ValidationError({"parametro_consulta": f"Erro inesperado na validação do JSON de CEP por rua/cidade: {str(e)}"})
        
        else:
             if tipo_consulta not in [choice[0] for choice in HistoricoConsulta.TIPO_CONSULTA_CHOICES]:
                raise serializers.ValidationError({"tipo_consulta": "Tipo de consulta inválido."})
        
        return data

# ... HistoricoConsultaSerializer permanece inalterado ...
class HistoricoConsultaSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo de histórico de consulta.
    Usado para exibir os dados salvos no banco de dados.
    """
    usuario_email = serializers.SerializerMethodField(
        help_text="Email do usuário que realizou a consulta."
    )
    tipo_consulta_display = serializers.SerializerMethodField(
        help_text="Nome amigável do tipo de consulta."
    )

    class Meta:
        model = HistoricoConsulta
        fields = [
            'id',
            'usuario',
            'usuario_email',
            'tipo_consulta',
            'tipo_consulta_display',
            'origem',
            'parametro_consulta',
            'data_consulta',
            'resultado'
        ]
        read_only_fields = ['id', 'usuario', 'data_consulta', 'resultado']

    def get_usuario_email(self, obj):
        return obj.usuario.email if obj.usuario else None

    def get_tipo_consulta_display(self, obj):
        return obj.get_tipo_consulta_display()
    
    
    
class BulkCnpjRequestSerializer(serializers.Serializer):
    """
    Serializador para receber uma lista de CNPJs para consulta em massa.
    Se a entrada for um arquivo, você precisará ajustar para serializers.FileField.
    """
    cnpjs = serializers.ListField(
        child=serializers.CharField(max_length=18),
        help_text="Lista de CNPJs para consulta em massa."
    )
   