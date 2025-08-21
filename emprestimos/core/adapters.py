import uuid
import logging
#from .tasks import enviar_email_verificacao
from django.contrib.auth import get_user_model 
from allauth.account.models import EmailAddress
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)
User = get_user_model()

class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email")
        if not email:
            return  

        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if not sociallogin.is_existing:
                # Atualizar e-mail
                EmailAddress.objects.filter(email=email).update(
                    verified=True,
                    primary=True
                )
                sociallogin.connect(request, existing_user)

class CustomAccountAdapter(DefaultAccountAdapter):
    # def send_mail(self, template_prefix, email, context):
    #     """Envia email de verificação de forma assíncrona"""
    #     email_message = self.render_mail(template_prefix, email, context)
    #     assunto = email_message.subject
    #     mensagem = email_message.body
    #     enviar_email_verificacao.delay(assunto, mensagem, email)

    def is_open_for_signup(self, request):
        """Permite login social sem exigir tela de cadastro manual"""
        return True  # Permite sempre o login social

    def populate_user(self, request, user, sociallogin, **kwargs):
        """Define username automaticamente se não informado"""
        if not user.username:
            user.username = self.generate_unique_username(sociallogin)

    def generate_unique_username(self, sociallogin):
        """Gera um username aleatório inexistente"""
        base_username = f"user_{uuid.uuid4().hex[:8]}"  # Inicializa um nome padrão

        while User.objects.filter(username=base_username).exists():
            base_username = f"user_{uuid.uuid4().hex[:8]}"

        return f"{base_username}"  # Se não houver dados sociais, cria um padrão