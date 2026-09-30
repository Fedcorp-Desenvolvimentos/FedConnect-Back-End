# Carregado automaticamente pelo gunicorn (cwd = /app). Flags de linha de
# comando (bind, timeout) continuam valendo por cima.
#
# Antes o gunicorn subia com 1 worker síncrono: uma chamada lenta ao FedHub
# (ngrok caído) segurava o único worker até o timeout e o site inteiro dava 504
# (incidente de 14/08/2026 e de 30/09/2026). Com threads, uma requisição presa
# ocupa só 1 thread; as demais continuam atendidas.
#
# No gthread o timeout vale para o heartbeat do worker, não para a duração da
# requisição — por isso o --timeout longo (endpoints de lote/relatório) não foi
# alterado. Ajuste por env: WEB_CONCURRENCY (workers) e GUNICORN_THREADS.
import os

worker_class = "gthread"
workers = int(os.getenv("WEB_CONCURRENCY", "3"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
