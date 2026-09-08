# Handgeschreven i.p.v. `makemigrations`: de autogenerator wil ook alle
# bestaande velden opnieuw "alteren" (0001_initial is al langer uit de pas met
# de modellen). Die drift staat los van dit veld en hoort niet in deze wijziging.
from django.db import migrations

import rgs_django_utils.database.dj_extended_models


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="childmodel",
            name="json_field",
            field=rgs_django_utils.database.dj_extended_models.JSONField(blank=True, null=True),
        ),
    ]
