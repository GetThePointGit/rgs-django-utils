import json
import os
import urllib.request
import urllib.error

from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


class Command(BaseCommand):
    help = "generate json with hasura config"

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--export_path",
            help="Path to export metadata to. Default is the hasura directory in the project root.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Apply the generated metadata directly to Hasura via the metadata API. "
                "Requires HASURA_GRAPHQL_URL and HASURA_GRAPHQL_ADMIN_SECRET environment variables."
            ),
        )

    def handle(self, *args, **options):
        self.stdout.write("Start generate_hasura_metadata")

        from rgs_django_utils.commands.hasura_permissions import HasuraPermissions

        perm = HasuraPermissions()

        export_path = options.get("export_path")
        perm.write_generate_hasura_metadata(export_path)

        self.stdout.write(self.style.SUCCESS("Successfully ran generate_hasura_metadata"))

        if options.get("apply"):
            self._apply_metadata(perm)

    def _apply_metadata(self, perm):
        hasura_url = os.environ.get("HASURA_GRAPHQL_URL")
        admin_secret = os.environ.get("HASURA_GRAPHQL_ADMIN_SECRET")

        if not hasura_url:
            self.stderr.write(self.style.ERROR(
                "HASURA_GRAPHQL_URL is niet ingesteld. "
                "Stel deze in, bijv. http://localhost:8080"
            ))
            return

        if not admin_secret:
            self.stderr.write(self.style.ERROR(
                "HASURA_GRAPHQL_ADMIN_SECRET is niet ingesteld."
            ))
            return

        metadata = perm.generate_hasura_metadata()

        payload = json.dumps({
            "type": "replace_metadata",
            "version": 2,
            "args": {
                "allow_inconsistent_metadata": True,
                "metadata": metadata["metadata"],
            },
        }).encode("utf-8")

        url = hasura_url.rstrip("/") + "/v1/metadata"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hasura-Admin-Secret": admin_secret,
            },
            method="POST",
        )

        self.stdout.write(f"Metadata toepassen op {url}...")

        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("is_consistent") is False:
                    self.stdout.write(self.style.WARNING(
                        "Metadata toegepast, maar Hasura meldt inconsistenties:"
                    ))
                    for inc in body.get("inconsistent_objects", []):
                        self.stdout.write(f"  - {inc.get('type')}: {inc.get('name', '')} — {inc.get('reason', '')}")
                else:
                    self.stdout.write(self.style.SUCCESS("Metadata succesvol toegepast op Hasura."))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            self.stderr.write(self.style.ERROR(f"Hasura API fout ({e.code}): {body}"))
        except urllib.error.URLError as e:
            self.stderr.write(self.style.ERROR(f"Kan Hasura niet bereiken: {e.reason}"))


if __name__ == "__main__":
    Command().handle()
