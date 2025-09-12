# Estágio 1: Build da aplicação
FROM python:3.13-slim AS builder

WORKDIR /app

# Instala as dependências (inclui gunicorn e outras libs)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da sua aplicação
COPY . .

# Executa o collectstatic
RUN python manage.py collectstatic --noinput

# Estágio 2: Imagem final para execução (produção)
FROM python:3.13-slim

WORKDIR /app

# Copia o ambiente virtual completo do estágio de build
COPY --from=builder /usr/local /usr/local

# Copia o código da sua aplicação
COPY --from=builder /app .

# Comando para rodar a aplicação em produção
# A sua aplicação principal deve ser o nome da pasta que contém o settings.py
# Ex: se o seu projeto é 'bigcorp', a linha deve ser:
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "bigcorp.wsgi:application"]