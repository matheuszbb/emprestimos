import json
import logging
from django.views import View
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from core.mixins import AdminRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden, HttpResponseServerError, HttpResponseNotFound, HttpResponseBadRequest

logger = logging.getLogger(__name__)

class HeartCheckView(View):
    async def get(self, request):
        return JsonResponse({"status": "OK"}, status=200)

class ChromeDevToolsStubView(View):
    async def get(self, request):
        return JsonResponse({}, status=200)

class Robots_txtView(View):
    async def get(self, request):
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

"""
Views de monitoramento do AsyncStaticMiddleware
"""



class StaticMiddlewareMixin:
    async def _get_static_middleware(self):
        """
        Busca a instância do AsyncStaticMiddleware de forma confiável.
        
        Returns:
            AsyncStaticMiddleware instance ou None
        """
        try:
            # Tenta recuperar a instancia registrada pelo middleware.
            from core.middleware import get_async_static_middleware

            middleware = get_async_static_middleware()
            if middleware is not None:
                return middleware

            # Importa o handler ASGI
            from django.core.handlers.asgi import ASGIHandler
            from importlib import import_module
            
            # Obtém o módulo ASGI configurado
            asgi_module_path = settings.ASGI_APPLICATION.rsplit('.', 1)[0]
            asgi_module = import_module(asgi_module_path)
            
            # Obtém a aplicação ASGI
            application = getattr(asgi_module, 'application', None)
            
            if application is None:
                return None
            
            # Navega pela cadeia de middlewares
            handler = application
            
            # Desempacota middlewares aninhados
            while hasattr(handler, 'application'):
                handler = handler.application
            
            # Procura pelo AsyncStaticMiddleware
            chain = getattr(handler, '_middleware_chain', None)
            if isinstance(chain, (list, tuple)):
                for middleware in chain:
                    if hasattr(middleware, 'get_cache_stats'):
                        return middleware
            else:
                current = chain
                visited = set()
                while current and id(current) not in visited:
                    visited.add(id(current))
                    if hasattr(current, 'get_cache_stats'):
                        return current
                    current = getattr(current, 'get_response', None)
            
            # Fallback: procura em load_middleware
            if hasattr(handler, 'load_middleware'):
                # Django 6.x pode ter middlewares em _middleware
                if hasattr(handler, '_middleware'):
                    for middleware_method in handler._middleware:
                        # Tenta extrair a classe do middleware
                        if hasattr(middleware_method, '__self__'):
                            middleware_instance = middleware_method.__self__
                            if hasattr(middleware_instance, 'get_cache_stats'):
                                return middleware_instance
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao buscar AsyncStaticMiddleware: {e}", exc_info=True)
        
        return None


class StaticCacheStatsView(StaticMiddlewareMixin, AdminRequiredMixin, View):
    """
    View JSON para estatísticas do cache.
    
    Endpoint: GET /_debug/static-cache/
    Auth: Requer superuser
    
    Response:
        {
            "cache_entries": 1247,
            "memory_usage_mb": 0.38,
            "hit_rate_percent": 97.24,
            ...
        }
    """
    
    async def get(self, request):
        """Retorna estatísticas do middleware."""
        
        # Busca middleware de forma confiável
        middleware = await self._get_static_middleware()
        
        if middleware and hasattr(middleware, 'get_cache_stats'):
            stats = middleware.get_cache_stats()
            
            # Adiciona contexto
            user = getattr(request, 'async_user', None)
            stats['user'] = user.username if user else 'anonymous'
            stats['timestamp'] = timezone.now().isoformat()
            
            return JsonResponse(stats, json_dumps_params={'indent': 2})
        
        return JsonResponse(
            {
                'error': 'AsyncStaticMiddleware não encontrado',
                'detail': 'Verifique se o middleware está configurado em MIDDLEWARE.',
                'settings_middleware': settings.MIDDLEWARE,
            },
            status=404
        )


class CacheDashboardView(StaticMiddlewareMixin, AdminRequiredMixin, View):
    """
    Dashboard HTML para visualizar estatísticas.
    
    Endpoint: GET /_debug/cache-dashboard/
    Auth: Requer superuser
    
    Renderiza: templates/debug/cache_dashboard.html
    """
    
    template_name = 'debug/cache_dashboard.html'
    
    async def get(self, request):
        """Renderiza dashboard."""
        
        # Busca middleware
        middleware = await self._get_static_middleware()
        
        stats = None
        if middleware and hasattr(middleware, 'get_cache_stats'):
            stats = middleware.get_cache_stats()
        
        user = getattr(request, 'async_user', None)
        context = {
            'stats': stats,
            'user': user,
            'timestamp': timezone.now(),
        }
        
        return await sync_to_async(render)(
            request,
            self.template_name,
            context
        )


class CacheControlView(StaticMiddlewareMixin, AdminRequiredMixin, View):
    """
    API de controle do cache.
    
    Endpoints:
        GET  /api/cache/control/  - Retorna stats
        POST /api/cache/control/  - Executa ações (clear_cache, reset_stats)
    
    Auth: Requer superuser
    
    POST Body:
        {
            "action": "clear_cache"  // ou "reset_stats"
        }
    """
    
    async def get(self, request):
        """Retorna estatísticas."""
        
        middleware = await self._get_static_middleware()
        
        if middleware and hasattr(middleware, 'get_cache_stats'):
            stats = middleware.get_cache_stats()
            return JsonResponse(stats)
        
        return JsonResponse({'error': 'Middleware não encontrado'}, status=404)
    
    async def post(self, request):
        """Executa ações administrativas."""
        try:
            body = json.loads(request.body) if request.body else {}
            action = body.get('action')
            
            if action == 'clear_cache':
                result = await self._clear_cache(request)
            elif action == 'reset_stats':
                result = await self._reset_stats(request)
            else:
                return JsonResponse(
                    {
                        'error': 'Ação inválida',
                        'valid_actions': ['clear_cache', 'reset_stats']
                    },
                    status=400
                )
            
            user = getattr(request, 'async_user', None)
            result['performed_by'] = user.username if user else 'anonymous'
            result['timestamp'] = timezone.now().isoformat()
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    async def _clear_cache(self, request):
        """Limpa o cache do middleware."""
        
        middleware = await self._get_static_middleware()
        
        if middleware and hasattr(middleware, '_file_cache'):
            entries_cleared = len(middleware._file_cache)
            memory_freed = middleware._cache_memory_bytes
            
            middleware._file_cache.clear()
            middleware._cache_memory_bytes = 0
            
            return {
                'success': True,
                'action': 'clear_cache',
                'entries_cleared': entries_cleared,
                'memory_freed_mb': round(memory_freed / (1024 * 1024), 2)
            }
        
        return {'success': False, 'error': 'Middleware não encontrado'}
    
    async def _reset_stats(self, request):
        """Reseta estatísticas (mantém cache)."""
        
        middleware = await self._get_static_middleware()
        
        if middleware and hasattr(middleware, '_cache_hits'):
            old_hits = middleware._cache_hits
            old_misses = middleware._cache_misses
            
            middleware._cache_hits = 0
            middleware._cache_misses = 0
            middleware._total_requests = 0
            
            return {
                'success': True,
                'action': 'reset_stats',
                'previous_hits': old_hits,
                'previous_misses': old_misses
            }
        
        return {'success': False, 'error': 'Middleware não encontrado'}






class CompleteCacheAdminView(StaticMiddlewareMixin, AdminRequiredMixin, View):
    """
    View completa de administração de cache.
    Suporta JSON API e HTML dependendo do Accept header.
    """
    
    template_name = 'debug/cache_admin.html'
    
    async def get(self, request):
        """
        GET: Retorna estatísticas
        Formato: JSON ou HTML baseado no Accept header
        """
        # Busca stats
        middleware = await self._get_static_middleware()
        
        if not middleware or not hasattr(middleware, 'get_cache_stats'):
            error_data = {
                'error': 'AsyncStaticMiddleware não encontrado',
                'detail': 'Verifique MIDDLEWARE em settings.py'
            }
            
            if self._is_json_request(request):
                return JsonResponse(error_data, status=404)
            else:
                return await sync_to_async(render)(
                    request,
                    'debug/error.html',
                    {'error': error_data},
                    status=404
                )
        
        # Adiciona metadados
        stats = middleware.get_cache_stats()
        user = getattr(request, 'async_user', None)
        stats['user'] = user.username if user else 'anonymous'
        stats['timestamp'] = timezone.now().isoformat()
        
        # Retorna JSON ou HTML
        if self._is_json_request(request):
            return JsonResponse(stats, json_dumps_params={'indent': 2})
        else:
            return await sync_to_async(render)(
                request,
                self.template_name,
                {'stats': stats}
            )
    
    async def post(self, request):
        """
        POST: Executa ações administrativas
        Actions: clear_cache, reset_stats
        """
        try:
            # Parse body
            body = json.loads(request.body) if request.body else {}
            action = body.get('action')
            
            if action == 'clear_cache':
                result = await self._clear_cache(request)
            elif action == 'reset_stats':
                result = await self._reset_stats(request)
            else:
                return JsonResponse(
                    {'error': 'Ação inválida', 'valid_actions': ['clear_cache', 'reset_stats']},
                    status=400
                )
            
            user = getattr(request, 'async_user', None)
            result['performed_by'] = user.username if user else 'anonymous'
            result['timestamp'] = timezone.now().isoformat()
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    async def _clear_cache(self, request):
        """Limpa o cache do middleware."""
        middleware = await self._get_static_middleware()
        
        if middleware and hasattr(middleware, '_file_cache'):
            entries_cleared = len(middleware._file_cache)
            memory_freed = middleware._cache_memory_bytes
            
            middleware._file_cache.clear()
            middleware._cache_memory_bytes = 0
            
            return {
                'success': True,
                'action': 'clear_cache',
                'entries_cleared': entries_cleared,
                'memory_freed_mb': round(memory_freed / (1024 * 1024), 2)
            }
        
        return {'success': False, 'error': 'Middleware não encontrado'}
    
    async def _reset_stats(self, request):
        """Reseta estatísticas (mantém cache)."""
        middleware = await self._get_static_middleware()
        
        if middleware and hasattr(middleware, '_cache_hits'):
            old_hits = middleware._cache_hits
            old_misses = middleware._cache_misses
            
            middleware._cache_hits = 0
            middleware._cache_misses = 0
            middleware._total_requests = 0
            
            return {
                'success': True,
                'action': 'reset_stats',
                'previous_hits': old_hits,
                'previous_misses': old_misses
            }
        
        return {'success': False, 'error': 'Middleware não encontrado'}
    
    def _is_json_request(self, request):
        """Detecta se requisição espera JSON."""
        accept = request.META.get('HTTP_ACCEPT', '')
        content_type = request.META.get('CONTENT_TYPE', '')
        
        return (
            'application/json' in accept or
            'application/json' in content_type or
            request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
        )