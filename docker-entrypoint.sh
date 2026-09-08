#!/bin/sh
# Ponto de entrada do contêiner: aplica migrações pendentes e só então sobe
# o processo pedido (gunicorn). Falha de migração derruba o start — melhor
# um deploy que não sobe do que um que sobe quebrado.
set -e

echo "[entrypoint] aplicando migrações pendentes..."
python manage.py migrate --noinput

echo "[entrypoint] iniciando: $*"
exec "$@"
