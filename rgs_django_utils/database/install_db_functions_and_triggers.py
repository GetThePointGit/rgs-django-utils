import logging
import os

from django.conf import settings
from django.db import connection

log = logging.getLogger(__name__)

SUB_DIR_BEFORE = getattr(settings, "SUB_DIR_BEFORE", "01_before")
SUB_DIR_AUTHORIZATION = getattr(settings, "SUB_DIR_AUTHORIZATION", "98_authorization")
SUB_DIR_LAST = getattr(settings, "SUB_DIR_LAST", "99_last")

_postgres_functions_base_path_cache = None


def _get_base_path():
    """Return the cached base path of the Postgres functions directory.

    Reads ``POSTGRES_INSTALL_ON_MIGRATION_FOLDER`` from Django settings, or
    falls back to ``<ROOT_DIR>/postgres/install`` with a warning. The
    resolved path is cached on the module so subsequent calls are free.
    """
    global _postgres_functions_base_path_cache
    if _postgres_functions_base_path_cache is not None:
        return _postgres_functions_base_path_cache

    if hasattr(settings, "POSTGRES_INSTALL_ON_MIGRATION_FOLDER"):
        base_path = settings.POSTGRES_INSTALL_ON_MIGRATION_FOLDER
    else:
        log.warning('"POSTGRES_INSTALL_ON_MIGRATION_FOLDER" not defined in the django settings.')
        base_path = os.path.join(settings.ROOT_DIR, "postgres", "install")
    _postgres_functions_base_path_cache = base_path
    return base_path


def install_db_before_functions():
    """Run the SQL scripts in the ``01_before`` directory.

    These scripts must be installed *before* migrations run because
    migrations reference the functions they define (e.g. default-value
    helpers).
    """

    return install_db_function_in_directory(SUB_DIR_BEFORE)


def install_db_authorization_functions():
    """Run the SQL scripts in the ``98_authorization`` directory.

    Executed after default values, cascading rules and triggers have been
    installed — typically to set up row-level security / Hasura roles.
    """

    return install_db_function_in_directory(SUB_DIR_AUTHORIZATION)


def install_db_last_functions():
    """Run the SQL scripts in the ``99_last`` directory.

    Final-pass scripts that rely on every other DDL change being in place
    (views, grants on Hasura schema, etc.).
    """

    return install_db_function_in_directory(SUB_DIR_LAST)


def install_db_functions(install_before=False, install_last=False):
    """Run every installable Postgres script in the configured folder.

    Walks the directory set by ``settings.POSTGRES_INSTALL_ON_MIGRATION_FOLDER``
    in sorted order and executes each SQL file. The two edge-case folders
    (``01_before`` and ``99_last``) are skipped unless explicitly enabled —
    they have dedicated call sites because of their ordering requirements.

    Parameters
    ----------
    install_before : bool, optional
        Include the ``01_before`` folder. Default is ``False``.
    install_last : bool, optional
        Include the ``99_last`` folder. Default is ``False``.
    """

    base_path = _get_base_path()

    if not os.path.isdir(base_path):
        log.warning("folder %s voor installatie van postgres scripts bestaat niet", base_path)
        return

    for sub_dir in sorted(os.listdir(base_path)):
        if not install_before and sub_dir == SUB_DIR_BEFORE:
            continue
        if not install_last and sub_dir == SUB_DIR_LAST:
            continue

        install_db_function_in_directory(sub_dir)

    log.info("##### done #####")


def install_db_function_in_directory(relative_path: str):
    """Execute every ``*.sql`` file in *relative_path*, in sorted order.

    Silently warns and returns when the directory does not exist so this
    helper can be called for optional subfolders.

    Parameters
    ----------
    relative_path : str
        Directory name relative to ``settings.POSTGRES_INSTALL_ON_MIGRATION_FOLDER``.
    """
    path = os.path.abspath(os.path.join(_get_base_path(), relative_path))

    if not os.path.isdir(path):
        log.warning("folder %s voor installatie van postgres scripts bestaat niet", path)
        return

    log.info("##### directory %s #####", relative_path)

    with connection.cursor() as cursor:
        for filename in sorted(os.listdir(path)):
            with open(os.path.join(path, filename), "r", encoding="utf-8") as f:
                log.info("run script %s", filename)
                cursor.execute(f.read())
