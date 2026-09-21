"""Reconstitui o registro de composição de vouchers emitidos antes do espelho.

Spec `consulta-espelho-voucher` (RF-VOU-005, ADR-0008). O registro nasceu em
2026-09-18; documentos anteriores não têm composição gravada e a consulta por
número devolve todas as parcelas do lançamento, com aviso.

Este comando **infere** a composição a partir das parcelas hoje **baixadas**
do voucher. Foi assim que o caso do voucher 20131244 fechou: a consulta com
filtro de baixadas devolvia exatamente as 169 linhas e os R$ 7.391,23 do PDF.

Limites da inferência, e por isso o registro fica marcado `reconstituido`:

* Vale enquanto as parcelas não baixadas continuarem não baixadas. Se uma
  delas for paga antes de rodar o comando, ela entra como se estivesse no PDF.
  Rode o quanto antes e confira o total contra o documento.
* Retenções e valor líquido não são recuperáveis (eram escolha da tela, não
  ficam no ERP): só o bruto é somado.

Uso:

    python manage.py reconstituir_espelho_voucher 20131244 --confirmar
    python manage.py reconstituir_espelho_voucher --favorecido 5912          # simula todos
    python manage.py reconstituir_espelho_voucher --favorecido 5912 --confirmar

Sem `--confirmar` o comando só mostra o que faria.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from consultas.services.fedhub_service import FedhubService
from fedhub.models import VoucherEmitido
from fedhub.services import espelho_voucher_service as espelho


class Command(BaseCommand):
    help = "Reconstitui a composição de vouchers antigos a partir das parcelas baixadas."

    def add_arguments(self, parser):
        parser.add_argument("numeros", nargs="*", help="Números de voucher. Vazio exige --favorecido.")
        parser.add_argument("--favorecido", help="Reconstitui todos os vouchers deste favorecido.")
        parser.add_argument("--confirmar", action="store_true", help="Grava. Sem isto, apenas simula.")
        parser.add_argument("--refazer", action="store_true", help="Refaz registros já reconstituídos.")

    def handle(self, *args, **opcoes):
        numeros = list(opcoes["numeros"])
        favorecido = opcoes["favorecido"]
        gravar = opcoes["confirmar"]
        refazer = opcoes["refazer"]

        if not numeros and not favorecido:
            raise CommandError("Informe ao menos um número de voucher ou --favorecido.")

        servico = FedhubService()

        if not numeros:
            numeros = self._numeros_do_favorecido(servico, favorecido)
            if not numeros:
                self.stdout.write(self.style.WARNING(f"Nenhum voucher encontrado para o favorecido {favorecido}."))
                return
            self.stdout.write(f"{len(numeros)} voucher(s) do favorecido {favorecido}.")

        if not gravar:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --confirmar para gravar."))

        total_gravados = 0
        for numero in numeros:
            total_gravados += self._reconstituir(servico, numero, gravar, refazer)

        if gravar:
            self.stdout.write(self.style.SUCCESS(f"{total_gravados} voucher(s) reconstituído(s)."))
        else:
            self.stdout.write(f"{total_gravados} voucher(s) seriam reconstituídos.")

    # ------------------------------------------------------------------ apoio

    def _numeros_do_favorecido(self, servico, favorecido):
        dados = servico.consultar_comissoes({"favorecido": favorecido}) or {}
        numeros = {
            str(linha.get("VOUCHER")).strip()
            for linha in dados.get("data", [])
            if str(linha.get("VOUCHER") or "").strip()
        }
        return sorted(numeros)

    def _reconstituir(self, servico, numero, gravar, refazer):
        numero = str(numero).strip()
        existente = VoucherEmitido.objects.filter(numero=numero).first()
        if existente and not (refazer and existente.reconstituido):
            origem = "reconstituído" if existente.reconstituido else "gravado na emissão"
            self.stdout.write(f"  {numero}: já tem registro ({origem}, {existente.itens.count()} parcela[s]) — pulado.")
            return 0

        dados = servico.consultar_comissoes({"voucher": numero, "status": "baixadas"}) or {}
        linhas = dados.get("data", [])
        if not linhas:
            self.stdout.write(self.style.WARNING(f"  {numero}: nenhuma parcela baixada — nada a reconstituir."))
            return 0

        bruto = sum((Decimal(str(l.get("VALOR") or 0)) for l in linhas), Decimal("0")).quantize(Decimal("0.01"))
        primeira = linhas[0]
        tipo_documento = "voucher"

        self.stdout.write(
            f"  {numero}: {len(linhas)} parcela(s), R$ {bruto} — favorecido {primeira.get('NOME', '')[:40]}"
        )
        if not gravar:
            return 1

        with transaction.atomic():
            voucher = espelho.registrar_emissao(
                numero,
                tipo_documento,
                {
                    "comissoes": linhas,
                    # Retenções e líquido não são recuperáveis: só o bruto.
                    "resumo": {"valor_total_bruto": bruto, "total_retencoes": 0, "valor_liquido_final": bruto},
                },
            )
            voucher.reconstituido = True
            voucher.save(update_fields=["reconstituido"])
        return 1
