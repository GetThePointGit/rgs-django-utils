import logging
import os

from django.conf import settings
from django.db import connection

log = logging.getLogger(__name__)

SUB_DIR_BEFORE = getattr(settings, "SUB_DIR_BEFORE", "01_before")
SUB_DIR_LAST = getattr(settings, "SUB_DIR_LAST", "99_last")

_postgres_functions_base_path_cache = None


def _get_base_path():
    """returns the base path for the Postgres functions defined in the 'POSTGRES_INSTALL_ON_MIGRATION_FOLDER'
    set in the django settings."""
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
    """installs all provided in directory '01_before'. will be used to install functions used in migrations (like
    functions for default values)"""

    return install_db_function_in_directory(SUB_DIR_BEFORE)


def install_db_last_functions():
    """installs all provided in directory '99_last'. Scripts will be runned after aal default values, cascading and
    triggers are installed."""

    return install_db_function_in_directory(SUB_DIR_LAST)


def install_db_functions(install_before=False, install_last=False):
    """install the Postgres functions defined in the 'POSTGRES_INSTALL_ON_MIGRATION_FOLDER' set in the settings."""

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
    """install the Postgres functions defined in the 'POSTGRES_INSTALL_ON_MIGRATION_FOLDER' set in the settings.

    :param relative_path: path relative to 'POSTGRES_INSTALL_ON_MIGRATION_FOLDER'
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
