@echo off
REM Navega para o diretório raiz do seu projeto Django
cd /d "D:\estacao53\Desktop\Codes\BIGCORP\BIGCORP---BackEnd"

REM Ativa o ambiente virtual (se você estiver usando um)
REM Se não usar venv, comente a linha abaixo
call "D:\estacao53\Desktop\Codes\BIGCORP\BIGCORP---BackEnd\venv\Scripts\activate.bat"

REM Executa o comando de gerenciamento do Django
REM Redireciona a saída para um arquivo de log
python manage.py purge_history --settings=bigcorp.settings >> D:\estacao53\Desktop\Codes\BIGCORP\BIGCORP---BackEnd\consultas\management\commands\logs\purge_log.txt 2>&1

REM Desativa o ambiente virtual (se você estiver usando um)
REM Se não usar venv, comente a linha abaixo
call deactivate

REM Opcional: Pausa para ver a saída se estiver executando manualmente
REM pause