# Handgeschreven i.p.v. `makemigrations`: zie 0002_childmodel_json_field.py
# voor de reden. `EnumFilteredTestModel` (en zijn `_ext`-tegenhanger) werden
# in de enum_filter-wijziging aan models.py toegevoegd zonder migratie; de
# tabellen ontbraken daardoor in de test-db. Deze migratie voegt alleen die
# twee ontbrekende modellen toe; de losstaande AlterField-ruis die
# `makemigrations` verder voorstelt (state-only, `dj_extended_models`
# i.p.v. de kale Django-veldklassen) hoort niet in deze wijziging.
import django.db.models.deletion
from django.db import migrations

import rgs_django_utils.database.dj_extended_models


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0003_childmodel_set_null_parent"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnumFilteredTestModel",
            fields=[
                (
                    "id",
                    rgs_django_utils.database.dj_extended_models.TextStringField(
                        primary_key=True, serialize=False, verbose_name="code"
                    ),
                ),
                ("name", rgs_django_utils.database.dj_extended_models.TextStringField(verbose_name="name")),
            ],
            options={
                "db_table": "enum_filtered_test_model",
            },
        ),
        migrations.CreateModel(
            name="EnumFilteredTestModelExtended",
            fields=[
                ("name", rgs_django_utils.database.dj_extended_models.TextStringField(verbose_name="name")),
                ("kind", rgs_django_utils.database.dj_extended_models.TextStringField(verbose_name="soort")),
                (
                    "standards",
                    rgs_django_utils.database.dj_extended_models.ArrayField(
                        base_field=rgs_django_utils.database.dj_extended_models.TextField(),
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "id",
                    rgs_django_utils.database.dj_extended_models.OneToOneField(
                        db_column="id",
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="extended",
                        serialize=False,
                        to="testapp.enumfilteredtestmodel",
                    ),
                ),
            ],
            options={
                "db_table": "enum_filtered_test_model_ext",
            },
        ),
    ]
