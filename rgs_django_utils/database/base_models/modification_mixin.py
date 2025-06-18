from django.conf import settings

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.dj_extended_models import FieldSection


class ModificationMetaMixin(models.Model):
    section = FieldSection("metadata", "metadata", 90)
    # meta
    db_last_modified = models.DateTimeField(
        "laatst aangepast in central database",
        editable=False,
        auto_now=True,
        config=models.Config(
            section=section,
            doc_short="laatst aangepast in centrale database. Gebruikt voor synchronisatie",
            ignore_for_history=True,
        ),
    )

    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="laatst aangepast door",
        related_name="last_modified_%(class)s",
        config=models.Config(
            section=section,
            doc_short="id van de gebruiker die record laatst heeft aangepast",
            doc_development="'Lazy link' - veld wordt gezet door hasura of import",
        ),
    )
    last_modified_at = models.DateTimeField(
        "laatst aangepast op",
        auto_now=True,
        config=models.Config(
            section=section,
            doc_short="datum waarop record laatst is aangepast",
            doc_development="wordt gezet door hasura of import",
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="aangemaakt door",
        related_name="created_%(class)s",
        config=models.Config(
            section=section,
            doc_short="id van de gebruiker die record heeft aangemaakt",
            doc_development="'Lazy link' - wordt gezet op basis van 'last_modified_by' bij aanmaken van record",
        ),
    )
    created_at = models.DateTimeField(
        "aangemaakt op",
        db_default=models.Func(function="now"),
        config=models.Config(
            section=section,
            doc_short="datum waarop record is aangemaakt",
            doc_development="wordt gezet op basis van 'last_modified_at' bij aanmaken van record",
        ),
    )

    class Meta:
        abstract = True


class ModificationSourceMixin(ModificationMetaMixin):
    section = FieldSection("metasource", "bron metadata", 91)

    source = models.ForeignKey(
        "Source",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="bron",
        config=models.Config(
            section=section,
            doc_short="bron van de data (import bestand, edit sessie of interface)",
            doc_development="wordt gezet door hasura of import",
        ),
    )
    source_ref = models.TextStringField(
        "bron referentie",
        null=True,
        blank=True,
        config=models.Config(
            section=section,
            doc_short="nummer binnen de bron (bijvoorbeeld regelnummer)",
        ),
    )

    class Meta:
        abstract = True
