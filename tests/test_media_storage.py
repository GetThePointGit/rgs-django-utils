"""Tests voor ``rgs_django_utils.media_storage``.

De functies zijn puur: ze bouwen alleen ``STORAGES``-entries en hebben geen
Django-settings of database nodig.
"""

import pytest
from django.core.exceptions import ImproperlyConfigured

from rgs_django_utils.media_storage import (
    MEDIA_S3_SUBPATHS,
    _require_s3_opts,
    _s3_relative_to_path,
    default_media_storage,
    media_nested_storage,
    tiles_storage_entry,
)

S3_OPTS = {
    "key": "AK123",
    "secret": "SK456",
    "endpoint_url": "https://s3.nl-ams.scw.cloud",
    "bucket": "ww-media",
    "prefix": "uploads",
    "region": "nl-ams",
}

# ── _s3_relative_to_path ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prefix", "verwacht"),
    [
        ("", "bucket"),
        (None, "bucket"),
        ("uploads", "bucket/uploads"),
        ("/uploads/2026/", "bucket/uploads/2026"),
        ("/", "bucket"),
    ],
)
def test_relative_to_path_combineert_bucket_en_prefix(prefix, verwacht):
    assert _s3_relative_to_path("bucket", prefix) == verwacht


# ── _require_s3_opts ────────────────────────────────────────────────────────


def test_require_s3_opts_laat_volledige_opties_door():
    assert _require_s3_opts({"bucket": "b", "key": "k", "secret": "s"}) is None


@pytest.mark.parametrize(
    ("opts", "ontbrekend"),
    [
        ({"key": "k", "secret": "s"}, "MEDIA_S3_BUCKET"),
        ({"bucket": "b", "secret": "s"}, "MEDIA_S3_ACCESS_KEY"),
        ({"bucket": "b", "key": "k"}, "MEDIA_S3_SECRET"),
        ({"bucket": "", "key": "k", "secret": "s"}, "MEDIA_S3_BUCKET"),
        ({}, "MEDIA_S3_BUCKET, MEDIA_S3_ACCESS_KEY, MEDIA_S3_SECRET"),
    ],
)
def test_require_s3_opts_noemt_wat_ontbreekt(opts, ontbrekend):
    with pytest.raises(ImproperlyConfigured) as exc:
        _require_s3_opts(opts)
    assert str(exc.value) == (
        f"MEDIA_STORAGE=s3 vereist MEDIA_S3_BUCKET, MEDIA_S3_ACCESS_KEY en MEDIA_S3_SECRET (ontbrekend: {ontbrekend})."
    )


def test_require_s3_opts_met_eigen_namen():
    """Een app met andere env-namen krijgt die terug in de foutmelding."""
    namen = {"bucket": "S3_BUCKET_MEDIA", "key": "S3_ACCESS_KEY", "secret": "S3_SECRET_KEY"}
    with pytest.raises(ImproperlyConfigured) as exc:
        _require_s3_opts({"bucket": "b"}, "MEDIA_STORAGE", namen)
    assert str(exc.value) == (
        "MEDIA_STORAGE=s3 vereist S3_BUCKET_MEDIA, S3_ACCESS_KEY en S3_SECRET_KEY "
        "(ontbrekend: S3_ACCESS_KEY, S3_SECRET_KEY)."
    )


# ── default_media_storage ───────────────────────────────────────────────────


def test_local_gebruikt_de_filesystem_storage():
    """Geen S3-OPTIONS in de lokale default."""
    assert default_media_storage("local") == {"BACKEND": "django.core.files.storage.FileSystemStorage"}


@pytest.mark.parametrize("waarde", ["", "something-else", "S3", None])
def test_onbekende_waarde_valt_terug_op_filesystem(waarde):
    assert default_media_storage(waarde, None) == {"BACKEND": "django.core.files.storage.FileSystemStorage"}


def test_local_faalt_nooit_ook_zonder_opties():
    """Lokale dev en CI zetten geen S3-variabelen."""
    default_media_storage("local", {})
    default_media_storage("local", None)


def test_s3_gebruikt_fsspec_met_storage_config():
    assert default_media_storage("s3", S3_OPTS) == {
        "BACKEND": "django_fsspec.FsspecStorage",
        "OPTIONS": {
            "storage_config": {
                "protocol": "s3",
                "key": "AK123",
                "secret": "SK456",
                "endpoint_url": "https://s3.nl-ams.scw.cloud",
                # bucket + prefix worden relative_to_path (fsspec-contract).
                "relative_to_path": "ww-media/uploads",
                "client_kwargs": {"region_name": "nl-ams"},
            }
        },
    }


def test_s3_zonder_prefix_en_regio():
    result = default_media_storage("s3", {"bucket": "ww-media", "key": "AK123", "secret": "SK456"})
    storage_config = result["OPTIONS"]["storage_config"]
    assert storage_config["relative_to_path"] == "ww-media"
    assert storage_config["client_kwargs"] == {"region_name": "nl-ams"}
    assert storage_config["endpoint_url"] is None


def test_s3_met_eigen_regio():
    result = default_media_storage("s3", {**S3_OPTS, "region": "fr-par"})
    assert result["OPTIONS"]["storage_config"]["client_kwargs"] == {"region_name": "fr-par"}


@pytest.mark.parametrize(
    "opts",
    [
        {"key": "AK123", "secret": "SK456"},
        {"bucket": "ww-media", "secret": "SK456"},
        {"bucket": "ww-media", "key": "AK123"},
        None,
    ],
)
def test_s3_zonder_bucket_key_of_secret_faalt_hard(opts):
    """Geen stille terugval: een placeholder-bucket schrijft naar de verkeerde plek."""
    with pytest.raises(ImproperlyConfigured, match="MEDIA_STORAGE=s3 vereist"):
        default_media_storage("s3", opts)


def test_s3_zonder_validatie_bouwt_de_entry_uit_wat_er_is():
    result = default_media_storage("s3", {"bucket": "urbanworks-media"}, validate=False)
    storage_config = result["OPTIONS"]["storage_config"]
    assert storage_config["relative_to_path"] == "urbanworks-media"
    assert storage_config["key"] is None
    assert storage_config["secret"] is None


def test_s3_met_eigen_env_namen_in_de_foutmelding():
    namen = {"bucket": "S3_BUCKET_MEDIA", "key": "S3_ACCESS_KEY", "secret": "S3_SECRET_KEY"}
    with pytest.raises(ImproperlyConfigured, match="ontbrekend: S3_BUCKET_MEDIA"):
        default_media_storage("s3", {"key": "k", "secret": "s"}, env_names=namen)


# ── media_nested_storage ────────────────────────────────────────────────────


@pytest.mark.parametrize("opts", [None, {}, {"bucket": ""}])
def test_nested_zonder_bucket_heeft_alleen_de_lokale_default(opts):
    """Zonder bucket (lokale dev/CI) valt elk pad terug op de lokale schijf."""
    result = media_nested_storage(opts) if opts is not None else media_nested_storage()
    assert result == {
        "BACKEND": "django_fsspec.FsspecStorage",
        "OPTIONS": {
            "storage_config": {
                "protocol": "nested",
                "path_storage_configs": {"default": {"protocol": "file", "auto_mkdir": True}},
            }
        },
    }


def test_nested_met_bucket_stuurt_de_vier_subpaden_naar_s3():
    opts = {
        "key": "AK123",
        "secret": "SK456",
        "endpoint_url": "https://s3.nl-ams.scw.cloud",
        "bucket": "waterworks-staging-media",
        "prefix": "dev",
    }
    path_storage_configs = media_nested_storage(opts)["OPTIONS"]["storage_config"]["path_storage_configs"]
    assert set(path_storage_configs) == {"global", "org", "project", "user", "default"}
    assert MEDIA_S3_SUBPATHS == ("global", "org", "project", "user")
    assert path_storage_configs["default"] == {"protocol": "file", "auto_mkdir": True}
    for subpath in MEDIA_S3_SUBPATHS:
        assert path_storage_configs[subpath] == {
            "protocol": "s3",
            "endpoint_url": "https://s3.nl-ams.scw.cloud",
            "key": "AK123",
            "secret": "SK456",
            "relative_to_path": f"waterworks-staging-media/dev/{subpath}",
        }


def test_nested_zonder_prefix_laat_het_prefixsegment_weg():
    result = media_nested_storage({"bucket": "waterworks-prod-media"})
    path_storage_configs = result["OPTIONS"]["storage_config"]["path_storage_configs"]
    assert path_storage_configs["global"]["relative_to_path"] == "waterworks-prod-media/global"


def test_nested_met_eigen_subpaden():
    result = media_nested_storage({"bucket": "b"}, subpaths=("fotos",))
    path_storage_configs = result["OPTIONS"]["storage_config"]["path_storage_configs"]
    assert set(path_storage_configs) == {"fotos", "default"}
    assert path_storage_configs["fotos"]["relative_to_path"] == "b/fotos"


# ── tiles_storage_entry ─────────────────────────────────────────────────────


@pytest.mark.parametrize("waarde", ["local", "", None])
def test_tiles_local_is_filesystem_onder_var_dir(waarde):
    """store_pmtiles vervangt de PMTiles van een bron onder dezelfde naam."""
    assert tiles_storage_entry(waarde, "/srv/var") == {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": "/srv/var/tiles", "base_url": "/tiles/", "allow_overwrite": True},
    }


def test_tiles_s3_is_fsspec_met_overschrijven():
    opts = {**S3_OPTS, "bucket": "waterworks-prod-tiles", "prefix": "prod"}
    assert tiles_storage_entry("s3", "/srv/var", opts) == {
        "BACKEND": "django_fsspec.FsspecStorage",
        "OPTIONS": {
            "on_collision": "overwrite",
            "storage_config": {
                "protocol": "s3",
                "key": "AK123",
                "secret": "SK456",
                "endpoint_url": "https://s3.nl-ams.scw.cloud",
                "relative_to_path": "waterworks-prod-tiles/prod",
                "client_kwargs": {"region_name": "nl-ams"},
            },
        },
    }


def test_tiles_s3_is_gelijk_aan_media_plus_overschrijven():
    """De urbanworks-variant: de media-entry met ``on_collision`` erbij."""
    entry = default_media_storage("s3", S3_OPTS)
    entry["OPTIONS"]["on_collision"] = "overwrite"
    assert tiles_storage_entry("s3", "/srv/var", S3_OPTS) == entry


def test_tiles_s3_zonder_credentials_faalt_hard():
    with pytest.raises(ImproperlyConfigured) as exc:
        tiles_storage_entry("s3", "/srv/var", {"bucket": "waterworks-prod-tiles"})
    assert str(exc.value) == (
        "TILES_STORAGE=s3 vereist S3_BUCKET_TILES, S3_ACCESS_KEY en S3_SECRET_KEY "
        "(ontbrekend: S3_ACCESS_KEY, S3_SECRET_KEY)."
    )


def test_tiles_s3_zonder_opties_faalt_hard():
    with pytest.raises(ImproperlyConfigured, match="ontbrekend: S3_BUCKET_TILES, S3_ACCESS_KEY, S3_SECRET_KEY"):
        tiles_storage_entry("s3", "/srv/var")


def test_tiles_s3_zonder_validatie():
    result = tiles_storage_entry("s3", "/srv/var", {"bucket": "urbanworks-tiles", "prefix": "prod"}, validate=False)
    assert result["OPTIONS"]["on_collision"] == "overwrite"
    assert result["OPTIONS"]["storage_config"]["relative_to_path"] == "urbanworks-tiles/prod"
