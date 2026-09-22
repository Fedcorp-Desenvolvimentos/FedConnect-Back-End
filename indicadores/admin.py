from django.contrib import admin

from indicadores.models import CargaCorp, Cliente, Documento, DocumentoNegocio, Producao, Ramo, Seguradora


@admin.register(CargaCorp)
class CargaCorpAdmin(admin.ModelAdmin):
    list_display = ("id", "origem", "extraido_em", "iniciada_em", "concluida_em", "sucesso", "duracao_ms")
    list_filter = ("origem", "sucesso")
    readonly_fields = ("iniciada_em",)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "pessoa")
    search_fields = ("codigo", "nome")


@admin.register(Ramo)
class RamoAdmin(admin.ModelAdmin):
    list_display = ("abreviatura", "nome")


@admin.register(Seguradora)
class SeguradoraAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome")


@admin.register(Producao)
class ProducaoAdmin(admin.ModelAdmin):
    list_display = (
        "nosnum", "tipdoc", "seguradora", "ramo", "cliente_nome", "datemi", "inivig", "fimvig", "cancelado", "renovacao",
    )
    list_filter = ("tipdoc", "cancelado", "renovacao", "seguradora")
    search_fields = ("nosnum", "cliente_nome")
    raw_id_fields = ("cliente", "carga")
    date_hierarchy = "datemi"


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("producao", "pretot", "val_c", "preliq", "fonte")
    raw_id_fields = ("producao",)


@admin.register(DocumentoNegocio)
class DocumentoNegocioAdmin(admin.ModelAdmin):
    list_display = ("producao", "codigo_negocio", "datinc_negocio")
    raw_id_fields = ("producao",)
