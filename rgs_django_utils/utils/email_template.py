import urllib
import urllib.parse

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from rgs_django_utils.permissions.claims import Claims


class EmailTemplate:
    """Base class for transactional email templates.

    Subclasses declare the name, subject and body templates as class-level
    attributes, and override :meth:`allowed` / :meth:`enrich_context` to plug
    in authorisation and template-variable resolution. Instances are never
    created directly — :meth:`construct` is the public entry point.

    Attributes
    ----------
    _name : str
        Unique template id used by :meth:`getByName` for lookup.
    _template_text : str
        ``str.format``-style plaintext body template.
    _template_html : str
        ``str.format``-style HTML body template (attached as alternative).
    _template_subject : str
        ``str.format``-style subject template.

    Examples
    --------
    >>> class Welcome(EmailTemplate):
    ...     _name = "welcome"
    ...     _template_subject = "Welcome {name}"
    ...     _template_text = "Hi {name}"
    ...     _template_html = "<p>Hi {name}</p>"
    >>> EmailTemplate.getByName("welcome") is Welcome
    True
    """

    _name = ""
    _template_text = ""
    _template_html = ""
    _template_subject = ""

    @classmethod
    def getByName(cls, name: str):
        """Return the concrete subclass whose ``_name`` matches *name*.

        Parameters
        ----------
        name : str
            Template identifier.

        Returns
        -------
        type[EmailTemplate]
            The matching subclass.

        Raises
        ------
        StopIteration
            If no subclass has ``_name == name``.
        """
        return next(sub for sub in cls.__subclasses__() if sub._name == name)

    @staticmethod
    def allowed(claims: Claims) -> bool:
        """Return ``True`` if *claims* permit sending this template.

        Override in subclasses — the base implementation denies everything
        so a misconfigured subclass can never accidentally send email.
        """
        return False

    @staticmethod
    def enrich_context(context: dict, **kwargs) -> dict:
        """Augment the caller-supplied *context* with template-specific data.

        Override in subclasses to inject URLs, tokens, recipient info, etc.
        The base implementation is an identity pass-through.
        """
        return context

    @staticmethod
    def from_email():
        """Return the ``From:`` address used for this template."""
        return settings.DEFAULT_FROM_EMAIL

    @classmethod
    def construct(cls, context: dict, **kwargs) -> None | EmailMultiAlternatives:
        """Build the ``EmailMultiAlternatives`` message, or ``None`` when denied.

        Parameters
        ----------
        context : dict
            Base template context. Must contain ``to`` after enrichment.
        **kwargs
            Forwarded to :meth:`allowed` and :meth:`enrich_context`. The
            ``claims`` kwarg is the primary authorisation input.

        Returns
        -------
        EmailMultiAlternatives or None
            Ready-to-send Django email with both text and HTML bodies, or
            ``None`` when :meth:`allowed` rejects the send.

        Raises
        ------
        ValueError
            If the enriched context is missing a ``to`` address.
        """
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
        auth_url = settings.AUTH_URL
        if not auth_url.startswith("http://") and not auth_url.startswith("https://"):
            auth_url = f"https://{auth_url}"
        url = f"{auth_url}/callback/{context.get('providerId')}?token={token}&email={urllib.parse.quote_plus(email)}"
        return {
            **context,
            "url": url,
            "to": email,
            "domain": settings.DOMAIN,
            "name": name,
        }
