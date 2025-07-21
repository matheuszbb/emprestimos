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
from django.contrib import admin
from django.urls import path, include
from .views import IndexView, Robots_txtView, Sitemap_xmlView, CustomSignupView, ComprovanteParcelaView, ComprovanteEmprestimoView
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', IndexView.as_view(), name='index'),
    path('robots.txt', Robots_txtView.as_view(), name='robots_txt'),
    path('sitemap.xml', Sitemap_xmlView.as_view(), name='sitemap_xml'),    
    path('accounts/signup/', CustomSignupView.as_view(), name='account_signup'),
    path('accounts/', include('allauth.urls')),
    path('parcela/<int:parcela_id>/comprovante/', ComprovanteParcelaView.as_view(), name='visualizar_comprovante_parcela'),
    path('emprestimo/<int:emprestimo_id>/comprovante/', ComprovanteEmprestimoView.as_view(), name='visualizar_comprovante_emprestimo'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
