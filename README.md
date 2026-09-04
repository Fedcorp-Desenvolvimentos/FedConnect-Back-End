🧩 Fed Connect — Back-End | Grupo FedCorp

**Fed Connect Back-End** é a API REST que sustenta a plataforma interna do Grupo FedCorp. Construída com **Django + Django REST Framework**, concentra a autenticação, as consultas a bases cadastrais externas e internas, o processamento de planilhas e as regras de negócio das áreas comercial, financeira e operacional — comissões, vistorias, faturamento, cotações e agenda.

Este repositório contém o **back-end** da plataforma. A interface que o consome está em [FedConnect-FrontEnd](https://github.com/Fedcorp-Desenvolvimentos/FedConnect-FrontEnd).

## 🧠 Visão Geral

O objetivo do back-end é ser a **camada única de negócio e integração** do Fed Connect:

- padroniza o acesso a múltiplas APIs de dados cadastrais (BrasilAPI, BigDataCorp, ViaCEP) sob um contrato único;
- guarda o histórico de todas as consultas realizadas, por usuário;
- aplica autenticação JWT e as regras de permissão por nível de acesso;
- gera documentos oficiais (recibos, vouchers, boletos, relatórios) em PDF e Excel;
- orquestra as operações que dependem dos sistemas legados da companhia, através do **FedHub** (serviço FastAPI que conversa com o banco Firebird).

## 🎯 Funcionalidades Principais

🔐 **Autenticação e Usuários**
- Login com JWT (access + refresh), login com Google e logout.
- Modelo de usuário customizado (`users.Usuario`) com níveis de acesso.
- Fluxo de recuperação de senha por e-mail com token temporário e validação.
- CRUD de usuários e endpoint de perfil (`/users/me/`).

🔎 **Consultas Cadastrais**
- Consulta de CPF (dados de pessoa física), CNPJ (dados empresariais) e CEP (endereço).
- Histórico de consultas por registro, por usuário e por período.
- Consultas comerciais, de segurados/beneficiários, de faturas, de corretores, de administradoras, de NFS-e e de localidade.

📚 **Processamento de Planilhas**
- Geração dos modelos de planilha (CPF, CNPJ, CEP) para download.
- Processamento em massa dos arquivos enviados, devolvendo a planilha preenchida.
- Consulta em massa comercial e por região.

💰 **Comissões**
- Listagem de faturas disponíveis para emissão e das comissões individuais de cada fatura.
- Consulta por data de corte (com versão V2 de consistência reforçada) e por favorecido/produto.
- Emissão de **recibo do corretor** e **voucher de comissão** em PDF.
- Cancelamento de comissões em lote e consulta do histórico de vouchers emitidos.

🔧 **Vistorias**
- Consulta com filtros por período, estado, administradora, vistoriador e fatura, com paginação.
- Listagem de estados, vistoriadores ativos e administradoras.
- Exportação de relatórios em Excel e PDF.
- Filtro por vistoriador liberado apenas para `nivel_acesso` administrador ou moderador.

🧾 **Faturamento e Pagamentos**
- Emissão e dados de segunda via de boleto.
- Integrações FedBnk (consulta, sincronização e cancelamento de boletos) e FedPay.
- Conversão de formatos de arquivo e rotinas de tratamento de erros de faturamento.

📤 **Envio Porto**
- Geração dos arquivos de assistência, vida e dental, com controle de jobs, download do resultado, envio por SFTP e relatório de inconsistências.

📊 **Analytics**
- Faturamento consolidado, inadimplência, ranking e faturamento por administradora, status de faturas e dashboard agregado.

📄 **Cotação, Agenda e Cadastros**
- Cotação de seguro incêndio conteúdo.
- Agenda comercial e reservas.
- Cadastros de pessoas, gerentes comerciais, empresas, bancos, produtos e cedentes.

🤖 **Automação**
- Separação de PDFs, upload e processamento de lotes de arquivos.

## 🛠️ Tecnologias Utilizadas

| Categoria | Tecnologia |
|-----------|------------|
| Framework | Django 6 + Django REST Framework |
| Linguagem | Python 3.12+ |
| Autenticação | `djangorestframework-simplejwt` + `google-auth` |
| Banco de dados | PostgreSQL (Supabase Cloud) via `psycopg2` |
| Documentação | `drf-spectacular` (OpenAPI 3 / Swagger / ReDoc) |
| PDFs | ReportLab |
| Planilhas | pandas + openpyxl |
| HTTP externo | requests / httpx + tenacity (retry) |
| Servidor | Gunicorn + WhiteNoise |
| Config | python-decouple + python-dotenv |
| Deploy | Docker · Procfile · DigitalOcean App Platform |

## 🧱 Apps Django

| App | Responsabilidade |
|-----|------------------|
| `bigcorp` | Projeto Django: settings, urls e serviços transversais |
| `users` | Usuários, autenticação, níveis de acesso e reset de senha |
| `consultas` | Consulta PF, PJ, CEP, comercial, segurados, faturas e histórico |
| `planilha` | Processamento em massa de CPF/CNPJ/CEP e modelos de planilha |
| `fedhub` | Ponte com o FedHub — comissões, vistorias, faturamento, analytics, boletos, pessoas, produtos, envio Porto |
| `empresas` | Cadastro de empresas |
| `agenda` | Agenda e reserva de salas |
| `agenda_comercial` | Agenda da equipe comercial |
| `cotacao` | Cotação de seguros |
| `bank` | Integração bancária (FedBnk) |
| `questionarios` | Questionários de processos |
| `condomed` | Módulo de produto Condomed |

## 🔌 Endpoints da API

Os grupos principais (a lista completa e sempre atualizada está no Swagger):

| Grupo | Exemplos |
|-------|----------|
| Auth | `POST /login/` · `POST /login/refresh/` · `POST /google-login/` · `POST /logout/` |
| Senha | `POST /solicitar-reset-senha/` · `GET /validar-token-reset/<token>/` · `POST /resetar-senha/` |
| Usuários | `GET /users/me/` · `PUT /users/password/` |
| Consultas | `POST /consultas/realizar/` · `GET /consultas/historico/` · `GET /consultas/segurados/` · `GET /consultas/faturas/` |
| Planilhas | `GET /planilha-modelo-{cpf,cnpj,cep}/` · `POST /processar-{cpf,cnpj,cep}-planilha/` |
| Comissões | `GET /comissoes/faturas/` · `GET /comissoes/por-data-v2/<data_corte>/` · `POST /comissoes/emitir-recibo/` · `POST /comissoes/emitir-voucher/` · `POST /comissoes/cancelar/` |
| Vistorias | `GET /vistorias/` · `GET /vistorias/estados/` · `GET /vistorias/vistoriadores/` · `GET /vistorias/exportar/{excel,pdf}/` |
| Faturamento | `GET /faturamento/dados-segunda-via-boleto/<fatura>/` · `POST /faturamento/emissao-segunda-via-boleto/<fatura>/` |
| FedBnk / FedPay | `GET /consultar-boletosfedbnk/` · `POST /boletofedbnk/cancelar/` · `GET /fedpay/consulta/<fatura>/` |
| Envio Porto | `POST /envio-porto/assistencia/gerar/` · `GET /envio-porto/jobs/` · `POST /envio-porto/vida/gerar/` |
| Analytics | `GET /analytics/dashboard/` · `GET /analytics/faturamento/` · `GET /analytics/inadimplencia/` |
| Cotação | `POST /cotacao/incendio-conteudo/` |
| Agenda | `GET|POST /comercial/agenda/` |
| Cadastros | `/pessoas/` · `/bancos/` · `/produtos/` · `/cedentes/` · `/empresas/` · `/administradoras/` |
| Automação | `POST /automacao/separar-pdf/` · `POST /automacao/processar-pdfs-bbz/` |

## 📖 Documentação da API

Com o projeto rodando:

| Recurso | URL |
|---------|-----|
| Swagger UI | `/schema/swagger-ui/` |
| ReDoc | `/schema/redoc/` |
| Schema OpenAPI (YAML) | `/schema/` |
| Django Admin | `/admin/` |

A collection `API_BigCorp_Collection.yaml` na raiz do repositório também pode ser importada em clientes REST.

## 🔐 Autenticação

Todas as rotas, exceto login e recuperação de senha, exigem um token JWT no header:

```http
Authorization: Bearer <access_token>
```

| Item | Valor |
|------|-------|
| Validade do access token | 120 minutos |
| Validade do refresh token | 7 dias |
| Renovação | `POST /login/refresh/` |
| Timeout do token de reset de senha | 1 hora |

Permissões são avaliadas por `nivel_acesso` do usuário (ex.: administrador, moderador, consultor) — alguns filtros e endpoints são exclusivos de administrador/moderador.

## 🌐 Integrações Externas

| Serviço | Finalidade |
|---------|------------|
| **FedHub-Backend** (FastAPI + Firebird) | Comissões, vistorias, faturamento e dados dos sistemas legados |
| BrasilAPI | Consulta de CNPJ e CEP |
| BigDataCorp | Consulta de CPF e dados de pessoas |
| ViaCEP | Consulta de CEP (alternativa) |
| FedBnk / FedCorp Pay | Emissão, sincronização e cancelamento de boletos |
| Google OAuth | Login com conta corporativa |
| Google Maps | Geolocalização e mapas |
| SMTP (Gmail) | E-mails transacionais e de recuperação de senha |
| Monday.com | Automações e integrações internas |

## 🚀 Como Rodar

### Pré-requisitos
- Python 3.12+
- PostgreSQL acessível (ou credenciais do Supabase)
- Acesso ao FedHub, se for usar comissões/vistorias/faturamento

### Instalação

```bash
# 1 - Clone o repositório
git clone git@github.com:Fedcorp-Desenvolvimentos/FedConnect-Back-End.git
cd FedConnect-Back-End

# 2 - Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3 - Instale as dependências
pip install -r requirements.txt
```

### Variáveis de ambiente

Crie um `.env` na raiz:

```env
DEBUG=True
SECRET_KEY=defina_uma_chave_forte_e_exclusiva

# Banco de dados
DB_DATABASE=
DB_USERNAME=
DB_PASSWORD=
DB_HOST=
DB_PORT=5432
DB_SSLMODE=require

# URLs de integração
FRONTEND_URL=http://localhost:3000
FEDHUB_URL=http://localhost:8090

# E-mail
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
SUPPORT_EMAIL=
```

> ⚠️ O `.env` não é versionado e nunca deve ser commitado. Solicite os valores de cada ambiente ao time de desenvolvimento e use `SECRET_KEY` distinta em produção.

### Migrações e execução

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

A API fica disponível em `http://127.0.0.1:8000` e a documentação em `http://127.0.0.1:8000/schema/swagger-ui/`.

### Docker

```bash
docker compose up --build
```

## ⚙️ Requisitos Não-Funcionais

| Item | Valor |
|------|-------|
| Paginação padrão | 100 itens por página (máximo 200) |
| Timeout de consultas externas | até 600 s |
| Timezone | America/Sao_Paulo |
| Idioma | pt-BR |
| CORS | restrito por lista de origens permitidas |
| CSRF | habilitado |
| Retry | `tenacity` nas integrações externas |

## 🌎 Ambientes

| Ambiente | Endereço |
|----------|----------|
| Produção | DigitalOcean App Platform · `fedconnect.com.br` |
| Homologação | integrado ao front em `fedconnect-hml.vercel.app` |
| Local | http://127.0.0.1:8000 |

## 🧭 Processo de Desenvolvimento

O projeto segue um fluxo **spec-driven**: toda feature relevante nasce em `specs/<nome-da-feature>/` com três documentos aprovados em sequência antes da implementação:

1. `requirements.md` — o que precisa existir e por quê
2. `design.md` — como será construído
3. `tasks.md` — as tarefas executáveis

Complementos do diretório `specs/`:

- `CONVENCOES.md` — convenções de código e de escrita das specs
- `adr/` — registros de decisões de arquitetura (ADRs)
- `STATUS.md` — situação atual de cada spec
- `verificar.sh` — checagem de conformidade das specs

## 🤝 Contribuição

1. Crie uma branch a partir da `main` (`git checkout -b feature/minha-feature`).
2. Abra a spec da feature em `specs/` e siga o fluxo de aprovação por fase.
3. Implemente seguindo as convenções do repositório e mantenha o Swagger atualizado.
4. Abra um Pull Request descrevendo o que muda, como testar e os endpoints afetados.

## 🧑‍💻 Desenvolvido por

**Michel Policeno** — Desenvolvedor Back-End
[LinkedIn](https://www.linkedin.com/in/michel-policeno-85a866212) · [GitHub](https://github.com/Michel-Policeno)

**Daniel Mello** — Desenvolvedor Back-End
[LinkedIn](https://www.linkedin.com/in/danielmellocf/) · [GitHub](https://github.com/DMCFaria)

**Ingrid Aylana** — Desenvolvedora Front-End
[LinkedIn](https://www.linkedin.com/in/ingryd-aylana-silva-dos-santos-4a2701158)

---

<sub>Projeto interno do Grupo FedCorp. Uso restrito.</sub>
