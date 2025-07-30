import re
from django.db.models import Q
from django.contrib import admin
from django.utils import timezone
from import_export import resources
from django.utils.html import format_html
from django.contrib.admin import SimpleListFilter
from import_export.admin import ImportExportModelAdmin
from django.utils.translation import gettext_lazy as _
from .forms import ParcelaAdminForm, EmprestimoAdminForm
from .models import Cliente, Contato, Emprestimo, Parcela

class AtrasoEmprestimoFilter(SimpleListFilter):
    title = _('Por Atrasado')
    parameter_name = 'atraso'

    def lookups(self, request, model_admin):
        return [
            ('com_atraso', 'Com atraso'),
            ('sem_atraso', 'Sem atraso'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'com_atraso':
            return queryset.filter(status=False, data_fim__lt=timezone.now()).distinct()
        if self.value() == 'sem_atraso':
            return queryset.exclude(status=False, data_fim__lt=timezone.now()).distinct()
        return queryset

class AtrasoParcelaFilter(SimpleListFilter):
    title = _('Por Atrasadas')
    parameter_name = 'atraso'

    def lookups(self, request, model_admin):
        return [
            ('com_atraso', 'Com atraso'),
            ('sem_atraso', 'Sem atraso'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'com_atraso':
            return queryset.filter(status=False, data_fim__lt=timezone.now()).distinct()
        if self.value() == 'sem_atraso':
            return queryset.exclude(status=False, data_fim__lt=timezone.now()).distinct()
        return queryset

# Inlines
class ContatoInline(admin.TabularInline):
    model = Contato
    extra = 1

# Recursos
class ClienteResource(resources.ModelResource):
    class Meta:
        model = Cliente

class ContatoResource(resources.ModelResource):
    class Meta:
        model = Contato

class EmprestimoResource(resources.ModelResource):
    class Meta:
        model = Emprestimo

class ParcelaResource(resources.ModelResource):
    class Meta:
        model = Parcela

@admin.register(Cliente)
class ClienteAdmin(ImportExportModelAdmin):
    resource_class = ClienteResource
    list_display = ['nome_completo', 'cpf_formatado', 'limite_f', 'limite_maximo_f', 'limite_disponivel_f', 'limite_usado_f', 'banimento']
    search_fields = ['nome', 'sobrenome', 'cpf']
    list_filter = ['banimento', 'data_cadastro']
    inlines = [ContatoInline]

    def get_search_results(self, request, queryset, search_term):
        # Limpa CPF formatado (remove ponto e traço)
        cpf_limpo = re.sub(r'[.-]', '', search_term)

        # Busca por nome/sobrenome/cpf original ou formatado
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        queryset |= self.model.objects.filter(Q(cpf=cpf_limpo))
        return queryset.distinct(), use_distinct

@admin.register(Contato)
class ContatoAdmin(ImportExportModelAdmin):
    resource_class = ContatoResource
    list_display = ['cliente', 'tipo', 'contato']
    search_fields = ['cliente__nome', 'contato']

@admin.register(Emprestimo)
class EmprestimoAdmin(ImportExportModelAdmin):
    resource_class = EmprestimoResource
    list_display = ['id', 'cliente', 'responsavel', 'valor_f', 'parcelas', 'status', 'atraso_detalhado_f', 'data_inicio', 'data_fim', 'data_pagamento']
    search_fields = ['cliente__nome', 'responsavel__username']
    list_filter = ['status', 'data_inicio', 'data_pagamento', AtrasoEmprestimoFilter]
    readonly_fields = ['tipo_comprovante', 'comprovante_link', 'comprovante_link_download', 'status']
    list_display_links = ('id', 'cliente')
    form = EmprestimoAdminForm
    fieldsets = (
        (None, {
            'fields': ('responsavel', 'cliente', 'valor', 'parcelas', 'porcentagem', 'status', 'data_inicio', 'data_fim', 'data_pagamento', 'motivo')
        }),
        ('Comprovante', {
            'fields': ('comprovante_upload', 'comprovante_link', 'tipo_comprovante', 'comprovante_link_download')
        }),
    )

    def comprovante_link(self, obj):
        if obj.comprovante:
            url = f'/emprestimo/{obj.pk}/comprovante/'
            return format_html(f'<a href="{url}" target="_blank">📎 Visualizar comprovante</a>')
        return "—"
    
    def comprovante_link_download(self, obj):
        if obj.comprovante:
            url = f'/emprestimo/{obj.pk}/comprovante/'
            return format_html(f'<a href="{url}" download>⬇️ Baixar comprovante</a>')
        return "—"

    comprovante_link.short_description = "Comprovante"
    comprovante_link_download.short_description = "Comprovante Download"

@admin.register(Parcela)
class ParcelaAdmin(ImportExportModelAdmin):
    resource_class = ParcelaResource
    list_display = ['id', 'emprestimo', 'cliente', 'valor_f', 'valor_pago_f', 'numero_parcela', 'status', 'atraso_detalhado_f', 'data_inicio', 'data_fim', 'data_pagamento']
    search_fields = ['cliente__nome', 'emprestimo__id']
    list_filter = ['status', 'data_fim', AtrasoParcelaFilter]
    readonly_fields = ['tipo_comprovante', 'comprovante_link', 'comprovante_link_download']
    list_display_links = ('id', 'emprestimo')
    actions = ['marcar_como_pago', 'marcar_como_nao_pago']
    form = ParcelaAdminForm
    fieldsets = (
        (None, {
            'fields': ('responsavel', 'cliente', 'emprestimo', 'valor', 'valor_pago', 'numero_parcela', 'status', 'data_inicio', 'data_fim', 'data_pagamento')
        }),
        ('Comprovante', {
            'fields': ('comprovante_upload', 'comprovante_link', 'tipo_comprovante', 'comprovante_link_download')
        }),
    )

    def comprovante_link_download(self, obj):
        if obj.comprovante:
            url = f'/parcela/{obj.pk}/comprovante/'
            return format_html(f'<a href="{url}" download>⬇️ Baixar comprovante</a>')
        return "—"

    def comprovante_link(self, obj):
        if obj.comprovante:
            url = f'/parcela/{obj.pk}/comprovante/'
            return format_html(f'<a href="{url}" target="_blank">📎 Visualizar comprovante</a>')
        return "—"
    
    def marcar_como_pago(self, request, queryset):
        atualizadas = queryset.update(status=True)

        # Chama o save apenas em uma parcela para disparar o signal
        ultima_parcela = queryset.last()
        if ultima_parcela:
            ultima_parcela.status = True  # redundante, mas necessário pra o save
            ultima_parcela.save()

        self.message_user(request, f"{atualizadas} parcelas marcadas como pagas ✅")
    
    def marcar_como_nao_pago(self, request, queryset):
        atualizadas = queryset.update(status=False)

        # Dispara o signal chamando save() em uma parcela
        ultima_parcela = queryset.last()
        if ultima_parcela:
            ultima_parcela.status = False  # redundante, mas necessário
            ultima_parcela.save()

        self.message_user(request, f"{atualizadas} parcelas marcadas como não pagas ❌")

    comprovante_link.short_description = "Comprovante"
    comprovante_link_download.short_description = "Comprovante Download"
    marcar_como_pago.short_description = "Marcar como pagas"
    marcar_como_nao_pago.short_description = "Marcar como não pagas"

