"""Administradora e condomínio saem da turma e entram na inscrição (ADR-0004).

Uma turma é um dia de curso em um local e recebe funcionários de várias
administradoras e vários condomínios — o vínculo é do participante, não da
turma.

Destrutiva por decisão: os três campos da turma são removidos sem cópia,
porque não há turma cadastrada (a tela nunca ficou acessível: nenhum usuário
tinha o nível `condomed`). Reverter recria as colunas vazias, não os valores.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("condomed", "0001_initial"),
    ]

    operations = [
        # --- a inscrição ganha o vínculo (obrigatório, INV-CIP-004) ---
        migrations.AddField(
            model_name="inscricaocipa",
            name="administradora_codigo",
            field=models.CharField(default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="inscricaocipa",
            name="administradora_nome",
            field=models.CharField(blank=True, default="", max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="inscricaocipa",
            name="condominio_nome",
            field=models.CharField(default="", max_length=150),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name="inscricaocipa",
            options={
                "ordering": ["condominio_nome", "nome"],
                "verbose_name": "inscrição CIPA",
                "verbose_name_plural": "inscrições CIPA",
            },
        ),
        migrations.AddIndex(
            model_name="inscricaocipa",
            index=models.Index(
                fields=["administradora_codigo"], name="condomed_insc_adm_idx"
            ),
        ),
        # --- a turma perde o cliente ---
        migrations.RemoveField(
            model_name="turmacipa",
            name="administradora_codigo",
        ),
        migrations.RemoveField(
            model_name="turmacipa",
            name="administradora_nome",
        ),
        migrations.RemoveField(
            model_name="turmacipa",
            name="condominio_nome",
        ),
    ]
