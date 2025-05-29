from rgs_django_utils.forms.fields.Field import Field
from rgs_django_utils.models.task import ProjectFile


class FileField(Field):
    def __init__(
        self,
        upload_url: str,
        download_url: str,
        value: int = None,
        accept: str | None = None,
        **kwargs,
    ):
        super().__init__(value=value, **kwargs)
        self.project_id = int
        self.field_type = "FileInput"
        self.instance_type = int
        self.upload_url = upload_url
        self.download_url = download_url
        self.accept = accept

    def validate(self) -> bool:
        if super().validate():
            if self.value is not None and not isinstance(self.value, int):
                self.errors.append(
                    {
                        "type": "value-type",
                        "message": f"Value must be an integer, got {type(self.value)}: {self.value}",
                    }
                )
                return False
            return True
        if self.value is None:
            return False
        if not ProjectFile.objects.filter(id=self.value, project_id=self.project_id).exists():
            self.errors.append({"type": "not-found", "message": f"File with id {self.value} does not exist"})
            return False
        # The user has not sufficient permissions.
        self.errors.append({"type": "not-found", "message": f"File with id {self.value} does not exist"})
        return False

    def to_python(self, value):
        try:
            return int(value)
        except TypeError:
            if not self.required:
                return None
            else:
                raise

    def to_json(self, value):
        try:
            return int(value)
        except TypeError:
            if not self.required:
                return None
            else:
                raise

    def __dict__(self):
        out = super().__dict__()
        out["upload_url"] = self.upload_url
        if self.accept is not None:
            out["accept"] = self.accept
        if self.value is not None:
            try:
                project_file = ProjectFile.objects.get(id=self.value)
            except ProjectFile.DoesNotExist:
                return out
            out["project_file"] = {
                "id": project_file.id,
                "filename": project_file.filename,
                "download_url": self.download_url.replace("{id}", str(project_file.id)),
                # "size": project_file.file.size,
            }
        return out
