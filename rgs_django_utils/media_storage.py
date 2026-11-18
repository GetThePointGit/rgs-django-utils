"""Selection of the Django storage entries for media and tiles.

Builds the ``STORAGES`` entries the backends (waterworks, urbanworks) share:
the ``default`` media storage, the nested ``"media"`` storage (photo import)
and the ``tiles`` storage of ``rgs_django_spatial``.

Which backend handles user uploads/downloads is gated on an environment
variable (``MEDIA_STORAGE``, ``TILES_STORAGE``) so that local development and
not-yet-migrated environments keep the on-disk ``FileSystemStorage``, while
S3-backed environments switch to Scaleway Object Storage via
``django-fsspec``.

The functions are pure (free of any Django-settings import side effects,
besides the ``ImproperlyConfigured`` exception class), so the app calls them
from its settings module and they can be unit-tested without settings.
``django-fsspec`` and ``s3fs`` are only needed by the app that actually
selects the S3 backend; this module does not import them.
"""

import os

from django.core.exceptions import ImproperlyConfigured

FSSPEC_BACKEND = "django_fsspec.FsspecStorage"
FILESYSTEM_BACKEND = "django.core.files.storage.FileSystemStorage"

#: Path segments under which the nested ``"media"`` storage routes to S3.
#: Every other path falls back to the local ``"default"`` sub-config.
MEDIA_S3_SUBPATHS = ("global", "org", "project", "user")

#: Environment variable names quoted in the error of a missing S3 option for
#: the ``default`` media storage.
MEDIA_ENV_NAMES = {"bucket": "MEDIA_S3_BUCKET", "key": "MEDIA_S3_ACCESS_KEY", "secret": "MEDIA_S3_SECRET"}

#: Environment variable names quoted in the error of a missing S3 option for
#: the ``tiles`` storage.
TILES_ENV_NAMES = {"bucket": "S3_BUCKET_TILES", "key": "S3_ACCESS_KEY", "secret": "S3_SECRET_KEY"}


def _s3_relative_to_path(bucket, prefix=""):
    """Combine an S3 bucket and optional key prefix into ``relative_to_path``.

    ``django_fsspec`` requires the ``s3`` protocol to fix the bucket (and an
    optional key prefix) through ``storage_config['relative_to_path']``, e.g.
    ``"my-bucket"`` or ``"my-bucket/uploads/2026"``.

    Parameters
    ----------
    bucket : str
        The S3 bucket name.
    prefix : str, optional
        An optional key prefix within the bucket. Leading/trailing slashes
        are normalised away.

    Returns
    -------
    str
        ``bucket`` when no prefix is given, otherwise ``bucket/prefix``.
    """
    prefix = (prefix or "").strip("/")
    if prefix:
        return f"{bucket}/{prefix}"
    return bucket


def _require_s3_opts(opts, setting="MEDIA_STORAGE", env_names=MEDIA_ENV_NAMES):
    """Validate that ``opts`` carries everything needed to talk to S3.

    Parameters
    ----------
    opts : dict
        Must contain non-empty ``bucket``, ``key`` and ``secret`` entries.
    setting : str, optional
        Name of the environment variable that selected S3, for the error
        message (default ``"MEDIA_STORAGE"``).
    env_names : dict of str, optional
        Environment variable name per option (``bucket``, ``key``,
        ``secret``), for the error message (default :data:`MEDIA_ENV_NAMES`).

    Raises
    ------
    django.core.exceptions.ImproperlyConfigured
        When one or more of ``bucket``/``key``/``secret`` is missing. This is
        a deliberate hard failure at settings-import time: a silent fallback
        (e.g. a placeholder bucket name) would risk writing to, or reading
        from, the wrong place in production. A local storage never reaches
        this check, so local dev/CI without any S3 variables set is
        unaffected.
    """
    names = [env_names[option] for option in ("bucket", "key", "secret")]
    missing = [env_names[option] for option in ("bucket", "key", "secret") if not opts.get(option)]
    if missing:
        raise ImproperlyConfigured(
            f"{setting}=s3 vereist {names[0]}, {names[1]} en {names[2]} (ontbrekend: {', '.join(missing)})."
        )


def _s3_storage_config(opts):
    """Build the ``storage_config`` that ``django_fsspec`` hands to ``fsspec``.

    Parameters
    ----------
    opts : dict
        S3 connection options, see :func:`default_media_storage`.

    Returns
    -------
    dict
        The ``s3`` storage config, with bucket and prefix combined into
        ``relative_to_path``.
    """
    return {
        "protocol": "s3",
        "key": opts.get("key"),
        "secret": opts.get("secret"),
        "endpoint_url": opts.get("endpoint_url"),
        "relative_to_path": _s3_relative_to_path(opts.get("bucket"), opts.get("prefix", "")),
        "client_kwargs": {"region_name": opts.get("region", "nl-ams")},
    }


def default_media_storage(media_storage, opts=None, *, validate=True, env_names=MEDIA_ENV_NAMES):
    """Build the ``STORAGES['default']`` entry for the chosen media backend.

    Parameters
    ----------
    media_storage : str
        Either ``"s3"`` (Scaleway Object Storage via ``django-fsspec``) or
        anything else (treated as ``"local"``: the on-disk
        ``FileSystemStorage``).
    opts : dict, optional
        S3 connection options. Only consulted when ``media_storage == "s3"``.
        Recognised keys:

        ``key`` : str
            S3 access key.
        ``secret`` : str
            S3 secret key.
        ``endpoint_url`` : str
            S3 endpoint URL.
        ``bucket`` : str
            Target bucket for media objects.
        ``prefix`` : str, optional
            Key prefix within the bucket.
        ``region`` : str, optional
            S3 region passed through to s3fs ``client_kwargs`` (default
            ``"nl-ams"``).
    validate : bool, optional
        Hard-fail when ``bucket``, ``key`` or ``secret`` is missing (default
        ``True``). ``False`` builds the entry from whatever is given.
    env_names : dict of str, optional
        Environment variable name per option, for the error message (default
        :data:`MEDIA_ENV_NAMES`).

    Returns
    -------
    dict
        A Django ``STORAGES`` entry with ``BACKEND`` (and, for S3,
        ``OPTIONS``).

    Raises
    ------
    django.core.exceptions.ImproperlyConfigured
        When ``media_storage == "s3"``, ``validate`` is on and
        ``bucket``/``key``/``secret`` are not all set, see
        :func:`_require_s3_opts`.

    Notes
    -----
    ``django_fsspec.FsspecStorage`` does *not* read flat ``key``/``secret``/
    ``endpoint_url``/``bucket``/``prefix`` keys directly. It expects a nested
    ``storage_config`` dict that is handed verbatim to ``fsspec.filesystem``,
    with the bucket (+ optional prefix) supplied via ``relative_to_path``.
    """
    if media_storage == "s3":
        opts = opts or {}
        if validate:
            _require_s3_opts(opts, "MEDIA_STORAGE", env_names)
        return {
            "BACKEND": FSSPEC_BACKEND,
            "OPTIONS": {"storage_config": _s3_storage_config(opts)},
        }
    return {"BACKEND": FILESYSTEM_BACKEND}


def media_nested_storage(opts=None, subpaths=MEDIA_S3_SUBPATHS):
    """Build the ``STORAGES['media']`` nested ``django_fsspec`` entry.

    Used by ``DynamicStorageFileField(storage_key="media")`` (photo import).
    Paths under ``subpaths`` route to S3, each into its own subfolder under
    the same ``<bucket>/<prefix>`` as :func:`default_media_storage`; every
    other path falls back to a local ``FileSystemStorage``.

    Parameters
    ----------
    opts : dict, optional
        Same shape as :func:`default_media_storage`'s ``opts``. Unlike that
        function, this one is **not** gated by ``MEDIA_STORAGE``: it is
        deliberately always callable.
    subpaths : tuple of str, optional
        Path segments that route to S3 (default :data:`MEDIA_S3_SUBPATHS`).

    Returns
    -------
    dict
        A Django ``STORAGES`` entry (``django_fsspec.FsspecStorage``,
        ``protocol: "nested"``).

    Notes
    -----
    No ``MEDIA_STORAGE`` gate applies here (unlike
    :func:`default_media_storage`): this "media" storage exists independently
    of the plain-FileField default storage and is always the nested S3/local
    config below. Deliberate choice for the *bucket-missing* case (local
    dev/CI, where the bucket is typically unset): rather than hard-failing at
    settings-import time (that would break every local/CI run that never
    touches photo import) or keeping a silently-wrong placeholder bucket
    name, the S3 subpaths are simply **omitted** when ``opts['bucket']`` is
    empty. Every path then falls through to the local ``"default"`` file
    storage. This keeps settings-import side-effect-free and lets photo
    import be smoke-tested locally without S3 credentials; in a real
    environment ``MEDIA_STORAGE=s3`` is set and :func:`default_media_storage`
    already hard-fails on the same missing bucket/key/secret.
    """
    opts = opts or {}
    path_storage_configs = {
        "default": {
            "protocol": "file",
            "auto_mkdir": True,
        },
    }
    bucket = opts.get("bucket")
    if bucket:
        relative_to_path_base = _s3_relative_to_path(bucket, opts.get("prefix", ""))
        for subpath in subpaths:
            path_storage_configs[subpath] = {
                "protocol": "s3",
                "endpoint_url": opts.get("endpoint_url"),
                "key": opts.get("key"),
                "secret": opts.get("secret"),
                "relative_to_path": f"{relative_to_path_base}/{subpath}",
            }
    return {
        "BACKEND": FSSPEC_BACKEND,
        "OPTIONS": {
            "storage_config": {
                "protocol": "nested",
                "path_storage_configs": path_storage_configs,
            },
        },
    }


def tiles_storage_entry(tiles_storage, var_dir, opts=None, *, validate=True, env_names=TILES_ENV_NAMES):
    """Build the ``STORAGES['tiles']`` entry that ``rgs_django_spatial.tiles`` uses.

    Parameters
    ----------
    tiles_storage : str
        ``"s3"`` for Scaleway Object Storage via ``django-fsspec`` (private
        bucket, presigned GET-URLs); anything else is local.
    var_dir : str
        Root of the runtime data directory; local tiles live in
        ``<var_dir>/tiles`` and are served under ``/tiles/``.
    opts : dict, optional
        Same shape as :func:`default_media_storage`'s ``opts`` (``key``,
        ``secret``, ``endpoint_url``, ``bucket``, ``prefix``, ``region``).
        Only consulted when ``tiles_storage == "s3"``.
    validate : bool, optional
        Hard-fail when ``bucket``, ``key`` or ``secret`` is missing (default
        ``True``). ``False`` builds the entry from whatever is given.
    env_names : dict of str, optional
        Environment variable name per option, for the error message (default
        :data:`TILES_ENV_NAMES`).

    Returns
    -------
    dict
        A Django ``STORAGES`` entry. Both variants allow overwriting under the
        same name: ``rgs_django_spatial.tiles.storage.store_pmtiles`` replaces
        the PMTiles of a source in place and rejects a storage that renames.

    Raises
    ------
    django.core.exceptions.ImproperlyConfigured
        When ``tiles_storage == "s3"``, ``validate`` is on and
        ``bucket``/``key``/``secret`` are not all set.
    """
    if tiles_storage == "s3":
        opts = opts or {}
        if validate:
            _require_s3_opts(opts, "TILES_STORAGE", env_names)
        return {
            "BACKEND": FSSPEC_BACKEND,
            "OPTIONS": {"on_collision": "overwrite", "storage_config": _s3_storage_config(opts)},
        }
    return {
        "BACKEND": FILESYSTEM_BACKEND,
        "OPTIONS": {
            "location": os.path.join(var_dir, "tiles"),
            "base_url": "/tiles/",
            "allow_overwrite": True,
        },
    }
