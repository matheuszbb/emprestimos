"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import JavaScriptCatalog
from .views.corefilesviews import (
    IndexView, CustomSignupView, ComprovanteParcelaView, ComprovanteEmprestimoView
)
from .views.simpleviews import (
    Robots_txtView, Sitemap_xmlView, HeartCheckView, ChromeDevToolsStubView,
)

# 🌍 Rotas que não precisam de tradução (como arquivos técnicos e APIs)
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('health/', HeartCheckView.as_view(), name='health_check'),
    path('robots.txt', Robots_txtView.as_view(), name='robots_txt'),
    path('sitemap.xml', Sitemap_xmlView.as_view(), name='sitemap_xml'),    
    path(".well-known/appspecific/com.chrome.devtools.json", ChromeDevToolsStubView.as_view(), name="chrome-devtools-stub"),

    path('emprestimosadmindjango/', admin.site.urls),
    path('accounts/signup/', CustomSignupView.as_view(), name='account_signup'),
    path('accounts/', include('allauth.urls')),
    path('parcela/<int:parcela_id>/comprovante/', ComprovanteParcelaView.as_view(), name='visualizar_comprovante_parcela'),
    path('emprestimo/<int:emprestimo_id>/comprovante/', ComprovanteEmprestimoView.as_view(), name='visualizar_comprovante_emprestimo'),
    # Rota para troca de idioma
    path('i18n/', include('django.conf.urls.i18n')),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
]

# 🌐 Rotas que devem ser traduzíveis (prefixadas com /pt-br/, /en/, etc.)
urlpatterns += i18n_patterns(
    path('', IndexView.as_view(), name='index'),
    prefix_default_language=True  # ❗️Evita prefixo para o idioma padrão (pt-br)
)

# Arquivos estáticos e de mídia
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
