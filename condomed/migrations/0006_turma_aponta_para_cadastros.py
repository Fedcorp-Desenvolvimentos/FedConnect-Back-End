# Passo 2 de `curso-cipa-cadastros` (RF-CIP-006/007): sai o código fixo, fica a FK.
# A 0005 criou os cadastros, semeou os dois locais e os dois instrutores e
# preencheu `local_ref`/`instrutor_ref` em toda turma; aqui os campos antigos
# saem e as FKs assumem o nome de sempre — o contrato da API continua sendo o
# `codigo` (SlugRelatedField), então nada muda para o frontend.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("condomed", "0005_cadastros_locais_e_instrutores"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="turmacipa", name="condomed_local_data_idx"),
        migrations.RemoveField(model_name="turmacipa", name="local"),
        migrations.RemoveField(model_name="turmacipa", name="instrutor"),
        migrations.RenameField(model_name="turmacipa", old_name="local_ref", new_name="local"),
        migrations.RenameField(model_name="turmacipa", old_name="instrutor_ref", new_name="instrutor"),
        migrations.AlterField(
            model_name="turmacipa",
            name="local",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="turmas",
                to="condomed.localcipa",
            ),
        ),
        migrations.AddIndex(
            model_name="turmacipa",
            index=models.Index(fields=["local", "data"], name="condomed_local_data_idx"),
        ),
    ]
