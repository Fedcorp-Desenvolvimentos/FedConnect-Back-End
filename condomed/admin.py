from django.contrib import admin

from .models import InscricaoCipa, TurmaCipa


@admin.register(TurmaCipa)
class TurmaCipaAdmin(admin.ModelAdmin):
    list_display = ("data", "local", "total_inscritos", "status")
    list_filter = ("local", "status")


@admin.register(InscricaoCipa)
class InscricaoCipaAdmin(admin.ModelAdmin):
    list_display = ("nome", "condominio_nome", "administradora_nome", "turma", "funcao")
    list_filter = ("administradora_nome",)
    search_fields = ("nome", "cpf", "condominio_nome")
