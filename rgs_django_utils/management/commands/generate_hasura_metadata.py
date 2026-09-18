import json
import os
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand, CommandError

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


class Command(BaseCommand):
    """Generate and optionally apply Hasura metadata.

    Without flags: writes ``hasura_metadata_exported.json`` using
    :class:`~rgs_django_utils.commands.hasura_permissions.HasuraPermissions`.

    With ``--apply``: also POSTs the freshly generated metadata to the
    Hasura admin API.

    With ``--apply-only``: skips generation and POSTs an existing JSON
    file (useful in CI when metadata is generated in one step and applied
    in another).

    Every way in which an apply can fail to take effect raises
    :class:`~django.core.management.base.CommandError`, so the command exits
    non-zero. Dat is dragend: deze metadata is waar de rechten echt staan, en
    een deploy-job die stil doorloopt laat een rechtenwijziging niet landen
    terwijl elk signaal groen blijft.
    """

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
        parser.add_argument(
            "--apply-only",
            action="store_true",
            help=(
                "Skip generation and apply the existing metadata JSON file to Hasura. "
                "Uses --export_path or the default location."
            ),
        )
        parser.add_argument(
            "--allow-inconsistent",
            action="store_true",
            help=(
                "Do not fail when Hasura reports inconsistent objects after applying. "
                "Without this flag an inconsistent apply is an error, because Hasura "
                "silently drops the objects it could not parse."
            ),
        )

    def handle(self, *args, **options):
        allow_inconsistent = bool(options.get("allow_inconsistent"))

        if options.get("apply_only"):
            self._apply_from_file(options.get("export_path"), allow_inconsistent=allow_inconsistent)
            return

        self.stdout.write("Start generate_hasura_metadata")

        from rgs_django_utils.commands.hasura_permissions import HasuraPermissions

        perm = HasuraPermissions()

        export_path = options.get("export_path")
        perm.write_generate_hasura_metadata(export_path)

        self.stdout.write("Metadata gegenereerd.")

        if options.get("apply"):
            self._apply_metadata(perm, allow_inconsistent=allow_inconsistent)

        # NOTE: deze regel stond hier boven de apply. Daardoor eindigde het log
        # altijd op "Successfully ran ...", ook als de apply daarna faalde.
        self.stdout.write(self.style.SUCCESS("Successfully ran generate_hasura_metadata"))

    def _apply_from_file(self, export_path=None, allow_inconsistent=False):
        """Load existing metadata JSON from disk and apply it to Hasura.

        Parameters
        ----------
        export_path : str, optional
            Path to the metadata JSON. Defaults to
            ``<ROOT_DIR>/hasura/hasura_metadata_exported.json``.
        allow_inconsistent : bool, default False
            Passed through to :meth:`_send_metadata_to_hasura`.

        Raises
        ------
        CommandError
            When *export_path* does not exist.
        """
        from django.conf import settings as django_settings

        if export_path is None:
            export_path = os.path.join(django_settings.ROOT_DIR, "hasura", "hasura_metadata_exported.json")

        if not os.path.exists(export_path):
            raise CommandError(f"Metadata bestand niet gevonden: {export_path}")

        self.stdout.write(f"Metadata laden uit {export_path}...")

        with open(export_path, "r") as f:
            metadata = json.load(f)

        self._send_metadata_to_hasura(metadata.get("metadata", metadata), allow_inconsistent=allow_inconsistent)

    def _apply_metadata(self, perm, allow_inconsistent=False):
        metadata = perm.generate_hasura_metadata()
        self._send_metadata_to_hasura(metadata["metadata"], allow_inconsistent=allow_inconsistent)

    @staticmethod
    def _hasura_credentials():
        """Read the Hasura admin endpoint and secret from settings, then the environment.

        Returns
        -------
        tuple of (str or None, str or None)
            URL and admin secret; each ``None`` when neither source has one.

        Notes
        -----
        Dit verving een ``if settings is None``-tak die nooit liep: ``settings``
        is een ``LazySettings``-object en is dus nooit ``None``, waardoor de
        environment-fallback voor script-mode onbereikbaar was.
        """
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        try:
            url = getattr(settings, "HASURA_GRAPHQL_URL", None)
            secret = getattr(settings, "HASURA_GRAPHQL_ADMIN_SECRET", None)
        except ImproperlyConfigured:
            url = secret = None

        return (
            url or os.environ.get("HASURA_GRAPHQL_URL"),
            secret or os.environ.get("HASURA_GRAPHQL_ADMIN_SECRET"),
        )

    def _send_metadata_to_hasura(self, metadata, allow_inconsistent=False):
        """POST *metadata* to the Hasura metadata API.

        Parameters
        ----------
        metadata : dict
            The metadata document to install.
        allow_inconsistent : bool, default False
            When ``True``, inconsistent objects reported by Hasura are logged
            as a warning instead of raising.

        Raises
        ------
        CommandError
            When the URL or admin secret is missing, when Hasura is
            unreachable, when it answers with an HTTP error, or when it
            reports inconsistent objects while *allow_inconsistent* is
            ``False``.
        """
        hasura_url, admin_secret = self._hasura_credentials()

        if not hasura_url:
            raise CommandError("HASURA_GRAPHQL_URL is niet ingesteld. Stel deze in, bijv. http://localhost:8080")

        if not admin_secret:
            raise CommandError("HASURA_GRAPHQL_ADMIN_SECRET is niet ingesteld.")

        payload = json.dumps(
            {
                "type": "replace_metadata",
                "version": 2,
                "args": {
                    "allow_inconsistent_metadata": True,
                    "metadata": metadata,
                },
            }
        ).encode("utf-8")

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
        except urllib.error.HTTPError as e:
            # HTTPError is een subklasse van URLError, dus deze tak moet eerst.
            raise CommandError(f"Hasura API fout ({e.code}): {e.read().decode('utf-8')}") from e
        except urllib.error.URLError as e:
            raise CommandError(f"Kan Hasura niet bereiken: {e.reason}") from e

        if body.get("is_consistent") is not False:
            self.stdout.write(self.style.SUCCESS("Metadata succesvol toegepast op Hasura."))
            return

        # Hasura heeft de metadata aangenomen (allow_inconsistent_metadata) maar
        # de objecten die het niet kon plaatsen laten vallen. Precies daar gaan
        # rechten stil verloren, dus dit is standaard een fout.
        regels = [
            f"  - {inc.get('type')}: {inc.get('name', '')} — {inc.get('reason', '')}"
            for inc in body.get("inconsistent_objects", [])
        ]
        melding = "\n".join(["Metadata toegepast, maar Hasura meldt inconsistenties:", *regels])

        if allow_inconsistent:
            self.stdout.write(self.style.WARNING(melding))
            return

        raise CommandError(f"{melding}\n\nGebruik --allow-inconsistent om hier bewust langs te gaan.")


if __name__ == "__main__":
    Command().handle()
