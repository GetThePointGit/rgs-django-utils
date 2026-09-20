# Handgeschreven i.p.v. `makemigrations`: zie 0002_childmodel_json_field.py
# voor de reden (0001_initial loopt al langer uit de pas met de modellen;
# die drift hoort niet in deze wijziging).
import django.db.models.deletion
from django.db import migrations

import rgs_django_utils.database.dj_extended_models


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0002_childmodel_json_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="childmodel",
            name="set_null_parent",
            field=rgs_django_utils.database.dj_extended_models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deferrable_children",
                to="testapp.parentmodel",
            ),
        ),
    ]
