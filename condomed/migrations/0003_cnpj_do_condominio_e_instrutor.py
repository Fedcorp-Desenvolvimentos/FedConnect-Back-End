"""CNPJ do condomínio na inscrição e instrutor na turma.

Os dois vêm do certificado em uso (ANALISE_CERTIFICADO_CIPA.md): ele cita o
condomínio com CNPJ e leva nome, registro MTE e assinatura do instrutor.

Aditiva e sem risco: os dois campos nascem em branco. CNPJ é opcional para
inscrever e obrigatório para emitir certificado; instrutor é opcional na
criação da turma e obrigatório para emitir — decisões do dono em 2026-09-04.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("condomed", "0002_vinculo_no_inscrito"),
    ]

    operations = [
        migrations.AddField(
            model_name="inscricaocipa",
            name="condominio_cnpj",
            field=models.CharField(blank=True, max_length=14),
        ),
        migrations.AddField(
            model_name="turmacipa",
            name="instrutor",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FELIPE", "Felipe Barboza de Oliveira"),
                    ("VINICIUS", "Vinicius dos Santos Pinto"),
                ],
                max_length=20,
            ),
        ),
    ]
