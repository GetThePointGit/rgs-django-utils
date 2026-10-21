import os

from django.core.management.base import BaseCommand, CommandError

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()

from django.conf import settings

from rgs_django_utils.commands.export_datamodel_to_json_schema import (
    check_datamodel_json_schema,
    export_datamodel_to_json_schema,
)


def _default_path() -> str:
    """Return the default export path ``<VAR_DIR>/schema/datamodel.schema.json``.

    Resolved lazily (not as argparse default) so the command also loads in
    projects without a ``VAR_DIR`` setting; those fall back to
    ``<BASE_DIR>/../var``.

    Returns
    -------
    str
        The default path.
    """
    var_dir = getattr(settings, "VAR_DIR", None) or os.path.join(settings.BASE_DIR, os.pardir, "var")
    return os.path.join(var_dir, "schema", "datamodel.schema.json")


class Command(BaseCommand):
    """Export the datamodel as a JSON Schema document.

    Thin wrapper around
    :func:`~rgs_django_utils.commands.export_datamodel_to_json_schema.export_datamodel_to_json_schema`.
    The output is consumed by the form builder and by client-side
    validation, and also serves as input for parts of the Hasura metadata.

    With ``--check`` nothing is written: the file at ``--path`` is compared
    with a fresh generation and the command fails (exit 1) with a short
    summary of the differences when it is stale. Consumers that keep a copy
    of the schema (waterworks-ui) use this in a local check before pushing.
    """

    help = "generate json schema with hasura config"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=None,
            help="Path to export JSON schema to; default <VAR_DIR>/schema/datamodel.schema.json.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Write nothing; fail (exit 1) with a summary when the file at --path differs from a fresh generation.",
        )

    def handle(self, *args, **options):
        export_path = options.get("path") or _default_path()

        if options.get("check"):
            verschillen = check_datamodel_json_schema(export_path)
            if verschillen:
                self.stderr.write(f"{export_path} loopt achter op het datamodel:")
                for regel in verschillen:
                    self.stderr.write(f"  - {regel}")
                raise CommandError(
                    f"{export_path} loopt achter; draai manage.py write_models_to_json_schema --path {export_path}"
                )
            self.stdout.write(self.style.SUCCESS(f"{export_path} is bij."))
            return

        self.stdout.write("Start export_datamodel_to_json_schema")
        export_datamodel_to_json_schema(export_path)

        self.stdout.write(self.style.SUCCESS("Successfully ran export_datamodel_to_json_schema"))


if __name__ == "__main__":
    Command().handle()
