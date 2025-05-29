import os

from django.core.management.base import BaseCommand
from thissite import settings

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()

from rgs_utils.commands.export_datamodel_to_excel import export_datamodel_to_excel


class Command(BaseCommand):
    help = "generate json with hasura config"

    def add_arguments(self, parser):
        pass
        # Named (optional) arguments
        parser.add_argument(
            "--path",
            type=str,
            default=os.path.join(settings.VAR_DIR, "datamodel.xlsx"),
            help="Path to export metadata to. ",
        )

    def handle(self, *args, **options):
        self.stdout.write("Start export_datamodel_to_excel")

        export_path = options.get("path")
        export_datamodel_to_excel(export_path)

        self.stdout.write(self.style.SUCCESS("Successfully ran export_datamodel_to_excel"))


if __name__ == "__main__":
    Command().handle()
