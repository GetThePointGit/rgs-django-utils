import logging
import os
import sys
from pathlib import Path

import django
import dotenv


def check_env_file_has_param(env_file: Path, parameter: str) -> bool:
    """Return ``True`` when *env_file* contains a line starting with *parameter*.

    Parameters
    ----------
    env_file : Path
        Path to the ``.env`` file to inspect.
    parameter : str
        Environment-variable name to look for (matched as a line prefix).

    Returns
    -------
    bool
        ``True`` when the file exists and contains the parameter.
    """
    if not env_file.exists():
        return False

    with open(env_file, "r") as f:
        for line in f:
            if line.startswith(parameter):
                return True
    return False


def find_env_file_with_param(start_dir: Path, parameter: str, including_dev: bool = True) -> Path | None:
    """Walk parent directories looking for a ``.env`` that sets *parameter*.

    Parameters
    ----------
    start_dir : Path
        Directory to start searching from. The search moves up to the
        filesystem root.
    parameter : str
        Environment-variable name that must be set inside the ``.env`` file.
    including_dev : bool, optional
        Also consider ``.env.dev`` in each directory. Default is ``True``.

    Returns
    -------
    Path or None
        Path to the first matching ``.env`` file, or ``None`` when none is
        found up to the root.
    """
    cur_dir = start_dir
    while True:
        env_file = Path(cur_dir, ".env")
        if Path(cur_dir, ".env").touch(exist_ok=True):
            if check_env_file_has_param(env_file, parameter):
                return env_file
        if including_dev:
            env_file_dev = Path(cur_dir, ".env.dev")
            if env_file_dev.touch(exist_ok=True):
                if check_env_file_has_param(env_file_dev, parameter):
                    return env_file_dev
        parent_dir = cur_dir.parent
        if parent_dir == cur_dir:  # reached the root directory
            break
        cur_dir = parent_dir

    return None


def find_settings_module_from_files(start_dir: Path) -> str | None:
    """Locate ``DJANGO_SETTINGS_MODULE`` by walking up to ``manage.py``.

    Starts at *start_dir* and walks up. When it finds a directory
    containing ``manage.py``, it scans that directory's subdirectories for
    the first one that contains ``settings.py`` and returns
    ``<subdir>.settings``.

    Parameters
    ----------
    start_dir : Path
        Directory from which to start the upward search.

    Returns
    -------
    str or None
        Dotted settings-module path (e.g. ``'thissite.settings'``) or
        ``None`` when no matching layout is found.
    """
    cur_dir = start_dir
    while True:
        managed_py = Path(cur_dir, "manage.py")
        if managed_py.exists():
            # look for settings.py in the subdirectories
            for subdir in cur_dir.iterdir():
                if subdir.is_dir() and (subdir / "settings.py").exists():
                    return f"{subdir.name}.settings"
        parent_dir = cur_dir.parent
        if parent_dir == cur_dir:  # reached the root directory
            break
        cur_dir = parent_dir
    return None


def setup_django(from_env=False, log: logging.Logger = None):
    """Initialise Django for script-style modules.

    Ensures ``DJANGO_SETTINGS_MODULE`` is set (by reading a ``.env`` file
    when *from_env* is true, or by scanning for ``manage.py`` otherwise)
    and then calls ``django.setup()``. Intended to be invoked inside an
    ``if __name__ == "__main__":`` guard so command-style modules can be
    run directly without needing a Django management command wrapper.

    Parameters
    ----------
    from_env : bool, optional
        If ``True``, resolve ``DJANGO_SETTINGS_MODULE`` from the nearest
        ``.env`` / ``.env.dev`` file. If ``False`` (default), fall back to
        walking up to ``manage.py``.
    log : logging.Logger, optional
        If provided, a ``StreamHandler`` is attached so log output appears
        on stdout while the script runs.

    Raises
    ------
    Exception
        When ``DJANGO_SETTINGS_MODULE`` cannot be located through either
        mechanism.

    Examples
    --------
    >>> # module-level skeleton for a standalone script
    >>> if __name__ == "__main__":          # doctest: +SKIP
    ...     from rgs_django_utils.setup_django import setup_django
    ...     setup_django()
    ...     main()
    """

    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        pathname = Path(sys.argv[0]).parent

        if from_env:
            env_file = find_env_file_with_param(pathname, "DJANGO_SETTINGS_MODULE", including_dev=True)
            if env_file is not None:
                dotenv.load_dotenv(env_file)
            else:
                raise Exception(
                    "DJANGO_SETTINGS_MODULE not set and no .env file found with DJANGO_SETTINGS_MODULE parameter"
                )
        else:
            # if not from_env, we look for the directory with the managed.py file and look in de subdirectories for a settings.py file
            module_name = find_settings_module_from_files(pathname)
            if module_name is not None:
                os.environ["DJANGO_SETTINGS_MODULE"] = module_name
            else:
                raise Exception(
                    "DJANGO_SETTINGS_MODULE not set and no managed.py file found with settings.py in subdirectories"
                )
    # check if DJANGO_SETTINGS_MODULE is set
    if os.environ.get("DJANGO_SETTINGS_MODULE") is None:
        raise Exception("DJANGO_SETTINGS_MODULE not set in environment variables")

    django.setup()

    if log is not None:
        ch = logging.StreamHandler()
        log.addHandler(ch)
