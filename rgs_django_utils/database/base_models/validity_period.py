from rgs_django_utils.database import dj_extended_models as models


class ValidityPeriodMixin(models.Model):
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True
