import urllib.parse
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import urllib

from rgs_utils.permissions.claims import Claims


class EmailTemplate:
    """Base class for email templates.

    All email templates should inherit from this class and implement the following class attributes:
    - _name: a unique name for the template
    - _template_text: the text template for the email
    - _template_html: the HTML template for the email
    - _template_subject: the subject template for the email
    - allowed(claims: Claims) -> bool: a method that returns True if the user has sufficient permissions to send/receive the email
    - enrich_context(context: dict, **kwargs) -> dict: a method that enriches the context with additional data
    """

    _name = ""
    _template_text = ""
    _template_html = ""
    _template_subject = ""

    @classmethod
    def getByName(cls, name: str):
        """Get the subclass by template name.

        Args:
            name (str): Name of the template

        Returns:
            Class: Subclass of EmailTemplate
        """
        return next(sub for sub in cls.__subclasses__() if sub._name == name)

    @staticmethod
    def allowed(claims: Claims) -> bool:
        return False

    @staticmethod
    def enrich_context(context: dict, **kwargs) -> dict:
        return context

    @staticmethod
    def from_email():
        return settings.DEFAULT_FROM_EMAIL

    @classmethod
    def construct(cls, context: dict, **kwargs) -> None | EmailMultiAlternatives:
        if not cls.allowed(kwargs.get("claims", Claims(""))):
            return None

        context = cls.enrich_context(context, **kwargs)

        if "to" not in context:
            raise ValueError("'to' field is required in context")

        subject = cls._template_subject.format(**context)
        text_content = cls._template_text.format(**context)
        html_content = cls._template_html.format(**context)

        msg = EmailMultiAlternatives(subject, text_content, cls.from_email(), (context.get("to"),))
        msg.attach_alternative(html_content, "text/html")
        return msg


class PasswordlessLoginEmail(EmailTemplate):
    _name = "passwordless_login"
    _template_text = """Beste {name},\n\nU kunt zich aanmelden op {domain} door op de volgende koppeling te klikken:\n\n{url}\n\nDeze koppeling is eenmalig en maximaal één dag geldig.\n\nAls u deze e-mail niet heeft aangevraagd mag u deze e-mail als niet verzonden beschouwen.\n\nMet vriendelijke groet,\n\nhet WIT team"""
    _template_html = """<p>Beste {name},</p><p>U kunt zich aanmelden op {domain} door op de volgende koppeling te klikken:</p><p><a href="{url}">{url}</a></p><p>Deze koppeling is eenmalig en maximaal één dag geldig.</p><p>Als u deze e-mail niet heeft aangevraagd mag u deze e-mail als niet verzonden beschouwen.</p><p>Met vriendelijke groet,<br><br>het WIT team</p>"""
    _template_subject = "Aanmelden bij {domain}"

    @staticmethod
    def allowed(claims: Claims) -> bool:
        return claims.has_allowed_role("module_auth_2") and claims.email

    @staticmethod
    def enrich_context(context: dict, claims: Claims, **kwargs) -> dict:
        token = claims.passwordless_token

        if not token:
            raise ValueError("Token is required")
        if not context.get("providerId", None):
            raise ValueError("Provider ID is required")

        email = claims.email
        name = claims.fullname
        url = f"https://{settings.DOMAIN}/api/auth/callback/{context.get("providerId")}?token={token}&email=${urllib.parse.quote_plus(email)}"
        return {
            **context,
            "url": url,
            "to": email,
            "domain": settings.DOMAIN,
            "name": name,
        }
