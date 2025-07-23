from django.utils import timezone
from django.dispatch import receiver
from .models import Emprestimo, Parcela
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from django.db.models.signals import post_delete, pre_delete, post_save

@receiver(post_save, sender=Emprestimo)
def criar_parcelas(sender, instance, created, **kwargs):
    if created:
        valor_bruto = instance.recebimento_futuro()
        num_parcelas = int(instance.parcelas)

        # Arredondamento para cima (padrão comercial)
        valor_por_parcela = (valor_bruto / Decimal(num_parcelas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Diferença gerada pelo arredondamento
        valor_total = valor_por_parcela * Decimal(num_parcelas)
        diferenca = valor_total - valor_bruto

        for i in range(1, num_parcelas + 1):
            valor_final = valor_por_parcela
            # Subtrai o excesso na primeira parcela, para que o total final fique exato
            if i == 1 and diferenca > 0:
                valor_final -= diferenca

            Parcela.objects.create(
                emprestimo=instance,
                cliente=instance.cliente,
                responsavel=instance.responsavel,
                valor=valor_final,
                numero_parcela=str(i),
                data_inicio=timezone.now(),
                data_fim=timezone.now() + timezone.timedelta(days=30 * i),
            )

        # Atualizar data_fim do empréstimo
        instance.data_fim = timezone.now() + timezone.timedelta(days=30 * num_parcelas)
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