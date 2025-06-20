from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from psycopg import sql

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


from thissite import settings

from rgs_django_utils.commands.export_datamodel_to_excel import export_datamodel_to_excel
from rgs_django_utils.database.install_db_default_records import add_default_records


class Command(BaseCommand):
    help = "Migrate datagse and update triggers, default records and db description"

    def add_arguments(self, parser):
        pass
        # Named (optional) arguments
        parser.add_argument(
            "--skip_migration",
            action="store_true",
            help="skip django migration command and run only the additional scripts",
        )
        parser.add_argument(
            "--skip_before",
            action="store_true",
            help="skip postgres before functions",
        )

    def handle(self, *args, **options):
        skip_migration = options.get("skip_migration")
        skip_before = options.get("skip_before")

        self.stdout.write("Start migrate database and update triggers and hasura metadata")

        from rgs_django_utils.commands.sync_db_description import sync_db_meta_tables
        from rgs_django_utils.database.install_db_defaults_and_relation_cascading import (
            install_db_defaults_and_relation_cascading,
        )
        from rgs_django_utils.database.install_db_functions_and_triggers import (
            install_db_before_functions,
            install_db_functions,
            install_db_last_functions,
        )

        if not skip_before:
            self.stdout.write(self.style.SUCCESS("RUN install_db_before_functions"))
            install_db_before_functions()

        if not skip_migration:
            self.stdout.write(self.style.SUCCESS("RUN migrate"))
            call_command("migrate")

        self.stdout.write(self.style.SUCCESS("RUN install_db_defaults_and_relation_cascading"))
        install_db_defaults_and_relation_cascading()

        self.stdout.write(self.style.SUCCESS("RUN add_default_records"))
        add_default_records()

        self.stdout.write(self.style.SUCCESS("RUN install_db_functions"))
        install_db_functions()

        self.stdout.write(self.style.SUCCESS("RUN install_db_last_functions"))
        install_db_last_functions()

        self.stdout.write(self.style.SUCCESS("RUN update application version in database"))
        current_version = settings.VERSION
        if current_version is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("""
                    CREATE OR REPLACE FUNCTION get_application_version() RETURNS varchar
                        LANGUAGE plpgsql AS
                    $$
                    BEGIN
                        RETURN {current_version};
                    END $$; 
                """).format(current_version=current_version)
                )

        sync_db_meta_tables()
        export_datamodel_to_excel()

        self.stdout.write(self.style.WARNING("Don't forget to update the hasura metadata"))
        self.stdout.write(self.style.SUCCESS("Successfully ran migrate_and_update"))


if __name__ == "__main__":
    Command().handle()
