from django.conf import settings

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.dj_extended_models import FieldSection, FPresets


class ModificationMetaMixin(models.Model):
    """Abstract mixin adding "who / when" audit columns to a model.

    Contributes five columns:

    * ``db_last_modified`` — Postgres-level sync timestamp
      (``auto_now``), excluded from history tracking.
    * ``last_modified_by`` / ``last_modified_at`` — updated by
      Hasura/import on every change.
    * ``created_by`` / ``created_at`` — populated on insert.

    All fields land in the ``metadata`` :class:`FieldSection` so they
    cluster together in the generated UI / docs.
    """

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
            permissions=models.FPerm(org_mem="-s-", proj_read="-s-"),
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
            presets=FPresets(("iu", {"last_modified_by_id": "x-hasura-user-id"})),
            permissions=models.FPerm(org_mem="-s-", project_read="-s-", project_edit="isu"),
        ),
    )
    last_modified_at = models.DateTimeField(
        "laatst aangepast op",
        auto_now=True,
        config=models.Config(
            section=section,
            doc_short="datum waarop record laatst is aangepast",
            doc_development="wordt gezet door hasura of import",
            permissions=models.FPerm(org_mem="-s-", project_read="-s-", project_edit="isu"),
            # X-Hasura-Now cannot be read from header. So we are going to pass it from frontend as a custom variable.
            # presets=FPresets(("-u", {"last_modified_at": "x-hasura-now"})),
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
            doc_development="'Lazy link' - wordt gezet op basis van 'created_by' bij aanmaken van record",
            presets=FPresets(("i-", {"created_by_id": "x-hasura-user-id"})),
            permissions=models.FPerm(org_mem="-s-", project_read="-s-", project_edit="is-"),
        ),
    )
    created_at = models.DateTimeField(
        "aangemaakt op",
        db_default=models.Func(function="now"),
        config=models.Config(
            section=section,
            doc_short="datum waarop record is aangemaakt",
            doc_development="wordt gezet op basis van 'created_at' bij aanmaken van record",
            permissions=models.FPerm(org_mem="-s-", project_read="-s-", project_edit="is-"),
            # X-Hasura-Now cannot be read from header. So we are going to pass it from frontend as a custom variable.
            # presets=FPresets(("i-", {"created_at": "x-hasura-now"})),
        ),
    )

    class Meta:
        abstract = True


class ModificationSourceMixin(ModificationMetaMixin):
    """Audit mixin that adds import-source tracking on top of :class:`ModificationMetaMixin`.

    Extends the five audit columns with ``source`` (FK to a ``Source``
    table) and ``source_ref`` so rows loaded from bulk imports can point
    back to their original file/row. Uses the ``metasource`` section so
    the two groups stay visually separate.
    """

    section = FieldSection("metasource", "bron metadata", 91)

    source = models.ForeignKey(
        "Source",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="bron",
        config=models.Config(
            section=section,
            doc_short="bron van de data (import bestand, edit sessie of interface); optioneel — leeg bij handmatige invoer",
            doc_development="wordt gezet door hasura of import; optioneel (niet alle data heeft een bron, bv. handmatige invoer)",
            permissions=models.FPerm(org_mem="-s-", project_read="-s-", project_edit="is-"),
        ),
    )
    source_ref = models.TextStringField(
        "bron referentie",
        null=True,
        blank=True,
        config=models.Config(
            section=section,
            doc_short="nummer binnen de bron (bijvoorbeeld regelnummer)",
            permissions=models.FPerm(org_mem="-s-", project_read="-s-", project_edit="is-"),
        ),
    )

    class Meta:
        abstract = True
