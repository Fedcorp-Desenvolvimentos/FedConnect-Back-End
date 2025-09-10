# BigCorp API

Este repositório contém o backend da API do sistema BigCorp, construído com Django e Django REST Framework.

## Sumário

- [Visão Geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Configuração do Ambiente](#configuração-do-ambiente)
- [Instalação](#instalação)
- [Executando o Projeto](#executando-o-projeto)
- [Endpoints da API](#endpoints-da-api)
- [Documentação da API (Swagger/OpenAPI)](#documentação-da-api-swaggeropenapi)
- [Autenticação](#autenticação)
- [Gerenciamento de Usuários](#gerenciamento-de-usuários)
- [Consultas (CEP, CPF, CNPJ)](#consultas-cep-cpf-cnpj)
- [Contribuição](#contribuição)
- [Licença](#licença)

## Visão Geral

A BigCorp API fornece serviços de autenticação de usuários, gerenciamento de perfis de usuários e funcionalidades de consulta a APIs externas (CEP, CPF, CNPJ) com armazenamento de histórico.

## Funcionalidades

- Autenticação de usuários via JWT (JSON Web Tokens)
- Gerenciamento de perfis de usuários (CRUD)
- Consulta de informações de CEP via ViaCEP
- Consulta de informações de CPF (mock/integração futura)
- Consulta de informações de CNPJ 
- Histórico de consultas por usuário, com permissões de acesso (usuário comum vs. admin)

## Configuração do Ambiente

### Pré-requisitos

- Python 3.9+
- pip (gerenciador de pacotes Python)
- PostgreSQL (ou Docker para rodar PostgreSQL)

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (onde está `manage.py`) com as seguintes variáveis:

SUPABASE_URL={PROJECT URL}

SUPABASE_KEY={YOUR SUPABASE KEY}

SECRET_KEY_JWT={YOUR SECRET KEYJWT}

SUPABASE_DB_NAME=postgres

SUPABASE_DB_USER={YOUR USER}

SUPABASE_DB_PASSWORD={YOUR PASSWORD}

SUPABASE_DB_HOST=aws-0-sa-east-1.pooler.supabase.com

SUPABASE_DB_PORT=5432

SUPABASE_DB_SSL=True

*(Lembre-se de instalar `python-decouple` para ler essas variáveis)*

## Instalação

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/seu-usuario/seu-projeto.git](https://github.com/seu-usuario/seu-projeto.git)
    cd seu-projeto
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate   # Windows
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Crie o `requirements.txt` com `pip freeze > requirements.txt`)*

4.  **Execute as migrações do banco de dados:**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

5.  **Crie um superusuário (para acesso ao Admin e testes):**
    ```bash
    python manage.py createsuperuser
    ```

## Executando o Projeto

Para iniciar o servidor de desenvolvimento:

```bash
python manage.py runserver

A API estará disponível em http://127.0.0.1:8000/.
Endpoints da API
Base URL: http://127.0.0.1:8000/
Autenticação
POST /login/: Obter tokens JWT (Access e Refresh).
Body: {"email": "seu_email", "password": "sua_senha"}
POST /login/refresh/: Renovar Access Token usando Refresh Token.
Body: {"refresh": "seu_refresh_token"}
POST /logout/: Blacklistar Refresh Token para logout.
Body: {"refresh": "seu_refresh_token"}
Gerenciamento de Usuários
GET /users/: Listar todos os usuários (apenas para admins).
GET /users/<id>/: Obter detalhes de um usuário específico (admin) ou do próprio (usuário comum).
POST /users/: Criar um novo usuário.
PUT /users/<id>/: Atualizar todos os detalhes de um usuário.
PATCH /users/<id>/: Atualizar parcialmente os detalhes de um usuário.
DELETE /users/<id>/: Deletar um usuário (apenas para admins).
GET /users/me/: Obter detalhes do usuário autenticado.
Consultas
POST /consultas/realizar/: Realizar uma nova consulta a APIs externas.
Body: {"tipo_consulta": "endereco|cpf|cnpj", "parametro_consulta": "valor"}
GET /consultas/historico/: Listar o histórico de consultas (admin: todos; comum: próprio).
GET /consultas/historico/<int:pk>/: Obter detalhes de uma consulta específica pelo seu ID.
GET /consultas/historico/usuario/<int:user_id>/: Listar o histórico de consultas de um usuário específico pelo seu ID (apenas para admins).


Swagger UI: http://127.0.0.1:8000/schema/swagger-ui/
ReDoc: http://127.0.0.1:8000/schema/redoc/
Schema JSON: http://127.0.0.1:8000/schema/
Autenticação
Todas as rotas, exceto login/, users/ (POST) e schema/, exigem autenticação via JWT (JSON Web Tokens). Inclua o Access Token no cabeçalho Authorization como Bearer Token:

Authorization: Bearer <seu_access_token>

Contribuição
Instruções para contribuir com o projeto...

Licença
MIT License
