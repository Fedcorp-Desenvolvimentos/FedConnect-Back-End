from supabase import create_client
from django.conf import settings


class SupabaseService:
    """
    Serviço para interagir com o Supabase.
    Fornece métodos para operações CRUD e consultas personalizadas.
    """
    
    def __init__(self):
        self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    
    def get_client(self):
        """Retorna o cliente Supabase inicializado."""
        return self.supabase
    
    # Métodos para CPF
    def consultar_cpf(self, cpf):
        """Consulta dados de um CPF específico."""
        return self.supabase.table('dados_cpf').select('*').eq('cpf', cpf).execute()
    
    def listar_cpfs(self, limit=100, offset=0):
        """Lista todos os CPFs cadastrados com paginação."""
        return self.supabase.table('dados_cpf').select('*').range(offset, offset + limit - 1).execute()
    
    def inserir_cpf(self, dados):
        """Insere um novo registro de CPF."""
        return self.supabase.table('dados_cpf').insert(dados).execute()
    
    def atualizar_cpf(self, cpf, dados):
        """Atualiza os dados de um CPF específico."""
        return self.supabase.table('dados_cpf').update(dados).eq('cpf', cpf).execute()
    
    def deletar_cpf(self, cpf):
        """Remove um registro de CPF."""
        return self.supabase.table('dados_cpf').delete().eq('cpf', cpf).execute()
    
    # Métodos para CNPJ
    def consultar_cnpj(self, cnpj):
        """Consulta dados de um CNPJ específico."""
        return self.supabase.table('dados_cnpj').select('*').eq('cnpj', cnpj).execute()
    
    def listar_cnpjs(self, limit=100, offset=0):
        """Lista todos os CNPJs cadastrados com paginação."""
        return self.supabase.table('dados_cnpj').select('*').range(offset, offset + limit - 1).execute()
    
    def inserir_cnpj(self, dados):
        """Insere um novo registro de CNPJ."""
        return self.supabase.table('dados_cnpj').insert(dados).execute()
    
    def atualizar_cnpj(self, cnpj, dados):
        """Atualiza os dados de um CNPJ específico."""
        return self.supabase.table('dados_cnpj').update(dados).eq('cnpj', cnpj).execute()
    
    def deletar_cnpj(self, cnpj):
        """Remove um registro de CNPJ."""
        return self.supabase.table('dados_cnpj').delete().eq('cnpj', cnpj).execute()
    
    # Métodos para Endereços
    def consultar_enderecos_por_cpf(self, cpf):
        """Consulta endereços associados a um CPF específico."""
        return self.supabase.table('endereco').select('*').eq('cpf_id', cpf).execute()
    
    def consultar_enderecos_por_cnpj(self, cnpj):
        """Consulta endereços associados a um CNPJ específico."""
        return self.supabase.table('endereco').select('*').eq('cnpj_id', cnpj).execute()
    
    def inserir_endereco(self, dados):
        """Insere um novo registro de endereço."""
        return self.supabase.table('endereco').insert(dados).execute()
    
    def atualizar_endereco(self, id, dados):
        """Atualiza os dados de um endereço específico."""
        return self.supabase.table('endereco').update(dados).eq('id', id).execute()
    
    def deletar_endereco(self, id):
        """Remove um registro de endereço."""
        return self.supabase.table('endereco').delete().eq('id', id).execute()
    
    # Métodos para Histórico de Consultas
    def registrar_consulta(self, dados):
        """Registra uma nova consulta no histórico."""
        return self.supabase.table('historico_consulta').insert(dados).execute()
    
    def listar_historico_por_usuario(self, usuario_id, limit=100, offset=0):
        """Lista o histórico de consultas de um usuário específico."""
        return self.supabase.table('historico_consulta').select('*').eq('usuario_id', usuario_id).order('data_consulta', desc=True).range(offset, offset + limit - 1).execute()
    
    def listar_todo_historico(self, limit=100, offset=0):
        """Lista todo o histórico de consultas (para administradores)."""
        return self.supabase.table('historico_consulta').select('*').order('data_consulta', desc=True).range(offset, offset + limit - 1).execute()
