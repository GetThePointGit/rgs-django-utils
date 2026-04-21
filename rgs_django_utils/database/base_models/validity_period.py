from rgs_django_utils.database import dj_extended_models as models


class ValidityPeriodMixin(models.Model):
    """Abstract mixin adding ``start_date`` / ``end_date`` validity bounds.

    Both fields are nullable so open-ended periods ("valid until further
    notice") can be modelled with ``end_date = NULL``. No validation is
    attached at this level — consumers are free to add a ``CheckConstraint``
    or application-level guard on ``start_date <= end_date`` where needed.
    """

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True
