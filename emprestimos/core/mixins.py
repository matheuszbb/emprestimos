"""
Mixins e utilitários reutilizáveis para views
"""
import random
import logging
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.shortcuts import render
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class AdminRequiredMixin:
    """
    Mixin para verificar se o usuário é superuser.
    Reutilizável em qualquer view que precise de verificação de admin.
    """
    
    async def _check_user_is_superuser(self, request):
        """
        Verifica se o usuário é superuser de forma segura em contexto async.
        
        Returns:
            User ou None
        """
        # Verificar se há um user_id na sessão
        session_user_id = await sync_to_async(lambda: request.session.get('_auth_user_id'))()

        if not session_user_id:
            return None

        # Acessar o usuário diretamente do banco para evitar problemas com lazy loading
        User = get_user_model()
        try:
            user = await User.objects.aget(pk=session_user_id)
            if user.is_superuser and user.is_active:
                return user
            return None
        except (User.DoesNotExist, ValueError):
            return None
    
    async def dispatch(self, request, *args, **kwargs):
        """
        Override dispatch para verificar permissões antes de processar a requisição.
        Views que herdam este mixin podem desabilitar a verificação automática
        definindo `skip_admin_check = True`.
        """
        if not getattr(self, 'skip_admin_check', False):
            admin_user = await self._check_user_is_superuser(request)
            if not admin_user:
                # Detectar se é requisição API (JSON) ou template (HTML)
                is_api_request = (
                    request.META.get('HTTP_ACCEPT', '').startswith('application/json') or
                    request.META.get('CONTENT_TYPE', '').startswith('application/json') or
                    request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
                )
                
                if is_api_request:
                    return JsonResponse({'error': 'Acesso negado'}, status=403)
                else:
                    return await sync_to_async(render)(request, '403.html', status=403)

            request.async_user = admin_user
        
        return await super().dispatch(request, *args, **kwargs)


class DateFilterMixin:
    """
    Mixin para processar filtros de data em views.
    Fornece validação e normalização de datas.
    """
    
    async def _get_date_filters(self, request):
        """
        Extrai e valida filtros de data da requisição.
        
        Args:
            request: Objeto HttpRequest
            
        Returns:
            tuple: (data_inicio, data_fim) como objetos date
            
        Raises:
            ValueError: Se as datas forem inválidas
        """
        # Obter parâmetros de data
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')

        # Valores padrão: últimos 30 dias
        hoje = timezone.now().date()
        data_inicio_default = hoje - timedelta(days=30)
        data_fim_default = hoje

        try:
            if data_inicio_str:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                # Validar que não é data futura
                if data_inicio > hoje:
                    data_inicio = data_inicio_default
            else:
                data_inicio = data_inicio_default

            if data_fim_str:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                # Validar que não é data futura
                if data_fim > hoje:
                    data_fim = data_fim_default
            else:
                data_fim = data_fim_default

            # Garantir que data_inicio <= data_fim
            if data_inicio > data_fim:
                data_inicio, data_fim = data_fim, data_inicio

            # Limitar período máximo a 1 ano para performance
            if (data_fim - data_inicio).days > 365:
                logger.warning(f"Período muito longo solicitado: {(data_fim - data_inicio).days} dias")
                data_inicio = data_fim - timedelta(days=365)

            return data_inicio, data_fim

        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao processar filtros de data: {e}")
            return data_inicio_default, data_fim_default

