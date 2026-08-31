from django.contrib import admin

from .models import InscricaoCipa, TurmaCipa


@admin.register(TurmaCipa)
class TurmaCipaAdmin(admin.ModelAdmin):
    list_display = ("data", "local", "condominio_nome", "status")
    list_filter = ("local", "status")


@admin.register(InscricaoCipa)
class InscricaoCipaAdmin(admin.ModelAdmin):
    list_display = ("nome", "turma", "funcao")
