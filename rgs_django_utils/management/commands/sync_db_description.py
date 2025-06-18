from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


class Command(BaseCommand):
    help = "Sync django extended model description to description tables."

    def add_arguments(self, parser):
        pass
        # Named (optional) arguments
        # parser.add_argument(
        #     'task_id',
        #     help='Taak id',
        # )

    def handle(self, *args, **options):
        self.stdout.write("Start sync_db_meta_tables")

        from rgs_django_utils.commands.sync_db_description import sync_db_meta_tables

        sync_db_meta_tables()

        self.stdout.write(self.style.SUCCESS("Successfully ran sync_db_meta_tables"))


if __name__ == "__main__":
    Command().handle()
