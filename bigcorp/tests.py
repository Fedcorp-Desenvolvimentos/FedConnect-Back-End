import unittest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import Usuario
from consultas.models import DadosCPF, DadosCNPJ, Endereco, HistoricoConsulta
import json


class UsuarioTestCase(TestCase):
    """Testes para o módulo de usuários e autenticação."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        self.client = APIClient()
        
        # Cria um usuário administrador
        self.admin_user = Usuario.objects.create_user(
            email='admin@example.com',
            password='senha123',
            nivel_acesso='admin',
            nome_completo='Administrador Teste'
        )
        
        # Cria um usuário comum
        self.normal_user = Usuario.objects.create_user(
            email='usuario@example.com',
            password='senha123',
            nivel_acesso='usuario',
            nome_completo='Usuário Comum Teste'
        )
    
    def test_login(self):
        """Testa o login de usuários e geração de token JWT."""
        url = reverse('token_obtain_pair')
        
        # Testa login com usuário administrador
        data = {
            'email': 'admin@example.com',
            'password': 'senha123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('access' in response.data)
        self.assertTrue('refresh' in response.data)
        self.assertTrue('user' in response.data)
        self.assertEqual(response.data['user']['nivel_acesso'], 'admin')
        
        # Testa login com usuário comum
        data = {
            'email': 'usuario@example.com',
            'password': 'senha123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('access' in response.data)
        self.assertTrue('refresh' in response.data)
        self.assertTrue('user' in response.data)
        self.assertEqual(response.data['user']['nivel_acesso'], 'usuario')
    
    def test_acesso_admin(self):
        """Testa o acesso de administradores a recursos protegidos."""
        # Autentica como administrador
        self.client.force_authenticate(user=self.admin_user)
        
        # Testa acesso à lista de usuários (apenas admin pode ver todos)
        url = reverse('usuario-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Deve ver todos os usuários
    
    def test_acesso_usuario_comum(self):
        """Testa o acesso de usuários comuns a recursos protegidos."""
        # Autentica como usuário comum
        self.client.force_authenticate(user=self.normal_user)
        
        # Testa acesso à lista de usuários (usuário comum só vê a si mesmo)
        url = reverse('usuario-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Deve ver apenas a si mesmo


class ConsultaTestCase(TestCase):
    """Testes para o módulo de consultas de dados cadastrais."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        self.client = APIClient()
        
        # Cria um usuário administrador
        self.admin_user = Usuario.objects.create_user(
            email='admin@example.com',
            password='senha123',
            nivel_acesso='admin',
            nome_completo='Administrador Teste'
        )
        
        # Cria um usuário comum
        self.normal_user = Usuario.objects.create_user(
            email='usuario@example.com',
            password='senha123',
            nivel_acesso='usuario',
            nome_completo='Usuário Comum Teste'
        )
        
        # Cria dados de teste para CPF
        self.cpf = DadosCPF.objects.create(
            cpf='12345678900',
            nome='Pessoa Teste',
            situacao_cadastral='Regular'
        )
        
        # Cria dados de teste para CNPJ
        self.cnpj = DadosCNPJ.objects.create(
            cnpj='12345678000190',
            razao_social='Empresa Teste LTDA',
            nome_fantasia='Empresa Teste',
            situacao_cadastral='Ativa'
        )
        
        # Cria endereços de teste
        self.endereco_cpf = Endereco.objects.create(
            cpf=self.cpf,
            tipo='residencial',
            logradouro='Rua Teste',
            numero='123',
            bairro='Bairro Teste',
            cidade='Cidade Teste',
            estado='SP',
            cep='12345678'
        )
        
        self.endereco_cnpj = Endereco.objects.create(
            cnpj=self.cnpj,
            tipo='comercial',
            logradouro='Avenida Teste',
            numero='456',
            bairro='Bairro Comercial',
            cidade='Cidade Teste',
            estado='SP',
            cep='87654321'
        )
    
    def test_consulta_cpf(self):
        """Testa a consulta de dados de CPF."""
        # Autentica como usuário comum
        self.client.force_authenticate(user=self.normal_user)
        
        # Testa consulta de CPF existente
        url = reverse('cpf-consultar') + f'?cpf={self.cpf.cpf}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cpf'], self.cpf.cpf)
        self.assertEqual(response.data['nome'], self.cpf.nome)
        
        # Verifica se a consulta foi registrada no histórico
        historico = HistoricoConsulta.objects.filter(
            usuario=self.normal_user,
            tipo_consulta='cpf',
            parametro_consulta=self.cpf.cpf
        )
        self.assertEqual(historico.count(), 1)
    
    def test_consulta_cnpj(self):
        """Testa a consulta de dados de CNPJ."""
        # Autentica como usuário comum
        self.client.force_authenticate(user=self.normal_user)
        
        # Testa consulta de CNPJ existente
        url = reverse('cnpj-consultar') + f'?cnpj={self.cnpj.cnpj}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cnpj'], self.cnpj.cnpj)
        self.assertEqual(response.data['razao_social'], self.cnpj.razao_social)
        
        # Verifica se a consulta foi registrada no histórico
        historico = HistoricoConsulta.objects.filter(
            usuario=self.normal_user,
            tipo_consulta='cnpj',
            parametro_consulta=self.cnpj.cnpj
        )
        self.assertEqual(historico.count(), 1)
    
    def test_consulta_endereco(self):
        """Testa a consulta de endereços por CPF e CNPJ."""
        # Autentica como usuário comum
        self.client.force_authenticate(user=self.normal_user)
        
        # Testa consulta de endereço por CPF
        url = reverse('endereco-por-cpf') + f'?cpf={self.cpf.cpf}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['logradouro'], self.endereco_cpf.logradouro)
        
        # Testa consulta de endereço por CNPJ
        url = reverse('endereco-por-cnpj') + f'?cnpj={self.cnpj.cnpj}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['logradouro'], self.endereco_cnpj.logradouro)


class HistoricoTestCase(TestCase):
    """Testes para o módulo de histórico de consultas."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        self.client = APIClient()
        
        # Cria um usuário administrador
        self.admin_user = Usuario.objects.create_user(
            email='admin@example.com',
            password='senha123',
            nivel_acesso='admin',
            nome_completo='Administrador Teste'
        )
        
        # Cria um usuário comum
        self.normal_user = Usuario.objects.create_user(
            email='usuario@example.com',
            password='senha123',
            nivel_acesso='usuario',
            nome_completo='Usuário Comum Teste'
        )
        
        # Cria históricos de consulta para o usuário comum
        self.historico1 = HistoricoConsulta.objects.create(
            usuario=self.normal_user,
            tipo_consulta='cpf',
            parametro_consulta='12345678900',
            resultado={'cpf': '12345678900', 'nome': 'Pessoa Teste'}
        )
        
        self.historico2 = HistoricoConsulta.objects.create(
            usuario=self.normal_user,
            tipo_consulta='cnpj',
            parametro_consulta='12345678000190',
            resultado={'cnpj': '12345678000190', 'razao_social': 'Empresa Teste LTDA'}
        )
        
        # Cria histórico de consulta para o usuário admin
        self.historico3 = HistoricoConsulta.objects.create(
            usuario=self.admin_user,
            tipo_consulta='cpf',
            parametro_consulta='98765432100',
            resultado={'cpf': '98765432100', 'nome': 'Outra Pessoa'}
        )
    
    def test_historico_admin(self):
        """Testa o acesso de administradores ao histórico de consultas."""
        # Autentica como administrador
        self.client.force_authenticate(user=self.admin_user)
        
        # Testa acesso ao histórico completo (admin vê todos)
        url = reverse('historico-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)  # Deve ver todos os históricos
    
    def test_historico_usuario_comum(self):
        """Testa o acesso de usuários comuns ao histórico de consultas."""
        # Autentica como usuário comum
        self.client.force_authenticate(user=self.normal_user)
        
        # Testa acesso ao histórico (usuário comum só vê o próprio)
        url = reverse('historico-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Deve ver apenas seus próprios históricos
        
        # Verifica se os históricos são realmente do usuário
        for item in response.data['results']:
            self.assertEqual(item['usuario'], self.normal_user.id)


if __name__ == '__main__':
    unittest.main()
