import re
from django.db.models import Q
from django.contrib import admin
from django.utils import timezone
from import_export import resources
from django.utils.html import format_html
from django.contrib.admin import SimpleListFilter
from import_export.admin import ImportExportModelAdmin
from django.utils.translation import gettext_lazy as _
from utils.formatar_dinheiro import formatar_dinheiro
from .forms import ParcelaAdminForm, EmprestimoAdminForm
from .models import Cliente, Contato, Emprestimo, Parcela, ChatId, BotToken, Notificacao

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
    readonly_fields = ['tipo_comprovante', 'comprovante_link', 'comprovante_link_download', 'status', 'detalhes_emprestimo', 'parcelas_vinculadas', 'status_detalhado', 'dias_vencimento', 'dias_atrasado']
    list_display_links = ('id', 'cliente')
    form = EmprestimoAdminForm
    fieldsets = (
        (None, {
            'fields': ('responsavel', 'cliente', 'valor', 'parcelas', 'porcentagem', 'status', 'data_inicio', 'data_fim', 'data_pagamento', 'motivo')
        }),
        ('Detalhes', {
            'fields': ('detalhes_emprestimo', 'parcelas_vinculadas', 'status_detalhado', 'dias_vencimento', 'dias_atrasado'),
            'classes': ('collapse',),
            'description': 'Informações detalhadas sobre o empréstimo e suas parcelas'
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

    # Métodos para o fieldset Detalhes
    def detalhes_emprestimo(self, obj):
        """Exibe informações gerais do empréstimo, incluindo detalhes do cliente, datas e responsável"""
        if not obj:
            return "—"
        cliente_nome = obj.cliente.nome_completo if hasattr(obj.cliente, 'nome_completo') else str(obj.cliente)
        responsavel = obj.responsavel.get_full_name() if obj.responsavel and hasattr(obj.responsavel, 'get_full_name') and obj.responsavel.get_full_name() else (obj.responsavel.username if obj.responsavel else '—')
        motivo = obj.motivo if hasattr(obj, 'motivo') and obj.motivo else '—'
        html = f"""
        <div style='background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007bff;'>
            <h4 style='margin: 0 0 10px 0; color: #007bff;'>📊 Resumo do Empréstimo</h4>
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; color: black;'>
                <div><strong>ID do Empréstimo:</strong> {obj.id}</div>
                <div><strong>Cliente:</strong> {cliente_nome}</div>
                <div><strong>Responsável:</strong> {responsavel}</div>
                <div><strong>Valor:</strong> {formatar_dinheiro(obj.valor)}</div>
                <div><strong>Parcelas:</strong> {obj.parcelas}</div>
                <div><strong>Porcentagem:</strong> {obj.porcentagem}%</div>
                <div><strong>Lucro:</strong> {formatar_dinheiro(obj.lucro())}</div>
                <div><strong>Recebimento Futuro:</strong> {formatar_dinheiro(obj.recebimento_futuro())}</div>
                <div><strong>Recebimento Atual:</strong> {formatar_dinheiro(obj.recebimento_atual())}</div>
                <div><strong>Data de Início:</strong> {obj.data_inicio.strftime('%d/%m/%Y') if obj.data_inicio else '—'}</div>
                <div><strong>Data de Vencimento:</strong> {obj.data_fim.strftime('%d/%m/%Y') if obj.data_fim else '—'}</div>
                <div><strong>Data de Pagamento:</strong> {obj.data_pagamento.strftime('%d/%m/%Y') if obj.data_pagamento else '—'}</div>
                <div style='grid-column: 1 / -1;'><strong>Motivo:</strong> {motivo}</div>
            </div>
        </div>
        """
        return format_html(html)
    
    def parcelas_vinculadas(self, obj):
        """Exibe lista completa e ordenada das parcelas vinculadas, sem scroll"""
        if not obj:
            return "—"

        # Ordena corretamente por número da parcela (convertendo para int)
        parcelas = sorted(obj.parcela_set.all(), key=lambda p: int(p.numero_parcela))
        if not parcelas:
            return "Nenhuma parcela criada"

        html = '<div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">'
        html += '<h4 style="margin: 0 0 10px 0; color: #856404;">📋 Parcelas Vinculadas</h4>'
        html += '<div style="max-height: 340px; overflow-y: auto;">'

        for parcela in parcelas:
            status_color = "#28a745" if parcela.status else "#dc3545"
            status_icon = "✅" if parcela.status else "❌"
            status_text = "Paga" if parcela.status else "Pendente"
            admin_url = f'/admin/core/parcela/{parcela.pk}/change/'
            html += f"""
            <div style="border: 1px solid #dee2e6; padding: 10px; margin: 5px 0; border-radius: 5px; background: white;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="color: black;">
                        <strong>Parcela {parcela.numero_parcela}</strong> - {parcela.valor_f()}
                        <br><small>Vencimento: {timezone.localtime(parcela.data_fim).strftime('%d/%m/%Y')}</small>
                    </div>
                    <div style="color: {status_color}; font-weight: bold;">
                        {status_icon} {status_text}
                    </div>
                </div>
                <div style="margin-top: 5px;">
                    <a href="{admin_url}" target="_blank" style="background: #007bff; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; font-size: 12px;">
                        🔗 Ver Parcela
                    </a>
                </div>
            </div>
            """

        html += '</div></div>'
        return format_html(html)
    
    def status_detalhado(self, obj):
        """Exibe status detalhado do empréstimo"""
        if not obj:
            return "—"
        
        if obj.status:
            status_html = '<span style="color: #28a745; font-weight: bold;">✅ CONCLUÍDO</span>'
        else:
            if obj.atraso():
                status_html = '<span style="color: #dc3545; font-weight: bold;">🚨 EM ATRASO</span>'
            else:
                status_html = '<span style="color: #ffc107; font-weight: bold;">⏳ EM ANDAMENTO</span>'
        
        html = f"""
        <div style="background: #e2e3e5; padding: 15px; border-radius: 8px; border-left: 4px solid #6c757d;">
            <h4 style="margin: 0 0 10px 0; color: #495057;">📈 Status do Empréstimo</h4>
            <div style="font-size: 16px; text-align: center; padding: 10px;">
                {status_html}
            </div>
        </div>
        """
        return format_html(html)
    
    def dias_vencimento(self, obj):
        """Exibe dias até o vencimento do empréstimo e da próxima parcela não paga"""
        if not obj or obj.status:
            return "—"

        hoje = timezone.now().date()
        vencimento_emprestimo = obj.data_fim.date()
        dias_restantes_emprestimo = (vencimento_emprestimo - hoje).days

        # Bloco do empréstimo
        if dias_restantes_emprestimo > 0:
            color = "#28a745"  # Verde
            icon = "⏰"
            texto = f"Faltam {dias_restantes_emprestimo} dias para o vencimento do empréstimo"
        elif dias_restantes_emprestimo == 0:
            color = "#ffc107"  # Amarelo
            icon = "⚠️"
            texto = "O empréstimo vence hoje!"
        else:
            color = "#dc3545"  # Vermelho
            icon = "🚨"
            texto = f"Empréstimo vencido há {abs(dias_restantes_emprestimo)} dias"

        html = f"""
        <div style='background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid {color}; margin-bottom: 10px;'>
            <h4 style='margin: 0 0 10px 0; color: {color};'>{icon} Vencimento do Empréstimo</h4>
            <div style='font-size: 16px; text-align: center; padding: 10px; color: {color}; font-weight: bold;'>
                {texto}
            </div>
            <div style='text-align: center; font-size: 14px; color: #6c757d;'>
                Data de vencimento: {obj.data_fim.strftime('%d/%m/%Y')}
            </div>
        </div>
        """

        # Bloco da próxima parcela não paga
        proxima_parcela = obj.parcela_set.filter(status=False, data_fim__gte=timezone.now()).order_by('data_fim').first()
        if proxima_parcela:
            vencimento_parcela = proxima_parcela.data_fim.date()
            dias_restantes_parcela = (vencimento_parcela - hoje).days
            valor_parcela = formatar_dinheiro(proxima_parcela.valor)
            admin_url = f"/admin/core/parcela/{proxima_parcela.pk}/change/"
            valor_link = f"<a href='{admin_url}' target='_blank' style='color: #007bff; text-decoration: underline; font-weight: bold;'>parcela ({valor_parcela})</a>"
            if dias_restantes_parcela > 0:
                color_p = "#17a2b8"  # Azul
                icon_p = "📅"
                texto_p = f"Faltam {dias_restantes_parcela} dias para o vencimento da próxima {valor_link}"
            elif dias_restantes_parcela == 0:
                color_p = "#ffc107"
                icon_p = "⚠️"
                texto_p = f"A próxima {valor_link} vence hoje!"
            else:
                color_p = "#dc3545"
                icon_p = "🚨"
                texto_p = f"Próxima {valor_link} vencida há {abs(dias_restantes_parcela)} dias"

            html += f"""
            <div style='background: #e9f7fa; padding: 15px; border-radius: 8px; border-left: 4px solid {color_p}; margin-bottom: 0;'>
                <h4 style='margin: 0 0 10px 0; color: {color_p};'>{icon_p} Vencimento da Próxima Parcela</h4>
                <div style='font-size: 16px; text-align: center; padding: 10px; color: {color_p}; font-weight: bold;'>
                    {texto_p}
                </div>
                <div style='text-align: center; font-size: 14px; color: #6c757d;'>
                    Data de vencimento: {proxima_parcela.data_fim.strftime('%d/%m/%Y')}
                </div>
            </div>
            """

        return format_html(html)
    
    def dias_atrasado(self, obj):
        """Exibe dias de atraso"""
        if not obj or obj.status:
            return "—"
        
        if not obj.atraso():
            html = """
            <div style="background: #d4edda; padding: 15px; border-radius: 8px; border-left: 4px solid #28a745;">
                <h4 style="margin: 0 0 10px 0; color: #155724;">✅ Em Dia</h4>
                <div style="font-size: 16px; text-align: center; padding: 10px; color: #155724; font-weight: bold;">
                    Empréstimo em dia!
                </div>
            </div>
            """
        else:
            dias_atraso = obj.dias_atraso()
            html = f"""
            <div style="background: #f8d7da; padding: 15px; border-radius: 8px; border-left: 4px solid #dc3545;">
                <h4 style="margin: 0 0 10px 0; color: #721c24;">🚨 Atraso</h4>
                <div style="font-size: 16px; text-align: center; padding: 10px; color: #721c24; font-weight: bold;">
                    {dias_atraso} dia{'s' if dias_atraso > 1 else ''} de atraso
                </div>
                <div style="text-align: center; font-size: 14px; color: #721c24;">
                    Vencimento: {obj.data_fim.strftime('%d/%m/%Y')}
                </div>
            </div>
            """
        
        return format_html(html)
    
    # Configurações dos campos
    detalhes_emprestimo.short_description = "📊 Resumo do Empréstimo"
    parcelas_vinculadas.short_description = "📋 Parcelas Vinculadas"
    status_detalhado.short_description = "📈 Status Detalhado"
    dias_vencimento.short_description = "⏰ Vencimento"
    dias_atrasado.short_description = "🚨 Atraso"

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

@admin.register(ChatId)
class ChatIdAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome', 'dono', 'chat_id', 'plataforma']
    search_fields = ['nome', 'chat_id', 'dono__username']
    list_filter = ['plataforma']

@admin.register(BotToken)
class BotTokenAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome', 'dono', 'token', 'plataforma']
    search_fields = ['nome', 'token', 'dono__username']
    list_filter = ['plataforma']

@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'dono', 'token', 'chat_id', 'plataforma']
    search_fields = ['dono__username', 'token__nome', 'chat_id__nome']
    list_filter = ['plataforma']