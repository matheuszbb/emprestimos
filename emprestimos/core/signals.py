from decimal import Decimal
from django.utils import timezone
from django.dispatch import receiver
from .models import Emprestimo, Parcela
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, pre_delete, post_save

@receiver(post_save, sender=Emprestimo)
def criar_parcelas(sender, instance, created, **kwargs):
    if created:
        # Número de parcelas como inteiro
        num_parcelas = int(instance.parcelas)

        # Valor de cada parcela
        valor_por_parcela = instance.recebimento_futuro() / Decimal(num_parcelas)

        # Gerar as parcelas
        for i in range(1, num_parcelas + 1):
            Parcela.objects.create(
                emprestimo=instance,
                cliente=instance.cliente,
                responsavel=instance.responsavel,
                valor=valor_por_parcela,
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