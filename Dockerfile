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

# Migrações rodam no START do contêiner, não no build: no build não há banco
# acessível, e é o start que tem as variáveis de ambiente de produção.
# Sem isto, todo deploy com migração nova subia código que consulta colunas
# inexistentes e a tela respondia 500 (incidente do CIPA, 08/09/2026).
# `migrate` é idempotente: instância que subir depois não refaz nada.
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Usamos o comando 'python -m gunicorn' que é mais confiável para encontrar o módulo
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "360", "bigcorp.wsgi:application"]