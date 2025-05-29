import uuid

from django.db import models


app_label = "testapp"


class ParentModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    ids = models.TextField()

    # field types
    int_field = models.IntegerField(default=0)

    class Meta:
        verbose_name = "verbose_parent_model"
        app_label = app_label

    @classmethod
    def get_model_serializer_config(cls, collection):
        return ModelSerializerConfig(
            collection=collection,
            model=cls,
            human_identification_fields=["ids"],
            program_identification_fields=["id"],
            model_dependencies=None,
            project_id_link="id",
            copy_field_names=(
                "ids",
                "int_field",
            ),
            export_field_names=(
                "ids",
                "int_field",
            ),
            import_field_names=(
                "ids",
                "int_field",
            ),
        )


class MiddleModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    ids = models.TextField()

    parent_model = models.ForeignKey(ParentModel, on_delete=models.CASCADE, verbose_name="verbose_parent_model")

    class Meta:
        verbose_name = "verbose_middle_model"
        app_label = app_label

    @classmethod
    def get_model_serializer_config(cls, collection):
        return ModelSerializerConfig(
            collection=collection,
            model=cls,
            human_identification_fields=["ids"],
            program_identification_fields=["uuid"],
            project_id_link="parent_model",
            model_dependencies=[ParentModel],
            copy_field_names=(
                "ids",
                "int_field",
            ),
            export_field_names=(
                "ids",
                "int_field",
            ),
            import_field_names=(
                "ids",
                "int_field",
            ),
        )


class ChildModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    ids = models.TextField()

    middle_model = models.ForeignKey(MiddleModel, on_delete=models.CASCADE, null=True, blank=True)

    # field types
    int_field = models.IntegerField(default=0)

    class Meta:
        verbose_name = "verbose_child_model"
        app_label = app_label

    @classmethod
    def get_model_serializer_config(cls, collection):
        return ModelSerializerConfig(
            collection=collection,
            model=cls,
            human_identification_fields=["middle_model", "ids"],
            program_identification_fields=["uuid"],
            project_id_link="middle_model__parent_model",
            model_dependencies=[MiddleModel],
            copy_field_names=(
                "uuid",
                "middle_model",
                "ids",
                "int_field",
            ),
            export_field_names=("middle_model", "ids", "int_field", "uuid"),
            import_field_names=(
                "uuid",
                "middle_model",
                "ids",
                "int_field",
            ),
        )


class ManyToManyModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    ids = models.TextField()

    middle_model_m2m = models.ManyToManyField(MiddleModel)

    class Meta:
        verbose_name = "verbose_middle_model"
        app_label = app_label
