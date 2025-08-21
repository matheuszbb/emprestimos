from django.views import View
from django.contrib import messages
from .models import Parcela, Emprestimo
from datetime import datetime, timedelta
from allauth.account.views import SignupView
from django.utils.safestring import mark_safe
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

MIME_EXTENSIONS = {
    'application/pdf': 'pdf',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/svg+xml': 'svg',
    'image/gif': 'gif',
}

class ComprovanteParcelaView(LoginRequiredMixin, UserPassesTestMixin, View):
    parcela = None

    def test_func(self):
        parcela_id = self.kwargs.get("parcela_id")
        self.parcela = get_object_or_404(Parcela, pk=parcela_id)
        return self.request.user.is_staff or self.parcela.responsavel == self.request.user
    
    def handle_no_permission(self):
        raise Http404

    def get(self, request, parcela_id):
        if self.parcela.comprovante:
            extensao = MIME_EXTENSIONS.get(self.parcela.tipo_comprovante, 'bin')
            response = HttpResponse(self.parcela.comprovante, content_type=self.parcela.tipo_comprovante)
            data_formatada = self.parcela.data_pagamento.strftime('%Y-%m-%d') if self.parcela.data_pagamento else 'sem-data'
            nome = f"comprovante_{parcela_id}_{self.parcela.emprestimo.id}_{self.parcela.cliente.id}_{self.parcela.cliente.nome_completo}_{data_formatada}.{extensao}".replace(" ","")
            response['Content-Disposition'] = f'inline; filename="{nome}"'
            return response
        else: raise Http404

class ComprovanteEmprestimoView(LoginRequiredMixin, UserPassesTestMixin, View):
    emprestimo = None

    def test_func(self):
        emprestimo_id = self.kwargs.get("emprestimo_id")
        self.emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id)
        return self.request.user.is_staff or self.emprestimo.responsavel == self.request.user
    
    def handle_no_permission(self):
        raise Http404

    def get(self, request, emprestimo_id):
        if self.emprestimo.comprovante:
            extensao = MIME_EXTENSIONS.get(self.emprestimo.tipo_comprovante, 'bin')
            response = HttpResponse(self.emprestimo.comprovante, content_type=self.emprestimo.tipo_comprovante)
            data_formatada = self.emprestimo.data_inicio.strftime('%Y-%m-%d') if self.emprestimo.data_inicio else 'sem-data'
            nome = f"comprovante_{emprestimo_id}_{self.emprestimo.cliente.id}_{self.emprestimo.cliente.nome_completo}_{data_formatada}.{extensao}".replace(" ","")
            response['Content-Disposition'] = f'inline; filename="{nome}"'
            return response
        else: raise Http404

class Robots_txtView(View):
    def get(self, request):
        robots_txt_content = f"""\
User-Agent: *
Allow: /
Sitemap: {request.build_absolute_uri('/sitemap.xml')}
"""
        return HttpResponse(robots_txt_content, content_type="text/plain", status=200)

class Sitemap_xmlView(View):
    def get(self, request):
        site_url = request.build_absolute_uri('/')[:-1]  # Remove a última barra se houver
        sitemap_xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url>
    <loc>{site_url}</loc>
</url>
</urlset>
"""
        return HttpResponse(sitemap_xml_content, content_type="application/xml", status=200)
    
class IndexView(View):
    def get(self, request):
        return redirect('admin:index')
        return render(request, 'core/index.html')

class CustomSignupView(SignupView):
    def dispatch(self, request, *args, **kwargs):
        return redirect('index')

