from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from rgs_utils.setup_django import setup_django

    setup_django()


class Command(BaseCommand):
    help = "generate json with hasura config"

    def add_arguments(self, parser):
        pass
        # Named (optional) arguments
        parser.add_argument(
            "--export_path",
            help="Path to export metadata to. Default is the hasura directory in the project root.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Start generate_hasura_metadata")

        from rgs_utils.utils.generate_hasura_metadata import generate_hasura_metadata

        export_path = options.get("export_path")
        generate_hasura_metadata(export_path)

        self.stdout.write(self.style.SUCCESS("Successfully ran generate_hasura_metadata"))


if __name__ == "__main__":
    Command().handle()
