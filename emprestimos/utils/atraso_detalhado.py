from django.utils.html import format_html

def atraso_detalhado(dias):
    if dias:
        return format_html('❌ Atrasado em {} dia{}', dias, "s" if dias != 1 else "")
    else:
        return format_html('✅ Em dia')
        