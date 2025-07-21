from decimal import Decimal
from django.utils.html import format_html

def formatar_dinheiro(valor, prefixo='R$'):
    if valor is None:
        valor = Decimal('0.00')
    texto = f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    return format_html(f'{prefixo} {texto}')