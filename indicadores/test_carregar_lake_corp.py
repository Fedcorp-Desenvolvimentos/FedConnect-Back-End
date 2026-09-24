# indicadores/test_carregar_lake_corp.py
#
# A carga pelo lake remove do espelho o que o lake não traz mais (decisão do
# pacote do lake de 23/09/2026: documento que a CORP apagou é marcado lá e
# some da extração). O lake é substituído por `patch`, como o resto da suíte
# faz com o que é externo.

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from indicadores.models import Producao
from indicadores.services import lake as servico_lake

COLUNAS = ["nosnum", "tipdoc", "seg", "ramo", "cli", "inivig", "fimvig", "datemi",
           "nosnum_ren", "cancelado", "renov_sit", "sin", "cliente"]


def _extracao(*nosnums):
    return {
        "gerado_em": "2026-09-23 21:00", "extracao": "2026-09-23", "colunas": list(COLUNAS),
        "docs": [[n, "A", "ALLI", "COND", 1, "2026-09-01", "2027-09-01", "2026-09-01", None, 0, 1, None, "COND X"]
                 for n in nosnums],
        "clientes": {"1": ["00000000000191", "J"]},
        "seguradoras": {"ALLI": "ALLIANZ"}, "ramos": {"COND": "CONDOMINIO"},
        "valores": {str(n): ["100.00", "10.00", "90.00", "D"] for n in nosnums},
        "negocios": {}, "fontes": {"lake": "postgresql://x:***@lake/corp_lake"},
    }


class CargaPeloLakeTests(TestCase):
    def test_remove_do_espelho_o_que_o_lake_nao_traz_mais(self):
        with patch.object(servico_lake, "extrair", return_value=_extracao(1, 2, 3)):
            call_command("carregar_lake_corp", dsn="postgresql://x:y@lake/corp_lake", verbosity=0)
        self.assertEqual(set(Producao.objects.values_list("nosnum", flat=True)), {1, 2, 3})

        # A CORP apagou o 2: o lake o marcou como ausente e ele saiu da extração.
        with patch.object(servico_lake, "extrair", return_value=_extracao(1, 3)):
            call_command("carregar_lake_corp", dsn="postgresql://x:y@lake/corp_lake", verbosity=0)
        self.assertEqual(set(Producao.objects.values_list("nosnum", flat=True)), {1, 3})

    def test_extracao_vazia_nao_apaga_o_espelho(self):
        with patch.object(servico_lake, "extrair", return_value=_extracao(1, 2)):
            call_command("carregar_lake_corp", dsn="postgresql://x:y@lake/corp_lake", verbosity=0)
        with patch.object(servico_lake, "extrair", return_value=_extracao()):
            call_command("carregar_lake_corp", dsn="postgresql://x:y@lake/corp_lake", verbosity=0)
        self.assertEqual(Producao.objects.count(), 2)
