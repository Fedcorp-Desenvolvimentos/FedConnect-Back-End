# Estágio 1: Build da aplicação (não toca no banco de dados)
FROM python:3.13-slim AS builder

WORKDIR /app

# Instala as dependências, incluindo as de desenvolvimento
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da sua aplicação
COPY . .

# Executa o collectstatic aqui (sem necessidade de banco de dados)
RUN python manage.py collectstatic --noinput

# Estágio 2: Imagem final para execução (produção)
FROM python:3.10-slim

WORKDIR /app

# Copia os arquivos da imagem de build, incluindo os arquivos estáticos
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app .

# Comando para rodar a aplicação em produção
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "sua_app.wsgi:application"]