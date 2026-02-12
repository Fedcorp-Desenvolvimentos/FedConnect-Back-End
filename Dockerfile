FROM python:3.13-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para o PostgreSQL e compilação
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos
COPY requirements.txt .

# Instala as dependências (certifique-se que gunicorn está no requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Executa o collectstatic (precisa dos 'defaults' no settings.py)
RUN python manage.py collectstatic --noinput

# Exponha a porta 8000
EXPOSE 8000

# Comando simplificado: o Docker encontrará o gunicorn no PATH do Python
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "bigcorp.wsgi:application"]