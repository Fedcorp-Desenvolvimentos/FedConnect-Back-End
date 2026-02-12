FROM python:3.13-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .

# Forçamos a atualização do pip e instalação do gunicorn explicitamente 
# para garantir que ele exista mesmo se faltar no requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copia o código
COPY . .

# Executa collectstatic (com os defaults no settings.py)
RUN python manage.py collectstatic --noinput

# Expõe a porta
EXPOSE 8000

# Usamos o comando 'python -m gunicorn' que é mais confiável para encontrar o módulo
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8000", "bigcorp.wsgi:application"]