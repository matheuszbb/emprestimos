"""
AsyncStaticMiddleware - Ultra-performático para Django 6.x
Serve arquivos estáticos de forma assíncrona com suporte a gzip pré-compactado.

Otimizações:
- Cache inteligente de metadados com limite de memória
- Streaming assíncrono com chunks otimizados
- Suporte a ETag e Last-Modified (304 responses)
- Detecção automática de arquivos .gz (WhiteNoise compatible)
"""

# ============================================================================
# IMPORTS
# ============================================================================
import os
import sys
import logging
import aiofiles
import mimetypes
from django.conf import settings
from typing import Optional, Tuple
from django.utils._os import safe_join
from django.utils.http import http_date
from email.utils import parsedate_to_datetime
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.http import StreamingHttpResponse, HttpResponseNotModified, HttpResponseNotFound


# ============================================================================
# LOGGER
# ============================================================================
logger = logging.getLogger("django.request")

# Exposes the active AsyncStaticMiddleware instance for diagnostics.
_ASYNC_STATIC_MIDDLEWARE = None


def get_async_static_middleware():
    return _ASYNC_STATIC_MIDDLEWARE


# ============================================================================
# MIDDLEWARE
# ============================================================================

class AsyncStaticMiddleware:
    """
    Middleware assíncrono para servir arquivos estáticos em Django 6.x.
    
    Features:
    - 100% assíncrono (ASGI nativo)
    - Cache inteligente de metadados com limite de memória
    - Suporte automático a gzip (arquivos .gz)
    - Validação HTTP (ETag + Last-Modified)
    - Streaming eficiente com aiofiles
    - Headers otimizados para CDN
    
    Configuração via settings.STATIC_MIDDLEWARE (Django 4.2+ pattern).
    
    Compatível com:
    - Django 6.0+
    - WhiteNoise (para compressão)
    - Uvicorn/Hypercorn/Daphne
    """
    
    # Declaração de capacidades Django 6.x
    async_capable = True
    sync_capable = False
    
    def __init__(self, get_response):
        """Inicializa o middleware com validações."""
        self.get_response = get_response

        global _ASYNC_STATIC_MIDDLEWARE
        _ASYNC_STATIC_MIDDLEWARE = self
        
        # Marca como coroutine para Django 6.x
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
        
        # Carrega configuração de settings.py
        self._load_config()
        
        # Cache de metadados de arquivos
        self._file_cache = {}
        self._cache_memory_bytes = 0
        
        # Estatísticas de performance
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_requests = 0
        
        # Validação de configuração
        self._validate_settings()
        
        # Log de inicialização
        logger.info(
            f"[AsyncStatic] Inicializado - "
            f"Cache: {self.max_cache_memory_mb}MB / {self.max_cache_entries} entradas | "
            f"Chunk: {self.chunk_size // 1024}KB"
        )
    
    def _load_config(self):
        """
        Carrega configuração de settings.STATIC_MIDDLEWARE.
        Usa valores padrão se não configurado.
        
        Padrão Django 6.x: Configuração modular via dicionários (como STORAGES)
        """
        # Obtém config de settings ou usa defaults
        config = getattr(settings, 'STATIC_MIDDLEWARE', {})
        storage_config = config.get('storage', {})
        cache_config = config.get('cache', {})
        
        # Storage config
        self.chunk_size = storage_config.get('CHUNK_SIZE', 524288)
        self.max_cache_memory_mb = storage_config.get('MAX_CACHE_MEMORY_MB', 5)
        self.avg_cache_entry_size = storage_config.get('AVG_CACHE_ENTRY_SIZE', 320)
        self.debug_logging = storage_config.get('DEBUG_LOGGING', False)
        
        # Calcula max entries
        self.max_cache_entries = int(
            (self.max_cache_memory_mb * 1024 * 1024) / self.avg_cache_entry_size
        )
        
        # Cache control config
        self.cache_control = cache_config.get(
            'CONTROL',
            'public, max-age=31536000, immutable'
        )
        self.cors_origin_fonts = cache_config.get('CORS_ORIGIN', '*')
    
    def _validate_settings(self):
        """Valida configurações necessárias do Django."""
        if not hasattr(settings, 'STATIC_URL'):
            raise ImproperlyConfigured(
                "AsyncStaticMiddleware requer STATIC_URL definido em settings.py"
            )
        
        if not hasattr(settings, 'STATIC_ROOT') or not settings.STATIC_ROOT:
            raise ImproperlyConfigured(
                "AsyncStaticMiddleware requer STATIC_ROOT definido em settings.py"
            )
        
        # Valida que STATIC_ROOT existe
        static_root = str(settings.STATIC_ROOT)
        if not os.path.exists(static_root):
            logger.warning(
                f"[AsyncStatic] STATIC_ROOT não existe: {static_root}. "
                "Execute 'python manage.py collectstatic' primeiro."
            )
    
    async def __call__(self, request):
        """
        Entry point assíncrono do middleware.
        Processa requests de arquivos estáticos de forma otimizada.
        """
        self._total_requests += 1
        
        # Early return se não for arquivo estático
        static_url = settings.STATIC_URL
        # Garante que static_url começa com /
        if not static_url.startswith('/'):
            static_url = '/' + static_url
        
        if not request.path.startswith(static_url):
            return await self.get_response(request)
        
        # Extrai path relativo
        rel_path = request.path[len(static_url):].lstrip('/')
        
        # Proteção contra path traversal
        try:
            full_path = safe_join(str(settings.STATIC_ROOT), rel_path)
        except (ValueError, SuspiciousFileOperation) as e:
            logger.warning(f"[AsyncStatic] Path suspeito bloqueado: {request.path} - {e}")
            return HttpResponseNotFound()
        
        # Busca arquivo (com cache inteligente)
        file_info = await self._get_file_info(full_path, request)
        
        if file_info is None:
            # Arquivo não encontrado - retorna 404
            return HttpResponseNotFound()
        
        serve_path, is_compressed, stat_result = file_info
        
        # Validação de cache HTTP (retorna 304 se não modificado)
        if self._should_return_304(request, stat_result):
            response = HttpResponseNotModified()
            response["ETag"] = self._generate_etag(stat_result)
            return response
        
        # Cria response com streaming assíncrono
        response = StreamingHttpResponse(
            self._async_file_iterator(serve_path),
            content_type=self._get_content_type(full_path)
        )
        
        # Configura headers de cache e performance
        self._set_response_headers(response, stat_result, is_compressed, rel_path)
        
        if self.debug_logging:
            logger.debug(
                f"[AsyncStatic] Servindo: {rel_path} | "
                f"Gzip: {is_compressed} | "
                f"Tamanho: {stat_result.st_size // 1024}KB"
            )
        
        return response
    
    async def _get_file_info(
        self, 
        full_path: str, 
        request
    ) -> Optional[Tuple[str, bool, os.stat_result]]:
        """
        Busca informações do arquivo com cache otimizado.
        
        Retorna:
            Tupla (caminho_arquivo, is_gzip, stat_result) ou None se não encontrado
        
        Cache Strategy:
            - Cache hit: Valida mtime e retorna dados cacheados
            - Cache miss: Busca no disco, cacheia se dentro do limite de memória
            - Eviction: FIFO quando limite de memória é atingido
        """
        cache_key = full_path
        
        # ===== CACHE HIT =====
        if cache_key in self._file_cache:
            self._cache_hits += 1
            cached_path, cached_compressed, cached_stat = self._file_cache[cache_key]
            
            # Revalidação rápida: verifica se arquivo foi modificado
            try:
                current_mtime = os.path.getmtime(cached_path)
                
                # Tolerância de 10ms para sistemas de arquivos
                if abs(current_mtime - cached_stat.st_mtime) < 0.01:
                    return self._file_cache[cache_key]
                
                # Arquivo modificado - remove do cache
                self._evict_from_cache(cache_key)
                
            except OSError:
                # Arquivo removido - limpa cache
                self._evict_from_cache(cache_key)
                return None
        
        # ===== CACHE MISS =====
        self._cache_misses += 1
        
        # Detecta suporte a gzip do cliente
        accept_encoding = request.headers.get("Accept-Encoding", "")
        supports_gzip = "gzip" in accept_encoding.lower()
        
        serve_path = full_path
        is_compressed = False
        
        # Prioriza arquivo .gz se disponível e cliente suporta
        if supports_gzip:
            gz_path = full_path + ".gz"
            try:
                if os.path.isfile(gz_path):
                    serve_path = gz_path
                    is_compressed = True
                    
                    if self.debug_logging:
                        logger.debug(f"[AsyncStatic] ✅ Gzip encontrado: {gz_path}")
            except OSError:
                pass
        
        # Verifica se arquivo existe e obtém metadados
        try:
            stat_result = os.stat(serve_path)
            
            # Garante que é arquivo regular (não diretório)
            if not os.path.isfile(serve_path):
                return None
                
        except (OSError, IOError):
            if self.debug_logging:
                logger.debug(f"[AsyncStatic] ❌ Não encontrado: {serve_path}")
            return None
        
        # ===== ATUALIZA CACHE =====
        file_info = (serve_path, is_compressed, stat_result)
        self._add_to_cache(cache_key, file_info)
        
        return file_info
    
    def _add_to_cache(self, cache_key: str, file_info: Tuple):
        """
        Adiciona entrada ao cache respeitando limite de memória.
        Implementa eviction FIFO quando limite é atingido.
        """
        # Calcula tamanho da nova entrada
        entry_size = (
            sys.getsizeof(cache_key) +
            sys.getsizeof(file_info) +
            sys.getsizeof(file_info[0]) +  # serve_path
            sys.getsizeof(file_info[2])    # stat_result
        )
        
        max_bytes = self.max_cache_memory_mb * 1024 * 1024
        
        # Eviction loop: remove entradas antigas até ter espaço
        while (
            self._cache_memory_bytes + entry_size > max_bytes and 
            len(self._file_cache) > 0
        ):
            # Remove entrada mais antiga (FIFO)
            oldest_key = next(iter(self._file_cache))
            self._evict_from_cache(oldest_key)
        
        # Proteção adicional: limite absoluto de entradas
        if len(self._file_cache) >= self.max_cache_entries:
            oldest_key = next(iter(self._file_cache))
            self._evict_from_cache(oldest_key)
        
        # Adiciona ao cache
        self._file_cache[cache_key] = file_info
        self._cache_memory_bytes += entry_size
    
    def _evict_from_cache(self, cache_key: str):
        """Remove entrada do cache e atualiza contador de memória."""
        if cache_key in self._file_cache:
            removed = self._file_cache.pop(cache_key)
            # Estima tamanho removido (usa média para performance)
            self._cache_memory_bytes = max(
                0, 
                self._cache_memory_bytes - self.avg_cache_entry_size
            )
    
    async def _async_file_iterator(self, file_path: str):
        """
        Generator assíncrono otimizado para streaming de arquivos.
        
        Usa aiofiles para I/O não-bloqueante, permitindo que o event loop
        processe outras requests enquanto lê do disco.
        
        Args:
            file_path: Caminho absoluto do arquivo a ser servido
            
        Yields:
            Chunks de CHUNK_SIZE bytes configurado
        """
        try:
            async with aiofiles.open(file_path, mode='rb') as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
        except Exception as e:
            logger.error(
                f"[AsyncStatic] Erro ao ler arquivo {file_path}: {e}", 
                exc_info=True
            )
            raise
    
    def _should_return_304(self, request, stat_result: os.stat_result) -> bool:
        """
        Verifica se deve retornar 304 Not Modified.
        
        Implementa validação conforme RFC 7232:
        - ETag (strong validation)
        - Last-Modified (weak validation)
        
        Args:
            request: HttpRequest do Django
            stat_result: Metadados do arquivo (os.stat_result)
            
        Returns:
            True se deve retornar 304, False caso contrário
        """
        # ===== VALIDAÇÃO POR ETAG (preferencial) =====
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match:
            current_etag = self._generate_etag(stat_result)
            
            # Suporta múltiplos ETags (separados por vírgula)
            client_etags = [tag.strip().strip('"') for tag in if_none_match.split(',')]
            current_etag_clean = current_etag.strip('"')
            
            if current_etag_clean in client_etags:
                return True
        
        # ===== VALIDAÇÃO POR LAST-MODIFIED =====
        if_modified_since = request.headers.get("If-Modified-Since")
        if if_modified_since:
            try:
                client_time = parsedate_to_datetime(if_modified_since)
                file_mtime = int(stat_result.st_mtime)
                client_mtime = int(client_time.timestamp())
                
                # Retorna 304 se arquivo não foi modificado
                if file_mtime <= client_mtime:
                    return True
                    
            except (TypeError, ValueError, OverflowError, AttributeError):
                # Data inválida - ignora validação
                pass
        
        return False
    
    def _generate_etag(self, stat_result: os.stat_result) -> str:
        """
        Gera ETag strong conforme RFC 7232.
        
        Formato: "mtime_hex-size_hex"
        Usa hexadecimal para compactar e milliseconds para precisão.
        
        Args:
            stat_result: Metadados do arquivo
            
        Returns:
            String ETag (ex: "18f3a2b-1a4c")
        """
        mtime_ms = int(stat_result.st_mtime * 1000)
        size = stat_result.st_size
        
        return f'"{mtime_ms:x}-{size:x}"'
    
    def _get_content_type(self, file_path: str) -> str:
        """
        Detecta Content-Type com fallbacks para tipos modernos.
        
        Args:
            file_path: Caminho do arquivo (usado para detectar extensão)
            
        Returns:
            MIME type string
        """
        # Tenta detecção padrão do Python
        content_type, _ = mimetypes.guess_type(file_path)
        
        if content_type:
            return content_type
        
        # Fallbacks para extensões modernas
        ext = os.path.splitext(file_path)[1].lower()
        
        mime_map = {
            # JavaScript
            '.js': 'application/javascript; charset=utf-8',
            '.mjs': 'application/javascript; charset=utf-8',
            '.cjs': 'application/javascript; charset=utf-8',
            
            # Stylesheets
            '.css': 'text/css; charset=utf-8',
            '.scss': 'text/x-scss; charset=utf-8',
            '.sass': 'text/x-sass; charset=utf-8',
            
            # Data
            '.json': 'application/json',
            '.jsonld': 'application/ld+json',
            '.xml': 'application/xml',
            
            # Images
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.avif': 'image/avif',
            '.ico': 'image/x-icon',
            
            # Fonts
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.otf': 'font/otf',
            '.eot': 'application/vnd.ms-fontobject',
            
            # Source maps
            '.map': 'application/json',
            
            # Manifests
            '.webmanifest': 'application/manifest+json',
        }
        
        return mime_map.get(ext, 'application/octet-stream')
    
    def _set_response_headers(
        self,
        response,
        stat_result: os.stat_result,
        is_compressed: bool,
        rel_path: str
    ):
        """
        Configura headers HTTP otimizados para CDN e cache.
        
        Headers configurados:
        - Cache validation: ETag, Last-Modified
        - Cache strategy: Cache-Control
        - Compression: Content-Encoding, Vary
        - Size: Content-Length
        - Security: X-Content-Type-Options
        - CORS: Access-Control-Allow-Origin (para fontes)
        """
        # ===== VALIDAÇÃO DE CACHE =====
        response["ETag"] = self._generate_etag(stat_result)
        response["Last-Modified"] = http_date(stat_result.st_mtime)
        
        # ===== ESTRATÉGIA DE CACHE =====
        # Usa configuração carregada de settings.STATIC_MIDDLEWARE
        response["Cache-Control"] = self.cache_control
        
        # ===== COMPRESSÃO =====
        if is_compressed:
            response["Content-Encoding"] = "gzip"
            response["Vary"] = "Accept-Encoding"
        
        # ===== TAMANHO DO CONTEÚDO =====
        # Crítico para performance: permite browser calcular progresso
        response["Content-Length"] = stat_result.st_size
        
        # ===== SECURITY HEADERS =====
        response["X-Content-Type-Options"] = "nosniff"
        
        # ===== CORS PARA FONTES =====
        # Permite uso cross-origin de web fonts
        if self._is_font_file(rel_path):
            response["Access-Control-Allow-Origin"] = self.cors_origin_fonts
    
    def _is_font_file(self, path: str) -> bool:
        """Verifica se é arquivo de web font."""
        font_extensions = {'.woff', '.woff2', '.ttf', '.otf', '.eot'}
        return any(path.lower().endswith(ext) for ext in font_extensions)
    
    def get_cache_stats(self) -> dict:
        """
        Retorna estatísticas detalhadas do cache para monitoramento.
        
        Returns:
            Dict com métricas de performance e uso de memória
        """
        total_validations = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_validations * 100) if total_validations > 0 else 0
        
        memory_mb = self._cache_memory_bytes / (1024 * 1024)
        memory_usage_percent = (memory_mb / self.max_cache_memory_mb * 100) if self.max_cache_memory_mb > 0 else 0
        
        avg_entry_size = (
            self._cache_memory_bytes // len(self._file_cache) 
            if self._file_cache else 0
        )
        
        return {
            # Cache size
            'cache_entries': len(self._file_cache),
            'max_cache_entries': self.max_cache_entries,
            'cache_fill_percent': round(
                (len(self._file_cache) / self.max_cache_entries * 100), 2
            ),
            
            # Memory usage
            'memory_usage_mb': round(memory_mb, 2),
            'max_memory_mb': self.max_cache_memory_mb,
            'memory_usage_percent': round(memory_usage_percent, 2),
            'avg_entry_size_bytes': avg_entry_size,
            
            # Performance metrics
            'total_requests': self._total_requests,
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate_percent': round(hit_rate, 2),
            
            # Configuration
            'chunk_size_kb': self.chunk_size // 1024,
        }