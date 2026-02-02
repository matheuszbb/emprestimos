import os
import logging
import inspect
import aiofiles
import mimetypes
from django.conf import settings
from django.utils._os import safe_join
from django.utils.http import http_date
from email.utils import parsedate_to_datetime
from django.http import StreamingHttpResponse, HttpResponseNotModified
from asgiref.sync import iscoroutinefunction, markcoroutinefunction

logger = logging.getLogger("django.request")

class AsyncStaticMiddleware:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        if not request.path.startswith(settings.STATIC_URL):
            return await self.get_response(request)

        rel_path = request.path[len(settings.STATIC_URL):].lstrip('/')
        try:
            full_path = safe_join(settings.STATIC_ROOT, rel_path)
        except ValueError:
            return await self.get_response(request)

        # 1. Lógica de Gzip (Igual WhiteNoise)
        accept_encoding = request.headers.get("Accept-Encoding", "")
        compressed_path = full_path + ".gz"
        serve_path = full_path
        is_compressed = False

        if "gzip" in accept_encoding and os.path.exists(compressed_path):
            serve_path = compressed_path
            is_compressed = True
            logger.debug(f"✅ [static] Gzip encontrado para {rel_path}")
        else:
            # Esse log vai te dizer se o arquivo .gz realmente existe onde o Django procura
            if "gzip" in accept_encoding:
                logger.debug(f"❌ [static] Gzip ausente no disco: {compressed_path}")

        if os.path.exists(serve_path) and os.path.isfile(serve_path):
            stat = os.stat(serve_path)
            
            # 2. Lógica de Cache (304) - Crucial para performance
            if_modified_since = request.headers.get("If-Modified-Since")
            if if_modified_since and int(stat.st_mtime) <= self.parse_http_date(if_modified_since):
                return HttpResponseNotModified()

            # 3. Resposta Assíncrona Nativa (Resolve o Warning)
            # Criamos um gerador assíncrono para ler o arquivo
            async def file_iterator(file_path, chunk_size=65536):
                async with aiofiles.open(file_path, mode='rb') as f:
                    while chunk := await f.read(chunk_size):
                        yield chunk

            response = StreamingHttpResponse(file_iterator(serve_path))
            
            # 4. Cabeçalhos de Eficiência
            content_type, _ = mimetypes.guess_type(full_path)
            response["Content-Type"] = content_type or "application/octet-stream"
            if is_compressed:
                response["Content-Encoding"] = "gzip"
            
            response["Cache-Control"] = "public, max-age=31536000, immutable"
            response["Last-Modified"] = http_date(stat.st_mtime)
            return response

        return await self.get_response(request)

    def parse_http_date(self, date_str):
        try:
            return int(parsedate_to_datetime(date_str).timestamp())
        except: return 0