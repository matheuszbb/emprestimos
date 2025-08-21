import os
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend

class EmailTemplate(EmailBackend):
    def send_messages(self, email_messages):

        COPYWRITER = os.getenv("COPYWRITER","")
        SITE_URL = os.getenv("SITE_URL", "")
        SITE = os.getenv("SITE", "")

        for message in email_messages:
            if isinstance(message, EmailMultiAlternatives):
                if (hasattr(message, 'alternatives') and isinstance(message.alternatives, list) and len(message.alternatives) > 0 and isinstance(message.alternatives[0], (list, tuple)) and len(message.alternatives[0]) >= 2 and message.alternatives[0][0].strip()):
                    original_html = message.alternatives[0][0]
                    message.alternatives = []
                elif message.body:
                    original_html = message.body.replace('\n', '<br>')

                original_html = original_html.replace('<a ', '<a style="color: #70ff70; text-decoration: underline; font-weight: bold;" ')

                html_content = f"""
                <!DOCTYPE html>
                <html lang="pt-BR">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <meta name="google" content="notranslate">
                        <meta name="format-detection" content="telephone=no">
                        <meta http-equiv="Content-Language" content="pt-BR">
                    </head>
                    <body style="margin: 0; padding: 0; background-color: #1c1c1e;">
                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1c1c1e;">
                            <tr>
                                <td>
                                    <table align="center" width="600" border="0" cellpadding="0" cellspacing="0" style="width: 600px; margin: 0 auto; color: #ffffff; font-family: Helvetica, Arial, sans-serif;">
                                        <tr>
                                            <td style="padding: 20px 10px;">
                                                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                                                    <tr>
                                                        <td width="200" align="left">
                                                            <a href="{SITE_URL}">
                                                                <img src="" alt="{SITE}" style="display: block; width: 200px; height: auto;">
                                                            </a>
                                                        </td>
                                                        <td align="right" style="font-size: 14px; color: #bbbbbb;" class="fallback-font">
                                                            <p style="margin: 0; display: inline-block; margin-left: 15px;"><a href="{SITE_URL}" style="color: #bbbbbb; text-decoration: none;" translate="no">HOME</a></p>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>

                                        <tr>
                                            <td style="padding: 20px 10px;">
                                                <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #2c2c2e; border-radius: 8px;">
                                                    <tr>
                                                        <td style="padding: 40px 30px;">
                                                            <div style="color: #ffffff; font-size: 16px; line-height: 1.5;" class="fallback-font">
                                                                <span style="pointer-events: none;">
                                                                    <font style="vertical-align: inherit;">
                                                                        <font style="vertical-align: inherit;">
                                                                            {original_html}
                                                                        </font>
                                                                    </font>
                                                                </span>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>

                                        <tr>
                                            <td align="center" style="padding: 10px; font-size: 12px; color: #888888;" class="fallback-font">
                                                <span style="pointer-events: none;">
                                                    <font style="vertical-align: inherit;">
                                                        <font style="vertical-align: inherit;">Este é um e-mail automático. Não responda.</font>
                                                    </font>
                                                </span>
                                            </td>
                                        </tr>

                                        <tr>
                                            <td align="center" style="padding: 10px; font-size: 12px; color: #888888;" class="fallback-font">
                                                <span style="pointer-events: none;">
                                                    <font style="vertical-align: inherit;">
                                                        <font style="vertical-align: inherit;">&copy; 2025 {COPYWRITER}. Todos os direitos reservados.</font>
                                                    </font>
                                                </span>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </body>
                </html>
                """
                message.attach_alternative(html_content, "text/html")
        return super().send_messages(email_messages)