import calendar
from django.utils import timezone
from django.dispatch import receiver
from .models import Emprestimo, Parcela
from decimal import Decimal, ROUND_HALF_UP
from django.db.models.signals import post_save
from dateutil.relativedelta import relativedelta

def ajustar_dia(data, dia_alvo):
    """
    Ajusta a data para o dia_alvo do mês.
    Se o mês não tiver esse dia, usa o último dia do mês.
    """
    ano = data.year
    mes = data.month
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia_final = min(dia_alvo, ultimo_dia)
    return data.replace(day=dia_final, hour=0, minute=0, second=0, microsecond=0)

@receiver(post_save, sender=Emprestimo)
def criar_parcelas(sender, instance, created, **kwargs):
    if created:
        valor_bruto = instance.recebimento_futuro()
        num_parcelas = int(instance.parcelas)

        # Garantir que data_inicio seja timezone-aware e meia-noite
        data_inicio = instance.data_inicio
        if timezone.is_naive(data_inicio):
            data_inicio = timezone.make_aware(data_inicio)
        data_inicio = data_inicio.replace(hour=0, minute=0, second=0, microsecond=0)

        dia_alvo = data_inicio.day  # dia do mês que queremos manter

        # Arredondamento comercial
        valor_por_parcela = (valor_bruto / Decimal(num_parcelas)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        valor_total = valor_por_parcela * Decimal(num_parcelas)
        diferenca = valor_total - valor_bruto

        for i in range(1, num_parcelas + 1):
            valor_final = valor_por_parcela
            if i == 1 and diferenca > 0:
                valor_final -= diferenca

            # Somar meses e ajustar para o dia correto
            data_fim_base = data_inicio + relativedelta(months=i)
            data_fim = ajustar_dia(data_fim_base, dia_alvo)

            if timezone.is_naive(data_fim):
                data_fim = timezone.make_aware(data_fim)

            Parcela.objects.create(
                emprestimo=instance,
                cliente=instance.cliente,
                responsavel=instance.responsavel,
                valor=valor_final,
                numero_parcela=str(i),
                data_inicio=data_inicio,
                data_fim=data_fim,
            )

        # Atualizar data_fim do empréstimo
        data_fim_emprestimo_base = data_inicio + relativedelta(months=num_parcelas)
        instance.data_fim = ajustar_dia(data_fim_emprestimo_base, dia_alvo)
        if timezone.is_naive(instance.data_fim):
            instance.data_fim = timezone.make_aware(instance.data_fim)

        instance.save()

@receiver(post_save, sender=Parcela)
def verificar_pagamento_completo(sender, instance, **kwargs):
    if not instance.pk or not instance.emprestimo:
        return  # Garante que a parcela e o empréstimo existem

    emprestimo = instance.emprestimo

    # Atualiza data_pagamento da parcela, se ela foi marcada como paga e ainda não tem data
    if instance.status and not instance.data_pagamento:
        instance.data_pagamento = timezone.now()
        instance.save(update_fields=['data_pagamento'])

    # Verifica se todas as parcelas estão quitadas
    todas_pagas = not emprestimo.parcela_set.filter(status=False).exists()

    if todas_pagas and emprestimo.status == False:
        # Marca empréstimo como quitado
        emprestimo.status = True
        emprestimo.data_pagamento = timezone.now()
        emprestimo.save(update_fields=['status', 'data_pagamento'])
    elif emprestimo.status and todas_pagas == False:
        # Reverte status do empréstimo se ainda houver parcelas pendentes
        emprestimo.status = False
        emprestimo.data_pagamento = None
        emprestimo.save(update_fields=['status', 'data_pagamento'])