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
        Path(cur_dir, ".env").touch(exist_ok=True)
        if check_env_file_has_param(env_file, parameter):
            return env_file
        if including_dev:
            env_file_dev = Path(cur_dir, ".env.dev")
            Path(cur_dir, ".env.dev").touch(exist_ok=True)
            if check_env_file_has_param(env_file_dev, parameter):
                return env_file_dev
        parent_dir = cur_dir.parent
        if parent_dir == cur_dir:  # reached the root directory
            break
        cur_dir = parent_dir

    return None


def reexec_with_project_python(django_root: Path) -> None:
    """Re-execute the current script using the project's Python interpreter.

    Checks for pixi environments (``.pixi/envs/default``) and common virtualenv
    locations (``.venv``, ``venv``). When a project Python is found and differs
    from the running interpreter, replaces the current process via ``os.execv``
    so that all project dependencies are available. No-ops when already running
    inside the project environment.

    Parameters
    ----------
    django_root : Path
        The directory containing ``manage.py`` for the target Django project.
    """
    candidates = [
        django_root / ".pixi" / "envs" / "default" / "bin" / "python",
        django_root / ".venv" / "bin" / "python",
        django_root / "venv" / "bin" / "python",
    ]
    for python in candidates:
        if python.exists() and os.path.realpath(sys.executable) != os.path.realpath(python):
            os.execv(str(python), [str(python)] + sys.argv)


def find_django_root(start_dir: Path) -> Path | None:
    """Find the directory containing ``manage.py`` near *start_dir*.

    Checks *start_dir* itself first, then its immediate subdirectories,
    then walks upward to the filesystem root.

    Parameters
    ----------
    start_dir : Path
        Directory to begin the search from.

    Returns
    -------
    Path or None
        The directory containing ``manage.py``, or ``None`` if not found.
    """
    if (start_dir / "manage.py").exists():
        return start_dir
    for subdir in sorted(start_dir.iterdir()):
        if subdir.is_dir() and (subdir / "manage.py").exists():
            return subdir
    cur = start_dir.parent
    while True:
        if (cur / "manage.py").exists():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
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

    pathname = Path(sys.argv[0]).parent
    path = find_env_file_with_param(pathname, "PATH_TO_THISSITE_ENV", including_dev=True)
    if path is None:
        raise Exception("PATH_TO_THISSITE_ENV not set and no .env file found with PATH_TO_THISSITE_ENV parameter")
    else:
        dotenv.load_dotenv(path)
        env_file = os.getenv("PATH_TO_THISSITE_ENV")
        django_root = find_django_root(Path(env_file).parent) if env_file else None
        if django_root:
            reexec_with_project_python(django_root)
        pathname = django_root or Path(sys.argv[0]).parent
        if str(pathname) not in sys.path:
            sys.path.insert(0, str(pathname))
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        if from_env:
            if env_file is not None and check_env_file_has_param(env_file, "DJANGO_SETTINGS_MODULE"):
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
