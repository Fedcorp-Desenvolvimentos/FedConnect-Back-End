# Estágio 1: Build da aplicação
FROM python:3.13-slim AS builder

WORKDIR /app

# Instala dependências de compilação necessárias para o psycopg2 (se não usar o binary)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Instalamos as dependências em um diretório específico para facilitar a cópia
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copia o código
COPY . .

# Estágio 2: Imagem final para execução (produção)
FROM python:3.13-slim

WORKDIR /app

# Instala a libpq, que é necessária em runtime para o postgres
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

# Copia as bibliotecas instaladas do estágio anterior
COPY --from=builder /install /usr/local

# Copia o código da aplicação
COPY --from=builder /app .

# Executa o collectstatic aqui (agora que as libs estão no PATH)
# Lembre-se de ter os 'defaults' no settings.py como conversamos
RUN python manage.py collectstatic --noinput

# Comando para rodar a aplicação
# Usamos o caminho completo para evitar erro de PATH
CMD ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:8000", "bigcorp.wsgi:application"]