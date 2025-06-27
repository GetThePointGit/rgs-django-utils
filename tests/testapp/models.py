import uuid

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models import BaseEnum, BaseEnumExtended

app_label = "testapp"

section_one = models.FieldSection("loc", "section_one", 1)
section_two = models.FieldSection("loc", "section_two", 2)


class ParentModel(models.Model):
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        config=models.Config(
            section=section_one,
            trigger_calc=[40, 50],
            hasura_set=models.HasuraSet(
                "x-hasura-userId",
                "now()"
            ),
            permissions=models.FPerm(
                project="-s-",
            ),
        ),
    )
    ids = models.TextField(
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
            ),
        ),
    )

    # field types
    int_field = models.IntegerField(
        default=0,
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
            ),
        ),
    )

    class Meta:
        verbose_name = "verbose_parent_model"
        app_label = app_label

    class TableDescription:
        modules = "*"

    @classmethod
    def get_permissions(cls):
        return models.TPerm(
            public=None,
            project={
                "insert": {},
                "select": {},
                "update": {},
                "delete": {},
            },
        )

    @classmethod
    def get_model_serializer_config(cls, collection):
        pass
        # return ModelSerializerConfig(
        #     collection=collection,
        #     model=cls,
        #     human_identification_fields=["ids"],
        #     program_identification_fields=["id"],
        #     model_dependencies=None,
        #     project_id_link="id",
        #     copy_field_names=(
        #         "ids",
        #         "int_field",
        #     ),
        #     export_field_names=(
        #         "ids",
        #         "int_field",
        #     ),
        #     import_field_names=(
        #         "ids",
        #         "int_field",
        #     ),
        # )


class MiddleModel(models.Model):
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="is-",
            ),
        ),
    )
    ids = models.TextField(
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="isu",
            ),
        ),
    )

    parent_model = models.ForeignKey(
        ParentModel,
        on_delete=models.CASCADE,
        verbose_name="verbose_parent_model",
        related_name="middle_models",
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="isu",
            ),
        ),
    )

    class Meta:
        verbose_name = "verbose_middle_model"
        app_label = app_label

    class TableDescription:
        modules = "*"

    @classmethod
    def get_permissions(cls):
        filt = {"parent_model": {"ids": {"_eq": "test"}}}
        return models.TPerm(
            public=None,
            project=filt,
            project_management={
                "insert": filt,
                "select": filt,
                "update": filt,
                "delete": filt,
            },
        )


class MiddleExtendedModel(models.Model):
    id = models.OneToOneField(
        MiddleModel,
        primary_key=True,
        related_name="extended",
        on_delete=models.CASCADE,
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="is-",
            ),
        ),
    )
    extra = models.TextField(
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="isu",
            ),
        ),
    )

    class Meta:
        verbose_name = "middle_extended_model"
        app_label = app_label

    @classmethod
    def get_permissions(cls):
        filt = {"parent_model": {"ids": {"_eq": "test"}}}
        return models.TPerm(
            public=None,
            project=filt,
        )


class ChildModel(models.Model):
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="is-",
            ),
        ),
    )
    ids = models.TextField(
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="is-",
            ),
        ),
    )

    middle_model = models.ForeignKey(
        MiddleModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        config=models.Config(
            section=section_one,
            permissions=models.FPerm(
                project="-s-",
                project_edit="is-",
            ),
        ),
    )

    # field types
    int_field = models.IntegerField(default=0)

    class Meta:
        verbose_name = "verbose_child_model"
        app_label = app_label

    @classmethod
    def get_permissions(cls):
        filt = {"middle_model": {"parent_model": {"ids": {"_eq": "test"}}}}
        return models.TPerm(
            public=None,
            project=filt,
        )


class ManyToManyModel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    ids = models.TextField()

    middle_model_m2m = models.ManyToManyField(MiddleModel)

    class Meta:
        verbose_name = "verbose_middle_model"
        app_label = app_label

    @classmethod
    def get_permissions(cls):
        filt = {"middle_model": {"parent_model": {"ids": {"_eq": "test"}}}}
        return models.TPerm(
            public=None,
            project=filt,
            project_management={
                "insert": {},
                "select": {},
            },
        )


class EnumExtendedTestModel(BaseEnumExtended):
    description = models.TextField(
        config=models.Config(
            section=section_two,
            permissions=models.FPerm("-s-"),
        ),
    )

    class Meta:
        db_table = "enum_extended_test_model"
        app_label = app_label

    class TableDescription:
        modules = "*"

    @classmethod
    def get_permissions(cls):
        filt = {"parent_model": {"ids": {"_eq": "test"}}}
        return models.TPerm({})

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "description"],
            "data": [
                ("A_0", "test0", "test 0 beschrijving"),
                ("A_1", "test1", "test 1 beschrijving"),
                ("A_2", "test2", "test 2 beschrijving"),
                ("A_3", "test3", "test 3 beschrijving"),
            ],
        }


class EnumTestModel(BaseEnum):
    class Meta:
        db_table = "enum_test_model"
        app_label = app_label

    class TableDescription:
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "description"],
            "data": [
                ("A_10", "test enum 0", "test enum 0 beschrijving"),
                ("A_11", "test enum 1", "test enum 1 beschrijving"),
                ("A_12", "test enum 2", "test enum 2 beschrijving"),
                ("A_13", "test enum 3", "test enum 3 beschrijving"),
            ],
        }
