from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.roles import audit_perm


class ValidityPeriodMixin(models.Model):
    """Abstract mixin adding ``start_date`` / ``end_date`` validity bounds.

    Both fields are nullable so open-ended periods ("valid until further
    notice") can be modelled with ``end_date = NULL``. No validation is
    attached at this level — consumers are free to add a ``CheckConstraint``
    or application-level guard on ``start_date <= end_date`` where needed.
    """

    start_date = models.DateField(
        null=True,
        blank=True,
        config=models.Config(permissions=audit_perm(), presentation=models.Presentation(width=110, bulk_edit=True)),
    )

    end_date = models.DateField(
        null=True,
        blank=True,
        config=models.Config(permissions=audit_perm(), presentation=models.Presentation(width=110, bulk_edit=True)),
    )

    class Meta:
        abstract = True
