from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

class SearchMixin:
    search_fields = []
    order_fields = []
    specific_search = []
    protected_search = ['id']

    def get_queryset(self):
        order = self.request.GET.get('order', '-id')
        if not order:
            order = '-id'
        queryset = super().get_queryset().order_by(order)

        search = self.request.GET.get('search', '')
        search_field = self.request.GET.get('search_field', '')

        if search and self.search_fields:
            q_objects = Q()
            if search_field:
                if (search_field not in self.protected_search) or (search_field in self.protected_search and search.isdigit()):
                    if search_field in self.specific_search:
                        q_objects |= Q(**{f'{search_field}': search})
                    else:
                        q_objects |= Q(**{f'{search_field}__icontains': search})
            else:
                for field in self.search_fields:
                    if (field not in self.protected_search) or (field in self.protected_search and search.isdigit()):
                        if field in self.specific_search:
                            q_objects |= Q(**{f'{field}': search})
                        else:
                            q_objects |= Q(**{f'{field}__icontains': search})
            queryset = queryset.filter(q_objects)
        return queryset

class AdvancedFilterMixin:
    filter_fields = []
    form_to_filter_fields = {}

    def get_queryset(self):
        queryset = super().get_queryset()

        for form_field, filter_field in self.form_to_filter_fields.items():
            value = self.request.GET.get(form_field, '')
            if value:
                if form_field in ['data_inicial', 'data_final']:
                    if value != '':
                        naive = datetime.strptime(value, "%Y-%m-%d")
                        value = timezone.make_aware(naive, timezone.get_current_timezone())
                        if form_field == 'data_inicial':
                            queryset = queryset.filter(**{filter_field: value})
                        else:
                            value += timedelta(days=1)
                            queryset = queryset.filter(**{filter_field: value})
                elif form_field in ['total_minimo', 'total_maximo']:
                    if value != '':
                        value = Decimal(value)
                queryset = queryset.filter(**{filter_field: value})

        return queryset