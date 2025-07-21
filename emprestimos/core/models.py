import re
from decimal import Decimal
from django.db import models
from django.contrib import admin
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from utils.atraso_detalhado import atraso_detalhado
from utils.formatar_dinheiro import formatar_dinheiro
from django.core.validators import MinValueValidator, MaxValueValidator, MaxLengthValidator

PARCELAS_CHOICES = [(str(i), str(i)) for i in range(1,13,1)]

TIPO_CONTATO_CHOICES = (
    ('celular', 'Celular'),
    ('whatsapp', 'WhatsApp'),
    ('email', 'Email'),
    ('instagram', 'Instagram'),
    ('facebook', 'Facebook'),
    ('telegram', 'Telegram'),
)

def validate_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)

    if len(cpf) != 11:
        raise ValidationError("CPF deve ter 11 dígitos.")
    if cpf == cpf[0] * 11:
        raise ValidationError("CPF inválido.")

    sum_of_products = sum((10-i) * int(cpf[i]) for i in range(9))
    verifying_digit = (sum_of_products * 10 % 11) % 10

    if verifying_digit != int(cpf[9]):
        raise ValidationError("CPF inválido.")

    sum_of_products = sum((11-i) * int(cpf[i]) for i in range(10))
    verifying_digit = (sum_of_products * 10 % 11) % 10

    if verifying_digit != int(cpf[10]):
        raise ValidationError("CPF inválido.")

class Cliente(models.Model):
    responsavel = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=255, blank=True, null=True)
    nome_completo = models.CharField(max_length=355, blank=True)
    cpf = models.CharField(max_length=11, blank=True, null=True, validators=[validate_cpf])
    data_cadastro = models.DateTimeField(default=timezone.now)
    limite_maximo = models.DecimalField(default=10000, max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('12.00'))])
    limite = models.DecimalField(default=1000, max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('12.00'))],verbose_name='Limite por Empréstimo')
    banimento = models.BooleanField(default=False)
    motivo_banimento = models.TextField(validators=[MaxLengthValidator(1024)], blank=True, null=True)
    data_banimento = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.id} - {self.nome_completo} - {self.responsavel.username}'

    def clean(self):
        if self.cpf:
            if self.id is not None and Cliente.objects.filter(cpf=self.cpf, responsavel=self.responsavel).exclude(id=self.id).exists():
                raise ValidationError("CPF já está em uso.")
            elif self.id is None and Cliente.objects.filter(cpf=self.cpf, responsavel=self.responsavel).exists():
                raise ValidationError("CPF já está em uso.")
        if self.pk and self.responsavel:
            original = Cliente.objects.get(pk=self.pk)
            if original.responsavel != self.responsavel:
                raise ValidationError("Não é permitido alterar o(a) responsável depois da criação.")

    def save(self, *args, **kwargs):
        self.nome_completo = f'{self.nome} {self.sobrenome if self.sobrenome else ""}'
        super().save(*args, **kwargs)
    
    def cpf_protegido(self):
        if self.cpf:
            return f'***.{self.cpf[3:6]}.***-{self.cpf[9:]}'
        else:
            return f''

    @admin.display(description="Cpf")
    def cpf_formatado(self):
        if self.cpf:
            return f'{self.cpf[0:3]}.{self.cpf[3:6]}.{self.cpf[6:9]}-{self.cpf[9:]}'
        else:
            return f''
    
    def limite_disponivel(self):
        total_pendente = self.emprestimo_set.filter(status=False).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        return (self.limite_maximo - total_pendente).quantize(Decimal('0.01'))
    
    def limite_usado(self):
        return self.emprestimo_set.filter(status=False).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    
    @admin.display(description="Limite por Empréstimo")
    def limite_f(self):
        return formatar_dinheiro(self.limite)

    @admin.display(description="Limite Máximo")
    def limite_maximo_f(self):
        return formatar_dinheiro(self.limite_maximo)

    @admin.display(description="Limite Disponível")
    def limite_disponivel_f(self):
        return formatar_dinheiro(self.limite_disponivel())

    @admin.display(description="Limite Usado")
    def limite_usado_f(self):
        return formatar_dinheiro(self.limite_usado())

class Contato(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='contatos')
    tipo = models.CharField(
        max_length=100, 
        choices=TIPO_CONTATO_CHOICES,
        default='celular',
    )
    contato = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.pk} - {self.get_tipo_display()} - {self.contato}'
    
    def numero_formatado(self):
        if self.tipo in ['celular', 'whatsapp'] and self.contato:
            contato = self.contato
            digitCount = len(contato)
            if digitCount == 13:
                return f'+{contato[0:2]} ({contato[2:4]}) {contato[4]}{contato[5:9]}-{contato[9:]}'
            elif digitCount == 12:
                return f'+{contato[0:2]} ({contato[2:4]}) {contato[4:8]}-{contato[8:]}'
            elif digitCount == 11:
                return f'({contato[0:2]}) {contato[2]}{contato[3:7]}-{contato[7:]}'
            elif digitCount == 10:
                return f'({contato[0:2]}) {contato[2:6]}-{contato[6:]}'
        else:
            return ''
    
    def clean(self):
        tipo = self.tipo
        contato = self.contato

        if tipo in ['celular', 'whatsapp', 'telegram']:
            contato = re.sub(r'\D', '', contato)
            if not re.match(r'^(55)?\d{2}9\d{8}$', contato):
                raise ValidationError("O Número de celular inválido. Deve estar no padrão brasileiro, exemplos: +55 (DDD) 9XXXX-XXXX ou (DDD) 9XXXX-XXXX")
            else:
                self.contato = contato
        elif tipo == 'email':
            try:
                validate_email(contato)
            except ValidationError:
                raise ValidationError("Email inválido.")
        elif tipo in ['instagram', 'facebook']:
            if not contato.isalnum():
                raise ValidationError("O nome de usuário deve ser alfanumérico.")   

class Emprestimo(models.Model):     
    responsavel = models.ForeignKey(User, on_delete=models.CASCADE, null=True)      
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True)
    data_inicio = models.DateTimeField(default=timezone.now)  
    data_fim = models.DateTimeField(default=timezone.now)
    data_pagamento = models.DateTimeField(blank=True, null=True)  
    status = models.BooleanField(default=False)
    parcelas = models.CharField(max_length=2, choices=PARCELAS_CHOICES, default='1')
    valor = models.DecimalField(default=1000, max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('12.00'))])
    porcentagem = models.DecimalField(default=Decimal('30.00'),max_digits=5,decimal_places=2,validators=[MinValueValidator(Decimal('1.00')),MaxValueValidator(Decimal('100.00'))])
    motivo = models.TextField(validators=[MaxLengthValidator(1024)], blank=True, null=True, default="Preciso do empréstimo para comprar uma coisa específica.")
    comprovante = models.BinaryField(blank=True, null=True)
    tipo_comprovante = models.CharField(max_length=50, blank=True, null=True)

    @admin.display(description="Valor")
    def valor_f(self):
        return formatar_dinheiro(self.valor)

    def lucro(self):
        return (self.valor * self.porcentagem / Decimal('100')).quantize(Decimal('0.01'))

    def recebimento_futuro(self):
        return (self.valor + self.lucro()).quantize(Decimal('0.01'))

    def recebimento_atual(self):
        total_pago = self.parcela_set.filter(status=True).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        return total_pago.quantize(Decimal('0.01'))

    def parcelas_pagas(self):
        return self.parcela_set.filter(status=True).count()

    def parcelas_restantes(self):
        return self.parcela_set.filter(status=False).count()

    def parcela_atual(self):
        return self.parcela_set.filter(status=False).order_by('numero_parcela').first()

    def parcela_anterior(self):
        return self.parcela_set.filter(status=True).order_by('-numero_parcela').first()

    def proxima_parcela(self):
        return self.parcela_set.filter(status=False, data_fim__gte=timezone.now()).order_by('data_fim').first()

    def atraso(self):
        return not self.status and self.data_fim < timezone.now()
    
    def dias_atraso(self):
        if self.atraso():
            diferenca = timezone.now().date() - self.data_fim.date()
            return diferenca.days
        return 0

    @admin.display(description="Atraso")
    def atraso_detalhado_f(self):
        return atraso_detalhado(self.dias_atraso())

    def __str__(self):
        return f'{self.id} - {self.cliente.nome} - {self.responsavel.username}'
    
    def clean(self):
        if not self.pk:
            if self.status:
                raise ValidationError("Este empréstimo não pode ser marcado como concluído ao ser criado, desmarque 'Status'.")
            
            if self.cliente:
                if self.cliente.banimento:
                    nome = self.cliente.nome_completo
                    data = self.cliente.data_banimento.strftime('%d/%m/%Y') if self.cliente.data_banimento else 'data desconhecida'
                    raise ValidationError(f"Não é permitido criar um novo empréstimo para o cliente '{nome}', que está banido desde {data}.")

                if self.valor > self.cliente.limite:
                    raise ValidationError(f"O valor ultrapassa o limite de R$ {self.cliente.limite:,.2f} por Empréstimo.")

                soma_pendente = Emprestimo.objects.filter(cliente=self.cliente,status=False).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

                if soma_pendente + self.valor > self.cliente.limite_maximo:
                    raise ValidationError(
                        f"Total de empréstimos pendentes: R$ {soma_pendente:,.2f} ."
                        f"Novo valor ultrapassa o limite de R$ {self.cliente.limite_maximo:,.2f} ."
                    )
        else:
            if self.status:
                parcelas_pendentes = self.parcela_set.filter(status=False).exists()
                if parcelas_pendentes:
                    raise ValidationError("Este empréstimo não pode ser marcado como concluído. Ainda existem parcelas não pagas.")
                
            original = Emprestimo.objects.get(pk=self.pk)
            
            if original.valor != self.valor:
                raise ValidationError("Não é permitido alterar o valor do empréstimo depois da criação.")
            if original.parcelas != self.parcelas:
                raise ValidationError("Não é permitido alterar a quantidade de parcelas depois da criação.")
            if original.porcentagem != self.porcentagem:
                raise ValidationError("Não é permitido alterar a porcentagem de lucro depois da criação.")
            if original.responsavel != self.responsavel:
                raise ValidationError("Não é permitido alterar o(a) responsável depois da criação.")
            if original.cliente != self.cliente:
                raise ValidationError("Não é permitido alterar a cliente depois da criação.")

    def save(self, *args, **kwargs):
        self.full_clean()  # chama o clean antes de salvar
        super().save(*args, **kwargs)

class Parcela(models.Model):
    responsavel = models.ForeignKey(User, on_delete=models.CASCADE, null=True)      
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True)
    emprestimo = models.ForeignKey(Emprestimo, on_delete=models.CASCADE, null=True)
    valor = models.DecimalField(default=1000, max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('1.01'))])
    data_inicio = models.DateTimeField(default=timezone.now)  
    data_fim = models.DateTimeField(default=timezone.now)
    data_pagamento = models.DateTimeField(blank=True, null=True) 
    status = models.BooleanField(default=False)
    numero_parcela = models.CharField(max_length=2, choices=PARCELAS_CHOICES, default='1')
    comprovante = models.BinaryField(blank=True, null=True)
    tipo_comprovante = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.emprestimo.id} - {self.cliente.nome} - {self.responsavel.username}"
    
    @admin.display(description="Valor")
    def valor_f(self):
        return formatar_dinheiro(self.valor)

    def atraso(self):
        return not self.status and self.data_fim < timezone.now()
    
    def dias_atraso(self):
        if self.atraso():
            diferenca = timezone.now().date() - self.data_fim.date()
            return diferenca.days
        return 0
    
    @admin.display(description="Atraso")
    def atraso_detalhado_f(self):
        return atraso_detalhado(self.dias_atraso())

    def clean(self):
        if self.emprestimo:
            total_parcelas = int(self.emprestimo.parcelas)

            # Verifica se já existem parcelas associadas
            existentes = Parcela.objects.filter(emprestimo=self.emprestimo)
            # Prevenção contra excesso de parcelas
            if not self.pk and existentes.count() >= total_parcelas:
                raise ValidationError(f"Este empréstimo só permite {total_parcelas} parcelas. Você já criou {existentes.count()}.")
            
            # Prevenção contra número duplicado
            duplicada = existentes.filter(numero_parcela=self.numero_parcela).exclude(pk=self.pk).exists()
            if duplicada:
                raise ValidationError(f"Já existe uma parcela número {self.numero_parcela} para este empréstimo.")

            if self.pk:
                original = Parcela.objects.get(pk=self.pk)
                if original.numero_parcela != self.numero_parcela:
                    raise ValidationError("Não é permitido alterar o número da parcela existente.")
                if original.valor != self.valor:
                    raise ValidationError("Não é permitido alterar o valor da parcela depois da criação.")
                if original.responsavel != self.responsavel:
                    raise ValidationError("Não é permitido alterar o(a) responsável depois da criação.")
                if original.cliente != self.cliente:
                    raise ValidationError("Não é permitido alterar a cliente depois da criação.")
                if original.emprestimo != self.emprestimo:
                    raise ValidationError("Não é permitido alterar o emprestimo depois da criação.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def delete(self, using=None, keep_parents=False):
        if self.emprestimo and self.emprestimo.pk:
            raise ValidationError("Parcelas não podem ser apagadas diretamente. Exclua o empréstimo para remover todas.")
        super().delete(using=using, keep_parents=keep_parents)