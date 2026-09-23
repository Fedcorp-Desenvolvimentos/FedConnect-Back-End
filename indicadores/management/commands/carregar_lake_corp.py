"""Carrega o espelho dos indicadores a partir do Data Lake CORP (fase 2 da ADR-0009).

Irmão de `carregar_snapshot_corp`, e de propósito quase igual: lê a origem,
monta o dicionário no contrato do snapshot e entrega ao MESMO carregador. O que
muda é de onde o dado vem; o que acontece com ele depois é idêntico, e é por
isso que os testes do snapshot continuam cobrindo a gravação.

Uso:

    python manage.py carregar_lake_corp
    python manage.py carregar_lake_corp --dsn "postgresql://lake_financeiro:...@host:5432/corp_lake"

Sem `--dsn`, usa `settings.LAKE_DSN`. A credencial deve ser a do papel
`lake_financeiro`, que é somente-leitura: este comando nunca escreve no lake.

Rodar duas vezes não duplica nada — a chave natural é `nosnum`, e a gravação é
upsert.
"""
from django.core.management.base import BaseCommand, CommandError

from indicadores.services import carga as servico_carga
from indicadores.services import lake as servico_lake
from indicadores.models import CargaCorp


class Command(BaseCommand):
    help = "Carrega o espelho dos indicadores a partir do Data Lake CORP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dsn",
            default=None,
            help="DSN do lake; sem isto, usa settings.LAKE_DSN. Use o papel somente-leitura.",
        )

    def handle(self, *args, **opcoes):
        try:
            dsn = opcoes["dsn"] or servico_lake.dsn_do_lake()
        except RuntimeError as erro:
            raise CommandError(str(erro)) from erro

        self.stdout.write(f"Lendo o lake em {servico_lake.mascarar(dsn)} ...")
        try:
            dados = servico_lake.extrair(dsn)
        except Exception as erro:  # noqa: BLE001
            # Falha de leitura NÃO grava CargaCorp: não houve carga nenhuma, e
            # registrar uma falha aqui confundiria "o lake não respondeu" com
            # "o dado do lake não presta", que é o que `carregar_snapshot` já
            # registra quando o contrato quebra.
            raise CommandError(f"não foi possível ler o lake: {erro}") from erro

        self.stdout.write(
            f"  extração do lake: {dados['extracao']} · "
            f"{len(dados['docs'])} documento(s), {len(dados['valores'])} com valores"
        )

        try:
            carga = servico_carga.carregar_snapshot(
                dados,
                arquivo=servico_lake.mascarar(dsn),
                origem=CargaCorp.ORIGEM_LAKE,
            )
        except servico_carga.SnapshotInvalido as erro:
            raise CommandError(f"o lake devolveu dado fora do contrato: {erro}") from erro

        self.stdout.write(self.style.SUCCESS(f"Carga {carga.pk} concluída em {carga.duracao_ms} ms."))
        self.stdout.write(f"  origem: {carga.origem} · extração: {carga.extraido_em}")
        self.stdout.write("  contagens:")
        for nome, valor in carga.contagens.items():
            self.stdout.write(f"    {nome}: {valor}")
        rejeitados = {nome: valor for nome, valor in carga.rejeitos.items() if valor}
        if rejeitados:
            self.stdout.write(self.style.WARNING("  rejeitos:"))
            for nome, valor in rejeitados.items():
                self.stdout.write(self.style.WARNING(f"    {nome}: {valor}"))
        else:
            self.stdout.write("  rejeitos: nenhum")
