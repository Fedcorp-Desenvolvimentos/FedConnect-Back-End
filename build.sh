#!/usr/bin/env bash

# Instala as dependências
pip install -r requirements.txt

# Aplica as migrações do banco de dados
python manage.py migrate

# Coleta os arquivos estáticos
python manage.py collectstatic --noinput --clear