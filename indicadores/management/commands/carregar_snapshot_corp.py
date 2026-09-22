"""Carrega um snapshot da CORP no espelho dos indicadores (RF-IEX-001, T-IEX-1.4).

Spec `indicadores-executivos`, ADR-0009. O arquivo fica FORA do repositório
(tem CPF e nome de cliente); o comando lê do caminho informado, faz upsert de
tudo numa transação, classifica renovação e registra a `CargaCorp`.

Uso:

    python manage.py carregar_snapshot_corp ../.local-dev/dados-teste-corp.json

Rodar duas vezes com o mesmo arquivo não duplica nada (chave natural
`nosnum`). Arquivo inexistente ou fora do contrato → `CommandError`, com a
carga gravada como falha e o motivo.
"""
from django.core.management.base import BaseCommand, CommandError

from indicadores.services import carga as servico_carga


class Command(BaseCommand):
    help = "Carrega o snapshot da CORP (JSON) no espelho dos indicadores executivos."

    def add_arguments(self, parser):
        parser.add_argument("caminho", help="Caminho do JSON no contrato do snapshot (fora do git).")

    def handle(self, *args, **opcoes):
        caminho = opcoes["caminho"]
        self.stdout.write(f"Carregando {caminho} ...")
        try:
            carga = servico_carga.carregar_arquivo(caminho)
        except servico_carga.SnapshotInvalido as erro:
            raise CommandError(f"Snapshot inválido: {erro}") from erro

        self.stdout.write(self.style.SUCCESS(f"Carga {carga.pk} concluída em {carga.duracao_ms} ms."))
        self.stdout.write(f"  origem: {carga.origem} · gerado_em: {carga.gerado_em} · extração: {carga.extraido_em}")
        self.stdout.write("  contagens:")
        for nome, valor in carga.contagens.items():
            self.stdout.write(f"    {nome}: {valor}")
        rejeitados = {nome: valor for nome, valor in carga.rejeitos.items() if valor}
        if rejeitados:
            self.stdout.write(self.style.WARNING("  rejeitos (gravados com referência nula, nunca descartados):"))
            for nome, valor in rejeitados.items():
                self.stdout.write(f"    {nome}: {valor}")
        else:
            self.stdout.write("  rejeitos: nenhum")
