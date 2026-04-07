import os

from django.core.management.base import BaseCommand
from thissite import settings

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()

from rgs_django_utils.commands.export_datamodel_to_json_schema import export_datamodel_to_json_schema


class Command(BaseCommand):
    help = "generate json schema with hasura config"

    def add_arguments(self, parser):
        pass
        # Named (optional) arguments
        parser.add_argument(
            "--path",
            type=str,
            default=os.path.join(settings.VAR_DIR, "schema", "datamodel.schema.json"),
            help="Path to export JSON schema to. ",
        )

    def handle(self, *args, **options):
        self.stdout.write("Start export_datamodel_to_json_schema")

        export_path = options.get("path")
        export_datamodel_to_json_schema(export_path)

        self.stdout.write(self.style.SUCCESS("Successfully ran export_datamodel_to_json_schema"))


if __name__ == "__main__":
    Command().handle()
