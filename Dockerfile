# Usa uma imagem oficial do Python como base, agora com a versão 3.13
FROM python:3.13-slim

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# Instala as dependências de sistema necessárias, como a biblioteca para o PostgreSQL.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos para o diretório de trabalho.
COPY requirements.txt .

# Instala as dependências do Python.
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação para o contêiner.
COPY . .

# Coleta os arquivos estáticos para o Gunicorn
RUN python manage.py collectstatic --noinput

# Expõe a porta que a aplicação Django vai usar.
EXPOSE 8000

# Comando para rodar as migrações e o servidor Gunicorn
CMD ["/bin/sh", "-c", "python manage.py migrate --noinput && gunicorn bigcorp.wsgi:application --bind 0.0.0.0:8000"]